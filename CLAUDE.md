# Timeline Visualiser - project notes for Claude

## What this is
A side-scrolling event timeline with an events table, CSV in/out and PNG
capture. Three deliverables share one behaviour:

1. **Python** (`app.py` + `timeline.py` + `figure.py`, Dash/Plotly) - the base version.
2. **Web** (`web/index.html`) - one self-contained file, vanilla JS + SVG.
3. **Windows exe** - the Python version frozen by PyInstaller in
   `.github/workflows/build-exe.yml`. Never commit binaries.

## Commands
- Run: `python app.py` (http://127.0.0.1:8050)
- Test: `python -m pytest -q` (includes the web/Python parity check; needs Node)
- Format/lint: `ruff format .` and `ruff check .` (CI fails if not clean)
- Web: open `web/index.html` directly; no build step.

## Standards
- Few, simple files. Do not add a file, framework or dependency without need.
- `timeline.py` holds all logic as plain functions with no web or plotting
  code; `figure.py` only draws; `app.py` only wires the page. New logic gets a
  unit test and, if the web version has the same function, a line in the
  parity harness in `tests/test_web.py`.
- In `web/index.html`, pure functions go above the `state` heading (Node runs
  that part in the tests); anything touching the page goes below it.
- The web version uses no libraries and makes no network requests, so it works
  offline and inside locked-down or embedded pages.
- **Keep the versions in step.** A behaviour change goes into `timeline.py`
  and `web/index.html` together (same function names in camelCase, same
  constants: palette, zoom limits, label levels, CSV aliases). The sample in
  `web/index.html` must equal `sample_events.csv`.
- CSV format `date,end,class,description` (+ optional `id`, `timeline`,
  `owner`, `source`, `depends_on`, `key`) is the contract between versions.
  Never break reading of older 3- or 4-column files; optional columns are
  written only when used.
- Dates are text, `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`; they sort as text.
- Every change to the events goes through one place (`update_rows` /
  `change()`), which is what makes Undo work. Filters never change stored data.
- Text from files goes into the page through `esc()` (web) or Dash props
  (Python), never as raw HTML.
- Colour follows the class name across the whole data set; classes past the
  8th share neutral grey. Label text stays dark; only lines/bands carry colour.
- Sample data must be invented. Never commit real workplace or client data,
  including in screenshots.
- Update `README.md`, `docs/DESIGN.md` and `ROADMAP.md` in the same commit as the change; log bugs in `BUGS.md`.

## Verifying a change
1. `python -m pytest -q`.
2. Run the Python app and the web page in a browser; exercise drag, zoom,
   table edit (Tab must keep focus), star, filters, undo, paste, download,
   capture, reload (data must persist) and Clear all (must stay empty after
   reload).
3. Look at a captured PNG at 1 day, 1 week, 1 month and 6 months, and at phone width.
4. The exe cannot be built off Windows: check the GitHub Actions run.

## Known limits / ideas
Limits: `docs/DESIGN.md`. Plans: `ROADMAP.md`. Bugs: `BUGS.md`.
