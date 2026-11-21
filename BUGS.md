# Bug log

One row per bug, newest first. Keep fixed rows; they show what has been tested.

| # | Found | Version | What happens | Steps to reproduce | Status | Fixed in |
|---|---|---|---|---|---|---|
| 4 | 2026-11-21 | Python / exe | Warning: Dash `DataTable` will be removed in a future major version (shown in every test run) | `python -m pytest -q`, see warnings summary | Open: held off by `dash<5`; replace before raising that limit (roadmap) | |
| 3 | 2026-11-21 | Exe build on Windows | Build failed: 10 web/Python parity tests saw garbled `·`, `–`, `★` | Run `tests/test_web.py` on Windows (exe build workflow) | Fixed: the Node call in the test now reads and writes UTF-8 instead of the Windows default (cp1252); test-only, app unaffected. Build also re-runs when tests change | v1.1.1 |
| 2 | 2026-11-17 | Web | After editing a table cell and pressing Tab, keyboard focus was lost because the table is rebuilt | Edit a class, press Tab, type | Fixed: focus is put back on the box the user moved to (browser check, see `CLAUDE.md` step 2) | v1.1.0 |
| 1 | 2026-11-14 | Python / exe on Windows | Download CSV used Windows line endings (CRLF); web used LF, so files differed by version | Run `tests/test_web.py` on Windows (exe build workflow) | Fixed: `to_csv` always writes `\n` | v1.0.0 |

Design limits that are known and accepted (not bugs) are listed in
`docs/DESIGN.md` under *Known limits*.
