# Timeline Visualiser

A small Python app that turns a table of dated events into a side-scrolling
timeline. Each event has a **class** (bold title), a **date** and a short
**description**; the line linking it to its date is coloured by class.

![Example capture](docs/example_capture.png)

## Run it

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050. The app starts with `sample_events.csv`;
press **Clear all** to start empty.

## Use it

| To do this | Do this |
|---|---|
| Scroll through time | Drag the timeline left/right, or use ◀ ▶ |
| Zoom | Zoom buttons (1 week to 6 months) or the mouse wheel; default is 1 month |
| Add an event | **Add row**, then type in the table |
| Paste events | Open *Paste rows from Excel or CSV*, paste, **Add pasted rows** |
| Load a file | **Load CSV / Excel** (adds to what is there; exact duplicates are skipped) |
| Save the data | **Download CSV** (all events, in date order) |
| Save a picture | **Capture PNG** (the timeline as shown, at 2x resolution) |
| Hide a panel | Untick **Timeline** or **Table** |

The table always sorts by date and only lists events inside the visible date
range, so an event whose date you change to outside the range leaves the table
(scroll there to see it again).

## Data format

```
date,class,description
2026-11-06,Results,Buffer recirculation data expected
```

- Dates: `YYYY-MM-DD` preferred. `10-Mar-2025`, `10.03.2025`, `10/03/2025`
  (day first) and `10-Mar` (current year) are also read.
- Header names `title`, `type` or `category` are accepted for `class`.
- Two columns are read as date + `Class: description`.
- Comma, semicolon or tab separated. Excel: first sheet, same columns.

## Files

| File | What it holds |
|---|---|
| `app.py` | The web page and its callbacks (Dash) |
| `timeline.py` | Data cleaning, label layout and figure drawing; no web code |
| `tests/test_timeline.py` | Unit tests: `python -m pytest` |
| `docs/DESIGN.md` | Requirements, design decisions, known limits |
| `sample_events.csv` | Made-up example data and CSV template |
