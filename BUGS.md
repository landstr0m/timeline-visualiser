# Bug log

One row per bug, newest first. Keep fixed rows; they show what has been tested.

| # | Found | Version | What happens | Steps to reproduce | Status | Fixed in |
|---|---|---|---|---|---|---|
| 1 | 2026-11-14 | Python / exe on Windows | Download CSV used Windows line endings (CRLF); web used LF, so files differed by version | Run `tests/test_web.py` on Windows (exe build workflow) | Fixed: `to_csv` always writes `\n` | v1.0.0 |

Design limits that are known and accepted (not bugs) are listed in
`docs/DESIGN.md` under *Known limits*.
