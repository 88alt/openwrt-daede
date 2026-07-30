# Editor Overlay Alignment

## Goal

Fix Issue #44's manual editor caret misalignment without removing syntax highlighting or adding an editor dependency.

## Root Cause

The editor overlays a transparent `textarea` on a syntax-highlighted `pre`. Soft wrapping, token bold/italic styles, and browser scrollbar width make the two layers use different glyph and line metrics. Once a long line wraps at a different position, the visible text and native caret diverge.

## Design

- Set the `textarea` to `wrap="off"`.
- Use `white-space: pre` and `word-break: normal` for both layers.
- Keep syntax colors, but remove token bold and italic styles so highlighting cannot change glyph width.
- Keep the existing horizontal and vertical scroll synchronization.
- Do not introduce CodeMirror or another dependency.
- Do not change the editor's save, validation, hot-reload, or placeholder behavior.

Long lines will use horizontal scrolling on desktop and mobile. This trade-off is explicitly accepted because accurate caret placement is more important than soft wrapping for configuration editing.

## Files

- `luci-app-daede/htdocs/luci-static/resources/view/daede/dae.js`
- `luci-app-daede/htdocs/luci-static/resources/view/daede/styles.js`
- `luci-app-daede/Makefile`

## Verification

- Run JavaScript syntax checks.
- Verify the supplied Issue #44 configuration at desktop and mobile viewport widths.
- Confirm that long lines do not wrap and horizontal scrolling keeps both layers aligned.
- Insert text before and after highlighted tokens and confirm the native caret matches the visible text.
- Run `git diff --check`.

## Release

This is a small LuCI-only fix, so bump `luci-app-daede` from `1.14.7-r19` to `1.14.7-r20`.
