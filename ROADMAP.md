# Roadmap

Built for short projects and deviation investigations: a handful to a few
hundred events over hours to months, edited by one person, pasted into a
report or slide. Features are judged against that; anything that makes the
page busier needs a strong reason.

## Done

### Unreleased (22 Nov 2026)
- Compress gaps: optional toggle, zig-zag break with the quiet time, × opens one gap

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

## Feedback to sort (21 Nov 2026, partner; boss feedback due next week)
Rank these together with the next round of feedback before building.
- **Table scope toggle**: the table only lists events in the current view
  (a design choice), which hid events. Add a toggle: *All events* / *Linked to view*.
- **Dependencies**: users expected linked events to move together. This is not
  built yet (item 3 below), so it read as broken. Needed: (a) clear
  instructions in the app and README on setting `id` and `depends_on`;
  (b) ~~when an event's date changes, its dependants move by the same amount~~
  superseded 22 Nov, see below.

## Feedback to sort (22 Nov 2026, partner)
Liked: the app generally works well; copy-paste of activities was easy and the
rows were ready in the table at once; the style is already good.
- **Dependencies: flag, never move** (replaces 21 Nov item (b) and changes
  Next item 3). Quote: *"I would prefer that it flags when a dependency happens
  after a due date, and not that it automatically pushes the date, since this
  might cause problems where items move unexpectedly."* So: dates only change
  when the user edits them; an event that starts before something it depends
  on has finished is marked (table row and timeline) with the reason in the
  tooltip. "Due" = the predecessor's end date (its single date if it has no
  end). Keep this question open: revisit if it causes problems in use.
- **Compressed time axis**: built 22 Nov (see Done). It was the blocker that
  made the tester stop using the tool for a hand-drawn timeline. Decisions:
  gap threshold 30% of the view (follows zoom); band starts/ends are activity,
  band middles are compressed; never before the first or after the last event;
  breaks always shown in the PNG. Rules in `docs/DESIGN.md`.

## Must do before raising `dash<5`
- Replace Dash `DataTable` (deprecated; bug #4). Candidate: `dash-ag-grid`;
  check it keeps Tab focus, paste and undo.

## Next (pick in order)
1. **Swimlanes**: draw each `timeline` in its own horizontal strip (the column and the picker already exist)
2. **Measure**: click two events to show the elapsed time between them on the picture
3. **Dependencies**: flag an event that starts before an event it depends on is due; never move dates automatically (`id` and `depends_on` are already stored; changed 22 Nov after feedback)
4. **Overlap/clash view** between timelines
5. **Report export**: picture plus table as one printable page
6. **Excel loading in the web version** (needs an unzip step; check it can stay library-free)

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
