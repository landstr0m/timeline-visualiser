# Roadmap

## Done (v1.0.0, 14 Nov 2026)
- Python (Dash) base, web single file, Windows exe via GitHub Actions
- Events table, single-date events and bands, CSV/Excel in, CSV out, PNG capture
- Zoom 1 week to 6 months, table filtered to the view, data kept until cleared
- Tests on every push, including a web/Python parity check

## Next (pick in order)
1. Optional CSV columns `id`, `timeline`, `owner`, `source`, `depends_on` (read, kept, written; see `docs/DESIGN.md`)
2. Several named timelines (uses `timeline`)
3. Per-class show/hide
4. Dependencies: moving an event shifts its dependants by the same duration
5. Overlap/clash view between timelines
6. Wheel-to-scroll option

## Later / ideas
- Time-of-day events
- Excel loading in the web version

Reasons for past choices are in `docs/DESIGN.md` (Decisions). Bugs are in `BUGS.md`.
