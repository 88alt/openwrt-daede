# Managed Clash YAML Subscriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn fetched Clash YAML URLs into securely stored, refreshable daede-managed subscriptions while keeping pasted YAML imports as static node snapshots.

**Architecture:** Keep browser-side `js-yaml` and `clash-converter.js` for interactive preview. Add a backend synchronization service that uses the packaged `yq` command to parse YAML into JSON and Lua 5.1 modules to convert nodes, update dae/daed, store secrets, and run scheduled refreshes. LuCI calls the backend service for managed subscriptions and retains its existing browser-side path for static YAML snapshots.

**Tech Stack:** LuCI JavaScript, js-yaml, BusyBox shell, yq v4, Lua 5.1, UCI, dae config generator, daed GraphQL, cron/procd, Node-based unit tests, Playwright on OpenWrt device 252

---

## File Structure

Create or modify these focused units:

- `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.sh`
  - Public backend command: save, sync, sync-due, list-redacted, delete, and credential updates.
- `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.lua`
  - YAML-JSON proxy conversion, scheduling decisions, status records, and backend synchronization orchestration.
- `luci-app-daede/root/usr/share/luci-app-daede/managed-daed.lua`
  - daed GraphQL authentication and safe group/node replacement.
- `luci-app-daede/root/usr/share/luci-app-daede/managed-dae.lua`
  - dae UCI staging, generation, rollback, and safe cleanup.
- `luci-app-daede/root/etc/init.d/daede-managed-subscriptions`
  - Two-minute delayed boot recovery.
- `luci-app-daede/root/etc/cron.d/daede-managed-subscriptions`
  - Periodic due-subscription check.
- `luci-app-daede/root/etc/config/daede_secrets`
  - Root-only source URLs and daed credentials.
- `luci-app-daede/htdocs/luci-static/resources/view/daede/managed-subscriptions.js`
  - Browser-side API and redacted managed-subscription model.
- `luci-app-daede/htdocs/luci-static/resources/view/daede/converter.js`
  - Dynamic third step and managed-subscription list.
- `luci-app-daede/htdocs/luci-static/resources/view/daede/styles.js`
  - Responsive list and form styling.
- `luci-app-daede/po/{templates/daede.pot,zh-cn/daede.po,zh_Hans/daede.po}`
  - English source strings and Chinese translations.
- `luci-app-daede/tests/managed-subscription/`
  - Backend fixtures and regression scripts. Tests remain local unless explicitly approved for publication.

## Task 1: Define And Test Managed Subscription State

**Files:**
- Create: `luci-app-daede/htdocs/luci-static/resources/view/daede/managed-subscriptions.js`
- Modify: `luci-app-daede/htdocs/luci-static/resources/view/daede/airport-sync.js`
- Test: `luci-app-daede/tests/managed-subscription/test-state.js`

- [ ] Write failing tests for:
  - Existing airport records without `kind` normalize to `static_yaml`.
  - Managed records normalize interval presets and custom values to `1..720`.
  - Default interval is `24`; automatic update defaults off.
  - Due-time calculation uses `last_success`, then treats never-successful enabled records as due.
  - Redacted records never expose URL, token, username, or password.
- [ ] Run `node luci-app-daede/tests/managed-subscription/test-state.js` and verify the missing API failures.
- [ ] Implement pure helpers:

```javascript
normalizeKind(record)
normalizeInterval(value)
isDue(record, nowSeconds)
redactManagedRecord(record)
```

- [ ] Run the state tests and existing airport helper tests.
- [ ] Commit only the state helper and its tests.

## Task 2: Add Backend YAML Parsing And Node Conversion

**Files:**
- Create: `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.lua`
- Create: `luci-app-daede/tests/managed-subscription/fixtures/mixed.yaml`
- Create: `luci-app-daede/tests/managed-subscription/test-conversion.sh`
- Modify: `luci-app-daede/Makefile`

- [ ] Add `+yq +lua` package dependencies in `Makefile`.
- [ ] Write a failing shell test that passes `mixed.yaml` through `yq -o=json` and expects Lua conversion output containing compatible `ss`, `ssr`, `vmess`, `vless`, `trojan`, `tuic`, `hysteria2`, and `anytls` links.
- [ ] Include metadata pseudo-nodes and unsupported protocols in the fixture; assert they are counted but excluded.
- [ ] Implement Lua equivalents of the existing `clash-converter.js` conversion rules.
- [ ] Make the Lua command emit structured JSON:

```json
{
  "detected": 10,
  "compatible": 8,
  "ignored_info": 1,
  "unsupported": 1,
  "nodes": [{ "name": "...", "type": "ss", "link": "ss://..." }]
}
```

- [ ] Run browser converter and Lua converter against the same fixture; assert normalized links match.
- [ ] Commit parser/converter support separately.

## Task 3: Implement Secret Storage And Backend Command Contract

**Files:**
- Create: `luci-app-daede/root/etc/config/daede_secrets`
- Create: `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.sh`
- Modify: `luci-app-daede/root/etc/uci-defaults/90-luci-app-daede-init`
- Modify: `luci-app-daede/Makefile`
- Test: `luci-app-daede/tests/managed-subscription/test-secrets.sh`

- [ ] Write failing tests proving:
  - Source URL is stored only in `daede_secrets`.
  - `list-redacted` output contains no URL token or password.
  - Secret configuration mode is `0600`.
  - Invalid airport IDs, backends, User-Agents, and intervals are rejected.
- [ ] Implement commands:

```text
save <airport-id>       Read a JSON request from stdin and persist state/secrets.
list-redacted           Emit safe JSON for LuCI.
credentials-set         Read daed credentials from stdin.
credentials-status      Return only whether credentials exist.
```

- [ ] Ensure command output is structured JSON and errors go to stderr with nonzero exit status.
- [ ] Add `/etc/config/daede_secrets` as a conffile and enforce `0600` in installation defaults.
- [ ] Run tests and verify no command prints secret values.
- [ ] Commit secret storage and command contract.

## Task 4: Move dae Synchronization Into The Backend

**Files:**
- Create: `luci-app-daede/root/usr/share/luci-app-daede/managed-dae.lua`
- Modify: `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.lua`
- Test: `luci-app-daede/tests/managed-subscription/test-dae-sync.sh`

- [ ] Write failing fixture-driven tests for:
  - First synchronization creates managed nodes and one group.
  - Refresh stages the replacement and removes stale owned nodes only after generation succeeds.
  - Generator failure restores the prior UCI snapshot.
  - Unmanaged nodes/groups and nodes referenced by another group remain untouched.
- [ ] Implement dae staging using stable airport-owned UCI section IDs and a restorable snapshot.
- [ ] Invoke `gen-dae-config.sh generate`; only persist new ownership after success.
- [ ] Record `last_attempt`, `last_success`, `last_result`, `last_error`, and node count.
- [ ] Run dae sync and full generator regression tests.
- [ ] Commit dae backend synchronization.

## Task 5: Move daed Synchronization Into The Backend

**Files:**
- Create: `luci-app-daede/root/usr/share/luci-app-daede/managed-daed.lua`
- Modify: `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.lua`
- Test: `luci-app-daede/tests/managed-subscription/test-daed-sync.lua`

- [ ] Write failing tests with a fake GraphQL transport for:
  - Authentication failure preserves the old airport.
  - First sync imports nodes, creates a group, and records ownership.
  - Refresh makes the new group usable before removing stale membership.
  - Shared nodes are never globally deleted.
  - Cleanup failure records a warning while keeping the usable replacement.
- [ ] Implement GraphQL operations equivalent to the current browser implementation:

```text
token
nodes/groups query
importNodes
createGroup / renameGroup / groupSetPolicy
groupAddNodes / groupDelNodes
removeNodes / removeGroup
```

- [ ] Load credentials only from `daede_secrets`; clear in-memory password references after use.
- [ ] Persist new ownership only after the replacement group is usable.
- [ ] Run fake transport tests.
- [ ] Commit daed backend synchronization.

## Task 6: Add Sync, Scheduling, Locking, And Delete Commands

**Files:**
- Modify: `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.sh`
- Modify: `luci-app-daede/root/usr/share/luci-app-daede/managed-subscription.lua`
- Create: `luci-app-daede/root/etc/init.d/daede-managed-subscriptions`
- Create: `luci-app-daede/root/etc/cron.d/daede-managed-subscriptions`
- Modify: `luci-app-daede/Makefile`
- Test: `luci-app-daede/tests/managed-subscription/test-scheduler.sh`

- [ ] Write failing tests for:
  - `sync <id>` fetches and synchronizes one managed URL.
  - `sync-due` skips disabled and not-yet-due records.
  - A per-airport lock prevents concurrent updates.
  - Fetch, parse, and empty-compatible-set failures retain old state.
  - `delete <id> keep` removes management/secrets but keeps backend objects.
  - `delete <id> purge` removes only safely owned backend objects.
- [ ] Implement the command paths and explicit exit codes.
- [ ] Add one periodic cron checker, not one cron entry per airport.
- [ ] Add an init service that sleeps approximately 120 seconds, then runs `sync-due`.
- [ ] Ensure boot, cron, and manual sync share the same lock.
- [ ] Run scheduler and deletion tests.
- [ ] Commit scheduling and lifecycle support.

## Task 7: Expose A Safe LuCI Backend API

**Files:**
- Modify: `luci-app-daede/root/usr/share/rpcd/acl.d/luci-app-daede.json`
- Modify: `luci-app-daede/htdocs/luci-static/resources/view/daede/managed-subscriptions.js`
- Test: `luci-app-daede/tests/managed-subscription/test-acl.sh`

- [ ] Write failing ACL tests proving LuCI may execute only the explicit managed-subscription commands and cannot read `/etc/config/daede_secrets`.
- [ ] Add explicit ACL entries for redacted list, save, sync, delete, credential status, and credential update commands.
- [ ] Implement browser wrappers that pass JSON via safe temporary files or stdin-capable RPC without putting secrets in command arguments.
- [ ] Verify source URL and passwords do not appear in process arguments, page data, or redacted output.
- [ ] Commit the safe LuCI API.

## Task 8: Split Step Three By Source Kind

**Files:**
- Modify: `luci-app-daede/htdocs/luci-static/resources/view/daede/converter.js`
- Modify: `luci-app-daede/htdocs/luci-static/resources/view/daede/styles.js`
- Modify: `luci-app-daede/po/templates/daede.pot`
- Modify: `luci-app-daede/po/zh-cn/daede.po`
- Modify: `luci-app-daede/po/zh_Hans/daede.po`

- [ ] Write a failing DOM/Playwright test asserting URL parsing shows `保存托管订阅`, while pasted YAML shows `导入静态节点`.
- [ ] For URL sources, show airport name, backend, automatic update switch, interval presets `24/36/48/72`, custom hours, saved-credential state, and `保存并立即同步`.
- [ ] Make URL-managed save/sync always use every compatible node, ignoring preview checkbox selections.
- [ ] Keep pasted YAML on the existing selected-node static snapshot path.
- [ ] Validate custom intervals from `1..720` and require daed credentials before enabling automatic updates.
- [ ] Add complete Chinese translations.
- [ ] Verify desktop and 375-pixel layouts under Argon and Bootstrap light/dark themes.
- [ ] Commit dynamic step-three behavior.

## Task 9: Add Managed Subscription List

**Files:**
- Modify: `luci-app-daede/htdocs/luci-static/resources/view/daede/converter.js`
- Modify: `luci-app-daede/htdocs/luci-static/resources/view/daede/styles.js`
- Modify: translation files listed in Task 8

- [ ] Write a failing UI test for managed subscription rows and action states.
- [ ] Render the list above converter input, showing name, backend, automatic interval, last success, node count, and latest result.
- [ ] Add `立即更新`, `编辑`, and `删除`.
- [ ] Make delete present two explicit choices: keep backend objects or purge safely owned objects.
- [ ] Display fetch, YAML, compatibility, authentication, synchronization, and cleanup-warning errors without exposing secrets.
- [ ] Verify long Chinese errors wrap without horizontal overflow.
- [ ] Commit managed-subscription management UI.

## Task 10: Migrate, Package, Deploy, And Verify

**Files:**
- Modify: `luci-app-daede/root/etc/uci-defaults/90-luci-app-daede-init`
- Modify: `luci-app-daede/Makefile`
- Test: all tests above plus device 252

- [ ] Migrate existing airport records without `kind` to static behavior without modifying their nodes or groups.
- [ ] Confirm existing URL-created airports are not silently promoted because their source URLs were never stored.
- [ ] Bump `PKG_RELEASE`.
- [ ] Run:

```sh
node luci-app-daede/tests/managed-subscription/test-state.js
for t in luci-app-daede/tests/managed-subscription/test-*.sh; do sh "$t"; done
msgfmt --check -o /dev/null luci-app-daede/po/zh-cn/daede.po
msgfmt --check -o /dev/null luci-app-daede/po/zh_Hans/daede.po
git diff --check
```

- [ ] Deploy to 252 and verify:
  - Managed URL first sync and manual refresh for dae.
  - Managed URL first sync and manual refresh for daed.
  - Saved daed credentials are not displayed.
  - An induced fetch or parse failure retains old nodes.
  - Cron due refresh works.
  - Boot recovery waits about two minutes and refreshes overdue subscriptions.
  - Static pasted YAML still imports only selected nodes.
  - Keep and purge deletion behave safely.
- [ ] Run the Argon/Bootstrap light/dark desktop/mobile screenshot matrix.
- [ ] Restore 252's original theme and service state.
- [ ] Review the complete diff against the design specification before any release commit or push.
