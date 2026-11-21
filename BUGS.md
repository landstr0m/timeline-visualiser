# Bug log

One row per bug, newest first. Keep fixed rows; they show what has been tested.

| # | Found | Version | What happens | Steps to reproduce | Status | Fixed in |
|---|---|---|---|---|---|---|
| 4 | 2026-11-21 | Python (seen at 127.0.0.1:8050); web not checked | When a band's start is scrolled off the left edge, its label does not move across to the view edge, so the name is off-screen. Expected: label always drawn at `max(band start, view start)` and truncated (e.g. with "…") so it never runs past the band's end. Confirmed not just the known limit "re-anchors when a drag is released" (`docs/DESIGN.md`): the label stays off-screen after the drag is released, and the band shows with no name | Load sample, drag until a band's start is off-screen, release; the band has no label | Open | |
| 3 | 2026-11-21 | Exe build on Windows | Build failed: 10 web/Python parity tests saw garbled `·`, `–`, `★` | Run `tests/test_web.py` on Windows (exe build workflow) | Fixed: the Node call in the test now reads and writes UTF-8 instead of the Windows default (cp1252); test-only, app unaffected. Build also re-runs when tests change | v1.1.1 |
| 2 | 2026-11-17 | Web | After editing a table cell and pressing Tab, keyboard focus was lost because the table is rebuilt | Edit a class, press Tab, type | Fixed: focus is put back on the box the user moved to (browser check, see `CLAUDE.md` step 2) | v1.1.0 |
| 1 | 2026-11-14 | Python / exe on Windows | Download CSV used Windows line endings (CRLF); web used LF, so files differed by version | Run `tests/test_web.py` on Windows (exe build workflow) | Fixed: `to_csv` always writes `\n` | v1.0.0 |

Design limits that are known and accepted (not bugs) are listed in
`docs/DESIGN.md` under *Known limits*.
