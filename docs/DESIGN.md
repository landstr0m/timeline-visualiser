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

Function names above are the Python ones; `web/index.html` has the same
functions in camelCase.

## How it fits together

Two pieces of state live in the browser: `rows` (every event) and `view` (the
visible date range). Three callbacks do all the work:

    user action -> update_view -> view --\
    user action -> update_rows -> rows ---+-> render -> figure + filtered table

`render` is the only place that draws, so the timeline and the table can never
disagree. All logic is in `timeline.py` as plain functions and is unit tested.

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

## Persistence (requirement 16)

Both versions keep events, visible range and title in the browser's local
storage. The sample loads only when nothing has ever been stored; after
*Clear all* the stored list is empty and stays empty. The exe uses the same
mechanism through the default browser. If storage is blocked (some embedded
pages), the web version still works but forgets on reload.

## Decisions

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
- **Dates only, no times.** Events sit at the start of their day.
- **Web version has no dependencies** (vanilla JS, SVG, canvas for the PNG) so
  it runs from a file, offline, or inside an iframe on a locked-down page.
- **One test command covers both versions.** `tests/test_web.py` runs the web
  page's data functions in Node and compares them with `timeline.py`, so the
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
- Single user, local use. Not hardened for hosting on a shared server.

## Next steps

See `ROADMAP.md`.
