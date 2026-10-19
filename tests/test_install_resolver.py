"""Offline resolver checks; never execute the installer's device mutations."""
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install.sh"
FUNCTIONS = SCRIPT.read_text().split('\nPM="$(detect_manager)"')[0]
SHA = "a" * 64


class ResolverTests(unittest.TestCase):
    def run_sh(self, body):
        return subprocess.run(["sh", "-c", FUNCTIONS + "\n" + body],
                              text=True, capture_output=True)

    def test_curl_failure_discards_partial_output_and_uses_wget(self):
        result = self.run_sh("""
curl() { printf 'partial'; echo 'TLS failure' >&2; return 60; }
wget() { printf 'complete'; }
fetch_text https://example.invalid
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "complete\n")
        self.assertIn("TLS failure", result.stderr)
        self.assertIn("trying wget", result.stderr)

    def test_both_downloaders_fail_without_stdout(self):
        result = self.run_sh("""
curl() { printf partial; return 22; }
wget() { printf partial; return 8; }
fetch_text https://example.invalid
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Fetch failed", result.stderr)

    def test_download_file_falls_back_and_replaces_partial_file(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_sh(f"""
curl() {{ printf partial > '{temp}/output'; return 22; }}
wget() {{ printf complete > "$2"; }}
download_file https://example.invalid '{temp}/output'
cat '{temp}/output'
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "complete")

    def test_index_filters_package_architecture_and_requires_checksum(self):
        records = [
            ("daed-extra", "aarch64_generic", "wrong-name.ipk", SHA),
            ("daed", "x86_64", "wrong-arch.ipk", SHA),
            ("daed", "aarch64_generic", "missing-sha.ipk", ""),
            ("daed", "aarch64_generic", "./daed.ipk", SHA),
            ("luci-app-daede", "all", "luci.ipk", SHA),
        ]
        index = "\n\n".join(
            f"Package: {pkg}\nArchitecture: {arch}\nFilename: {file}\nSHA256sum: {sha}"
            for pkg, arch, file, sha in records) + "\n"
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "Packages.gz"
            fixture.write_bytes(gzip.compress(index.encode()))
            result = self.run_sh(f"""
PM=opkg
EXT=ipk
fetch_text() {{ return 1; }}
download_file() {{ cp '{fixture}' "$2"; }}
if resolve_from_manifest 24.10 aarch64_generic; then exit 9; fi
resolve_from_opkg_index 24.10 aarch64_generic
printf '%s' "$PLAN"
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/daed.ipk|" + SHA, result.stdout)
        self.assertIn("/luci.ipk|" + SHA, result.stdout)
        self.assertNotIn("wrong", result.stdout)
        self.assertIn("manifest unavailable", result.stderr)

    def test_index_rejects_incomplete_corrupt_and_apk_inputs(self):
        for setup in [
            'PM=apk; download_file() { echo called >&2; return 1; }',
            'PM=opkg; download_file() { printf corrupt > "$2"; }',
            'PM=opkg; download_file() { printf "" | gzip > "$2"; }',
        ]:
            result = self.run_sh(setup + "\nresolve_from_opkg_index 24.10 x86_64")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("called", result.stderr)

    def test_github_multiline_and_singleline_json(self):
        payload = {"assets": [{"browser_download_url": url} for url in [
            "https://github.com/o/r/daed_1_aarch64_generic.ipk",
            "https://github.com/o/r/luci-app-daede_1_all.ipk",
            "https://github.com/o/r/vmlinux-btf_1_x86_64.ipk",
        ]]}
        for indent in (None, 2):
            with tempfile.TemporaryDirectory() as temp:
                fixture = Path(temp) / "release.json"
                fixture.write_text(json.dumps(payload, indent=indent))
                result = self.run_sh(f"""
fetch_text() {{ cat '{fixture}'; }}
resolve_from_github aarch64_generic ipk
printf '%s' "$PLAN"
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("daed_1_aarch64_generic.ipk", result.stdout)
            self.assertIn("luci-app-daede_1_all.ipk", result.stdout)

    def test_main_resolves_index_before_github(self):
        main = SCRIPT.read_text().split('\nPM="$(detect_manager)"', 1)[1]
        main = '\nPM="$(detect_manager)"' + main.split('\nrm -rf "$TMP_DIR"', 1)[0]
        body = """
detect_manager() { echo opkg; }
detect_arch() { echo aarch64_generic; }
detect_sdk() { echo 24.10; }
resolve_from_manifest() { echo manifest >&2; return 1; }
resolve_from_opkg_index() { echo index >&2; PLAN=fixture; return 0; }
resolve_from_github() { echo github >&2; return 1; }
""" + main
        result = self.run_sh(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "manifest\nindex\n")
        self.assertIn("Using R2 feed Packages.gz: 24.10/aarch64_generic", result.stdout)

    def test_final_error_reports_device_and_attempted_sdks(self):
        main = SCRIPT.read_text().split('\nPM="$(detect_manager)"', 1)[1]
        main = '\nPM="$(detect_manager)"' + main.split('\nrm -rf "$TMP_DIR"', 1)[0]
        result = self.run_sh("""
detect_manager() { echo opkg; }
detect_arch() { echo aarch64_generic; }
detect_sdk() { echo 25.12; }
fetch_text() { return 1; }
download_file() { return 1; }
""" + main)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GitHub API unavailable or empty", result.stderr)
        self.assertIn("PM=opkg SDK=25.12 arch=aarch64_generic", result.stderr)
        self.assertIn("attempted SDKs: 24.10 25.12", result.stderr)

    def test_sdk_candidates_remain_restricted(self):
        for pm, sdk, expected in [
            ("opkg", "25.12", "24.10\n25.12\n"),
            ("opkg", "24.10", "24.10\n"),
            ("opkg", "23.05", "23.05\n"),
            ("apk", "25.12", "25.12\n"),
            ("apk", "", ""),
        ]:
            result = self.run_sh(f'PM={pm}; package_sdks "{sdk}"')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected)


if __name__ == "__main__":
    unittest.main()
