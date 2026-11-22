# Changelog

## Unreleased
- **Compress gaps** toggle: long stretches with no activity are cut from the axis, marked and labelled; open one gap with its × (partner feedback 22 Nov)
- Exe built from `requirements-lock.txt` (exact versions)
- Notes: DataTable deprecation (bug #4), partner feedback in roadmap

## v1.1.1 - 2026-11-21 (build fix)
- Windows exe build fixed: the web/Python parity test now talks to Node in UTF-8 (bug #3)
- Exe build also runs when tests change

## v1.1.0 - 2026-11-17 (investigation features)
- Time of day on events and bands; zoom to 1 day with hour ticks
- Gap column (time since the previous event), band length in tooltips
- Key events, Today line, Fit all, Copy PNG
- Filters: hide classes, pick a timeline, search
- Optional CSV columns: `id`, `timeline`, `owner`, `source`, `depends_on`, `key`
- Undo for the last 10 changes
- Drawing moved to `figure.py`; table-edit and merge logic moved into `timeline.py` with tests; 35 tests (was 10)
- Fix: web table lost keyboard focus after every edit (bug 2)
- Changed: minimum zoom is 1 day (was 1 week); sample data has times, owners and key events

## v1.0.0 - 2026-11-14 ("done for now")
- Python, web and Windows exe versions with all requirements in `docs/DESIGN.md`
- Tests on every push, including a web/Python parity check; ruff formatter and lint
- Roadmap, bug log, MIT licence
- Fix: CSV download uses the same line endings on every system (bug 1)
