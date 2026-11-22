# Timeline Visualiser - design

## Requirements and where they are met

| # | Requirement | Where |
|---|---|---|
| 1 | Side-scroll a timeline with the mouse | Plotly pan mode; `update_view` in `app.py` |
| 2 | Events held in a separate table: class, date, description | `rows` store + DataTable |
| 3 | Lines link each event to its date, coloured by class | `build_figure`, `class_colours` |
| 4 | Manual entry, copy-paste, or CSV/Excel load | `update_rows`, `rows_from_text`, `rows_from_excel` |
| 5 | Download the structured CSV | `download_csv`, `to_csv` |
| 6 | One month by default; zoom from one week to six months | `default_view`, `clamp_view` |
| 7 | Text stays legible at every zoom | `layout_labels` |
| 8 | Rows auto-sort chronologically | `sort_rows`, applied on every change |
| 9 | Table lists only events in the visible range | `in_view`, applied in `render` |
| 10 | Timeline and table can each be hidden | `show` checklist |
| 11 | Capture button makes a static PNG | browser-side `Plotly.downloadImage` |
| 12 | Bands: events with start and end date, labelled at start or earliest visible date | `layout_bands`, `build_figure` |
| 13 | Events with only a start date display as before | `layout_labels` |
| 14 | Web version that can be embedded | `web/index.html` |
| 15 | Windows executable from the Python version | `.github/workflows/build-exe.yml` |
| 16 | Data persists until cleared, with option to save | local storage (`rows`, `view` stores); Download CSV |
| 17 | Time of day on events; zoom to one day | `parse_when`, `when_num`, `tick_step` |
| 18 | Elapsed time between events | `span_text`, `with_gaps` (Gap column), `tip_lines` |
| 19 | Key events stand out | `key` field; `label_head`; diamond marker in `figure.py` |
| 20 | Today line | `_today` in `figure.py` |
| 21 | Hide classes, pick a timeline, search | `filter_rows`, `timelines` |
| 22 | Optional columns for owner, source, timeline, id, depends_on | `EXTRAS`, `to_csv`, `rows_from_frame` |
| 23 | Undo | `undo` store in `update_rows`; `change()` in the web version |
| 24 | Fit all events in view | `fit_span`, `fit_view` |
| 25 | Copy the picture to the clipboard | browser-side snippet in `app.py`; `toPng` in the web version |
| 27 | Table lists events in view or all events | *scope* picker; `render` / `draw` |
| 28 | Flag dependency problems, never move dates | `dependency_issues`, `flag_rows`, `band_name`; Check column |
| 26 | Compress long quiet stretches (toggle, per-gap expand) | `find_breaks`, `squash`, `unsquash`, `break_text`; Plotly `rangebreaks` + `_breaks` in `figure.py` |

Function names above are the Python ones; `web/index.html` has the same
functions in camelCase.

## Comparison with similar tools (Nov 2026)

What comparable tools offer, and what was taken from each for short projects
and deviation investigations:

| Tool type | Examples | Taken | Left out, and why |
|---|---|---|---|
| Timeline components | vis-timeline | Time of day, today line, fit, groups (as the `timeline` filter; swimlanes are next on the roadmap) | Drag-to-edit items: easy to move an event by accident in an investigation record |
| Presentation timelines | Office Timeline | Milestone (key) markers, today line, copy into a document | Percent complete, templates and themes: clutter for this use |
| Root-cause-analysis event timelines | GE APM, Causelink | Marking key/contributing events, source of each fact, exact sequence in hours and minutes, elapsed time | Cause trees and action tracking: belongs in the quality system |
| Story timelines | TimelineJS | Nothing | Media slides; not a working tool |

Kept deliberately: no server, no accounts, one file for the web version.

## How it fits together

Two pieces of state live in the browser: `rows` (every event) and `view` (the
visible date range). Three callbacks do all the work:

    user action -> update_view -> view --\
    user action -> update_rows -> rows ---+-> render -> figure + filtered table

`render` is the only place that draws, so the timeline and the table can never
disagree. All logic is in `timeline.py` as plain functions and is unit tested;
`figure.py` turns its results into a Plotly figure.

A third store, `undo`, holds up to 10 earlier versions of `rows`. Every data
change passes through `update_rows`, which pushes the previous rows before
returning the new ones. Filters (search, hidden classes, timeline) are inputs
to `render` only: they never change `rows`, and Download CSV always writes
everything.

## Dates and times

A moment is text: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`. Text in that form sorts
chronologically, reads back unchanged from CSV, and needs no time-zone
handling. For arithmetic it becomes a day number with a fraction for the time
(`when_num`). An event without a time sits on the midnight tick of its day
and counts as visible whenever any part of that day is in view; an event with
a time is a point. Elapsed time is given in hours and minutes only when both
ends have a time, otherwise in whole days.

Axis ticks follow the zoom (`tick_step`): hours (every 1, 2, 3, 6 or 12) when
there is room, then days, weeks, months.

## Label layout (requirement 7)

1. Each label sits to the right of its date line. Its width is estimated from
   its longest line of text and converted to days using the measured screen
   width.
2. Events are taken in date order. Each goes in the lowest lane whose previous
   label has already ended, so labels never overlap.
3. If that needs more than 5 lanes, the text is shortened and step 2 repeated:
   full description (2 lines) -> one truncated line -> class only.
4. When there is no room for a tick on every day, the date is added to each
   label and the axis switches to weekly, then monthly ticks.
5. The figure grows taller if even class-only labels need more lanes.

Labels have a white background, so a line running up to a higher label passes
behind lower ones rather than through their text.

## Bands (requirement 12)

Bands sit in their own strip above the single-date labels, so date lines never
cross them. Each takes the lowest lane that is free from its start date; a
lane stays busy until both the band and its label have ended. The label is
placed at `max(band start, view start)`, never past the band's end.

## Compressed gaps (requirement 26, partner feedback 22 Nov 2026)

- **Activity** is every event date and every band start and end. The middle of
  a band is not activity, so a long band is shortened along with the gap.
- **A gap is cut** when it is at least `GAP_SHARE` (30%) of the visible span.
  `PAD_SHARE` (5% of the span) stays visible on each side; the left side also
  keeps room for the label of a band starting there, so it stays readable.
  Gaps only fall between two moments of activity, so nothing is cut before the
  first event or after the last.
- **Gaps are found over all shown (filtered) events, not only the visible
  ones.** The result is the same as "compress, see what comes into view,
  compress again", but breaks do not appear and vanish while dragging. The
  threshold follows the zoom: at 1 month a 9-day gap is cut, at 6 months it is not.
- **Positions**: `squash` turns a real day number into an axis position by
  removing hidden time; `unsquash` goes back. The view keeps its start as a
  real date and its span in axis days, so zoom levels mean the same screen width.
  Moves (drag, ◀ ▶, zoom, Today) are worked out in axis positions.
- **Drawing**: web draws the cut itself (dotted line, zig-zag, label with ×).
  Python uses Plotly `rangebreaks` to remove the time and `_breaks` for the
  marks. Both are part of the picture, so a PNG can never hide a compression.
- **Labels** show the whole quiet stretch between the two events (what a reader
  wants to know), not only the hidden part.
- Each gap is named by its two edge moments (`key`). Opened gaps are kept in
  memory only; the toggle clears them. The toggle itself is remembered.

## Persistence (requirement 16)

Both versions keep events, visible range and title in the browser's local
storage. The sample loads only when nothing has ever been stored; after
*Clear all* the stored list is empty and stays empty. The exe uses the same
mechanism through the default browser. If storage is blocked (some embedded
pages), the web version still works but forgets on reload.

## Data that may come in twos later

Planned optional CSV columns, so these can be added without breaking older
files (missing column = blank, files without them still load):

| Column | Why |
|---|---|
| `id` | Stable row id, needed for dependencies |
| `timeline` | Several named timelines in one file; also the basis for clash checks between timelines |
| `owner` | Who is responsible for the event |
| `source` | Which file or system the row came from |
| `depends_on` | Ids this event follows; the event is flagged if it starts before one of them is due (its end, else its date) or names a missing id. Dates are never moved automatically: moving linked events surprised testers (feedback 22 Nov 2026) |
| `key` | `yes` marks a key event |

All six are read, kept, editable under *Details* and written back since
v1.1.0. `timeline` drives a filter; `id` and `depends_on` are stored only
(dependencies are on the roadmap). The CSV `id` is held in the row field
`ref`, because `id` is the table's own internal row key.

Overlaps/clashes are worked out from dates and `timeline`, not stored.

## Data: open vs private

Only invented sample data lives in the repo. Real event files stay on the
user's machine or in browser storage. The live page and repo are public.

## Decisions

- **Files over 500 lines kept whole (tidy-up 22 Nov 2026).** `web/index.html`
  (~745), `timeline.py` (~660) and `app.py` (~530) passed 500 lines. The web page
  must stay one file to be embeddable and work offline; `timeline.py` mirrors the
  web page's pure functions name for name, which the parity test relies on.
  Both are split into headed sections instead. The tidy-up removed a repeated
  width sum (`plot_px` in `app.py`) and checked for dead code (none). Revisit if
  a section passes ~200 lines or a third version appears.

- **Exe built from a lock file (v1.1.2).** `requirements-lock.txt` pins every
  package to an exact version, so the same code always gives the same exe.
  The Tests workflow still installs from the ranges in `requirements.txt`, so a
  new library version that breaks something shows up there first.
- **Dash + Plotly.** Pure Python, runs locally, and Plotly gives drag-pan,
  wheel-zoom and PNG export without custom JavaScript (two short browser-side
  snippets: measuring width, and capture).
- **Colour follows the class name**, alphabetically across the whole data set,
  so scrolling never repaints a class. Palette is colour-blind-checked; a 9th
  or later class shares neutral grey rather than reusing a hue.
- **Loading a file adds** to the current events instead of replacing them, so
  manual entries are never lost silently. Use *Clear all* first to replace.
- **An unreadable date typed into the table is rejected** and the previous
  date kept, with a message; unreadable rows in a file are skipped and counted.
- **Times are optional (v1.1).** Dates alone stay the normal case; a time is
  added only where the sequence within a day matters. Midnight means "no
  time", so spreadsheet exports like `2026-11-03 00:00:00` read as plain dates.
- **Filters hide, they never delete.** A hidden class keeps its colour, and
  the download is always complete, so a filtered view cannot lose data.
- **Optional columns are written only when used**, so a file that came in
  with four columns goes out with four.
- **Extra columns and time boxes sit behind *Details*** to keep the default
  table at five columns.
- **Undo instead of "are you sure?"** Confirm boxes get clicked through;
  undo fixes the mistake after it is noticed.
- **Month and weekday names are fixed English** (`MON`, `DOW`), so pictures
  are identical on machines with different regional settings.
- **The web version stays one file** although it is past 600 lines, because
  "send one file to a colleague" is the point of it. Inside, pure functions
  sit above the `state` heading and are run by the tests.
- **Web version has no dependencies** (vanilla JS, SVG, canvas for the PNG) so
  it runs from a file, offline, or inside an iframe on a locked-down page.
- **One test command covers both versions.** `tests/test_web.py` runs the web
  page's pure functions in Node and compares them with `timeline.py`, so the
  versions cannot drift apart unnoticed. It runs on every push.
- **The exe is built by GitHub Actions on Windows**, because PyInstaller can
  only build for the system it runs on. Binaries are not stored in the repo.

## Known limits

- Data is stored per browser and per version; it does not sync between
  devices. Download the CSV to move it.
- Python version: band labels re-anchor to the view edge when a drag is
  released, not during it (the web version does it live).
- Web version reads CSV only, not Excel.
- The exe is about 70 MB, takes a few seconds to start, and uses port 8050.
- Label width is estimated, not measured, so very wide characters can touch a
  neighbouring label.
- The mouse wheel zooms; sideways scrolling is by drag or the arrow buttons.
- An event at exactly 00:00 cannot be entered; use 00:01.
- The Gap column measures from the start of the previous listed row, bands
  included; with a filter on, it measures between the rows still shown.
- Undo history is lost when the page is closed or reloaded.
- Copy PNG needs a browser that allows clipboard pictures; some embedded
  pages block it (Capture PNG still works).
- At day-level zoom a timed event is drawn part-way between two day ticks,
  while the weekend stripe is centred on the ticks; zoom in for exact reading.
- Single user, local use. Not hardened for hosting on a shared server.

## Next steps

See `ROADMAP.md`.
