# Roadmap

Built for short projects and deviation investigations: a handful to a few
hundred events over hours to months, edited by one person, pasted into a
report or slide. Features are judged against that; anything that makes the
page busier needs a strong reason.

## Done

### Unreleased (22 Nov 2026)
- Compress gaps: optional toggle, zig-zag break with the quiet time, × opens one gap
- Table scope: linked to view / all events
- Dependencies: flag (⚠, Check column, tooltip), never move; instructions in app and README

### v1.1.0 (17 Nov 2026) - investigation features
Chosen after comparing with vis-timeline, Office Timeline and the event
timelines in root-cause-analysis tools (see `docs/DESIGN.md`, *Comparison*).
- Time of day on start and end (`2026-11-03 09:15`); zoom down to 1 day with hour ticks
- Gap column: time since the previous event; band length in tooltips
- Key events (star in the table, diamond on the timeline)
- Today line
- Filters: hide classes, pick a timeline, search text
- Optional CSV columns `id`, `timeline`, `owner`, `source`, `depends_on`, `key` (read, kept, written only when used)
- Undo (last 10 changes, including Clear all and deletes)
- Fit all; Copy PNG to the clipboard
- Code split: `figure.py` holds drawing; table-edit logic moved into tested functions

### v1.0.0 (14 Nov 2026)
- Python (Dash) base, web single file, Windows exe via GitHub Actions
- Events table, single-date events and bands, CSV/Excel in, CSV out, PNG capture
- Zoom 1 week to 6 months, table filtered to the view, data kept until cleared
- Tests on every push, including a web/Python parity check

## Feedback log
- 21 Nov 2026 (partner): table hid events outside the view; linked events were expected to move. Both addressed (see Done).
- 22 Nov 2026 (partner): works well; copy-paste easy; style good. Long quiet stretches blocked use (tester switched to a
  hand-drawn timeline) - built *Compress gaps*. Dependencies should *flag*, not move: *"I would prefer that it flags
  when a dependency happens after a due date, and not that it automatically pushes the date, since this might cause
  problems where items move unexpectedly."* Built as flag-only.
- Open question: "due" = the predecessor's end date (its date if it has no end). Revisit if it causes problems in use.
- Boss feedback: not waited for; add here if it comes.

## Must do before raising `dash<5`
- Replace Dash `DataTable` (deprecated; bug #4). Candidate: `dash-ag-grid`;
  check it keeps Tab focus, paste and undo.

## Next (pick in order)
1. **Swimlanes**: draw each `timeline` in its own horizontal strip (the column and the picker already exist)
2. **Measure**: click two events to show the elapsed time between them on the picture
3. **Overlap/clash view** between timelines
4. **Report export**: picture plus table as one printable page
5. **Excel loading in the web version** (needs an unzip step; check it can stay library-free)

## Later / ideas
- Keyboard shortcuts (arrows to scroll, +/- to zoom)
- Wheel-to-scroll option
- An event at exactly 00:00 (today midnight means "no time given")
- Python version: redraw while dragging
- Share a timeline as a link. Security: the data would sit in the link itself, so only for non-confidential timelines; needs a design note first

## Decided against (for now)
- Accounts, server storage, live collaboration: the tool is single-user and local on purpose
- Percent-complete, resources, critical path: that is a project-planning tool, not a timeline

Reasons for past choices are in `docs/DESIGN.md` (Decisions). Bugs are in `BUGS.md`.
