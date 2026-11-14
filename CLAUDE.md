# Timeline Visualiser - project notes for Claude

## What this is
A side-scrolling event timeline with an events table, CSV in/out and PNG
capture. Three deliverables share one behaviour:

1. **Python** (`app.py` + `timeline.py`, Dash/Plotly) - the base version.
2. **Web** (`web/index.html`) - one self-contained file, vanilla JS + SVG.
3. **Windows exe** - the Python version frozen by PyInstaller in
   `.github/workflows/build-exe.yml`. Never commit binaries.

## Commands
- Run: `python app.py` (http://127.0.0.1:8050)
- Test: `python -m pytest -q` (includes the web/Python parity check; needs Node)
- Web: open `web/index.html` directly; no build step.

## Standards
- Few, simple files. Do not add a file, framework or dependency without need.
- `timeline.py` holds all logic as plain functions with no web code; `app.py`
  only wires the page. New logic gets a unit test.
- The web version uses no libraries and makes no network requests, so it works
  offline and inside locked-down or embedded pages.
- **Keep the versions in step.** A behaviour change goes into `timeline.py`
  and `web/index.html` together (same function names in camelCase, same
  constants: palette, zoom limits, label levels, CSV aliases).
- CSV format `date,end,class,description` is the contract between versions.
  Never break reading of older 3-column files.
- Colour follows the class name across the whole data set; classes past the
  8th share neutral grey. Label text stays dark; only lines/bands carry colour.
- Sample data must be invented. Never commit real workplace or client data,
  including in screenshots.
- Update `README.md`, `docs/DESIGN.md` and `ROADMAP.md` in the same commit as the change; log bugs in `BUGS.md`.

## Verifying a change
1. `python -m pytest -q`.
2. Run the Python app and the web page in a browser; exercise drag, zoom,
   table edit, paste, download, capture, reload (data must persist) and
   Clear all (must stay empty after reload).
3. Look at a captured PNG at 1 week, 1 month and 6 months, and at phone width.
4. The exe cannot be built off Windows: check the GitHub Actions run.

## Known limits / ideas
Limits: `docs/DESIGN.md`. Plans: `ROADMAP.md`. Bugs: `BUGS.md`.
