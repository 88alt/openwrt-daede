# Performance fork maintenance — quic-go / outbound

The aggressive build replaces dae's QUIC and outbound dependencies with the
olicesx performance forks. Pins live in `ci/pins.env`; assemble workflows fetch
them from the `kenzok8/*` mirrors so a disappearing upstream branch cannot break
an old release.

## Current frozen pair

| component | branch | pinned commit |
|-----------|--------|---------------|
| outbound | `olicesx/outbound:perf/complete-optimizations` | `ae9f25d31dcf` |
| quic-go | `olicesx/quic-go:fix/audit-remediation` | `08e975ef39de` |

The outbound `go.mod` requires the quic-go pseudo-version ending in
`08e975ef39de`, so these commits must move as a pair. The quic-go base contains
the earlier performance work plus the later QUIC security, buffer ownership and
GSO capacity fixes.

`olicesx/quic-go` is not a GitHub fork of `quic-go/quic-go`; its module name and
history differ. Do not rebase it onto an official quic-go tag. A refresh means
using the exact commit required by outbound, or backporting a specific official
fix onto this lineage.

## Self-owned patches that must survive every sync

The repository currently carries 17 patch files:

- `dae/patches`: 1 regular dae patch.
- `dae/patches_arm`: 2 ARM32 compatibility patches.
- `daed/patches`: 11 daed reliability and update patches.
- `daed/patches_arm`: 2 ARM32 compatibility patches for the embedded dae core.
- `ci/patches/outbound`: 1 SSR buffered-reader fix.
- `ci/patches/quic-go`: currently empty; retained for future backports.

On 2026-08-28 every patch was checked against the pinned upstream source. None
was equivalently absorbed, and all 17 remain required. In particular, outbound
still lacks the SSR `unwrapConn` fix.

The `patch-absorbed` job in `auto-bump.yml` checks every regular, ARM, outbound
and quic-go patch in package order. It reports a patch when reverse apply starts
passing, applies every still-required patch forward, and fails instead of
silently skipping a source it cannot fetch or patch. Confirm the behavior in
upstream before deleting a reported local patch.

## Refresh procedure

1. Read outbound's `go.mod` and resolve the full quic-go commit named by its
   pseudo-version.
2. Audit every local patch against the proposed bases:
   - reverse apply succeeds: upstream may have absorbed it; inspect the source
     before deleting it;
   - forward apply succeeds: keep it;
   - neither succeeds: port it and verify the original behavior still exists.
3. Mirror the exact outbound and quic-go branches into `kenzok8/*` before
   changing `ci/pins.env`.
4. For outbound, apply `ci/patches/outbound/*.patch` and run
   `go test ./protocol/shadowsocks_stream/`.
5. For quic-go, apply any `ci/patches/quic-go/*.patch` and run `go build ./...`.
6. On a staging branch run both assemble workflows and the four-SDK dae/daed
   build gate. Promote to `main` only after every package exists.

## Automatic safeguards

- `Detect upstream changes` holds outbound when its required quic-go suffix no
  longer matches `QUICGO_BASE_COMMIT`.
- `perf-staleness` opens a tracking issue for that mismatch and closes it after
  the pair is aligned again.
- `patch-absorbed` checks all local patch locations so an upstream sync cannot
  silently discard an ARM, daed, SSR or future quic-go fix.

The exact build path is intentionally pinned. Tracking official quic-go releases
directly is not useful here because dae-core depends on the older, incompatible
olicesx API lineage.
