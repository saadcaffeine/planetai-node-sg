# docs/design

`fixtures/` holds the node captures the dashboard is rendered and tested against. `python3 tools/shots.py` writes its screenshots to `shots/` here, which git ignores.

The design notes that used to sit beside them (the September audit, the UX reviews, LANGUAGE_GAP, the scale spike, the handoffs and prompts) are working records, and they moved on 9 Nov 2026 to the private **`planetai-design`** repo, at `node-docs/design/`, with the audit evidence that went there before them (`design/audit/2026-09/`).

The visual language is not this repo's to edit either. **`planetai-design/planetai-theme.css`** is generated from that repo's `references/planetai-layer.md`, and `app/static/planetai-theme.css` is a byte-for-byte copy of it, held there by `tools/check_theme.py`, which is in `make lint` and fails.
