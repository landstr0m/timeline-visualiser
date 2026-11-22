"""Timeline Visualiser - Dash web app.  Run:  python app.py

This file only wires the page: what is on it, and which function runs when
something is clicked. Logic is in timeline.py, drawing in figure.py.

State lives in browser-side stores:
  rows : every event (the table shows those in view, or all of them)
  view : the visible date range {start, end, n}
  undo : earlier versions of `rows`, newest last (lost when the page closes)
`rows` and `view` are kept in the browser's local storage, so data persists
until cleared. The title, filters and panel ticks persist the same way.

Three callbacks do the work:
  user action -> update_view -> view --\\
  user action -> update_rows -> rows ---+-> render -> figure + filtered table
"""

from __future__ import annotations

import base64
import sys
import threading
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dash import ALL, Dash, Input, Output, State, callback, clientside_callback, ctx, dash_table, dcc, html, no_update

import timeline as tl
from figure import build_figure

# When frozen into an .exe, bundled files are unpacked to sys._MEIPASS.
SAMPLE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "sample_events.csv"
ZOOMS = {"1 day": 1, "1 week": 7, "2 weeks": 14, "1 month": 31, "3 months": 92, "6 months": 184}
UNDO_DEPTH = 10
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def view_dict(start: datetime, end: datetime, n: int = 0, span: float | None = None) -> dict:
    """`span` is the width of the view in days on the axis; with compressed gaps it is less than end - start."""
    span = span if span is not None else (end - start).total_seconds() / 86400
    return {"start": start.isoformat(), "end": end.isoformat(), "n": n, "span": span}


def view_span(view: dict) -> float:
    start, end = view_range(view)
    return view.get("span") or (end - start).total_seconds() / 86400


def kept_rows(rows, hidden, timeline, search) -> list[dict]:
    """Rows left after the filters (a picked timeline that no longer exists is ignored)."""
    rows = rows or []
    timeline = timeline if timeline in tl.timelines(rows) else ""
    return tl.filter_rows(rows, hidden or [], timeline, search or "")


def plot_px(width) -> float:
    """Width of the drawing area in px (the graph minus its side margins), as figure.py uses it."""
    return max((width or 1100) - 60, 200)


def gap_breaks(kept, compress, expanded, span, width) -> list[dict]:
    """The compressed gaps for this view, or none when *Compress gaps* is off."""
    if "Compress gaps" not in (compress or []):
        return []
    drawable = [r for r in kept if r["class"] or r["description"]]
    return tl.find_breaks(drawable, span, plot_px(width) / span, expanded or [])


def view_range(view: dict) -> tuple[datetime, datetime]:
    return datetime.fromisoformat(view["start"]), datetime.fromisoformat(view["end"])


DEP_HINT = (
    "Dependencies: give an event an Id, then put that Id under Depends on for each event that follows it"
    " (several: separate with commas). An event that starts before the one it depends on is due (its end date,"
    " or its date if it has none) is marked ⚠ with the reason. Dates never move by themselves."
)


def table_columns(details: bool, check: bool = False) -> list[dict]:
    """Table columns. The optional ones appear only when *Details* is ticked; Check only when something is flagged."""
    columns = [{"name": "Check", "id": "check", "editable": False}] if check else []
    columns += [
        {"name": "Start (YYYY-MM-DD [HH:MM])", "id": "date"},
        {"name": "End (optional)", "id": "end"},
        {"name": "Gap", "id": "gap", "editable": False},
        {"name": "Class", "id": "class"},
        {"name": "Description", "id": "description"},
    ]
    if details:
        columns += [
            {"name": "Key (yes)", "id": "key"},
            {"name": "Owner", "id": "owner"},
            {"name": "Source", "id": "source"},
            {"name": "Timeline", "id": "timeline"},
            {"name": "Id", "id": "ref"},
            {"name": "Depends on", "id": "depends_on"},
        ]
    return columns


# ------------------------------------------------------------------ page ----
rows0, _ = tl.rows_from_text(SAMPLE.read_text(encoding="utf-8")) if SAMPLE.exists() else ([], 0)
btn = {
    "padding": "6px 10px",
    "border": "1px solid #c9c8c0",
    "borderRadius": "6px",
    "background": "#fff",
    "cursor": "pointer",
    "fontSize": "14px",
}
bar = {"display": "flex", "flexWrap": "wrap", "gap": "6px", "alignItems": "center", "margin": "8px 0"}

app = Dash(__name__, title="Timeline Visualiser")
app.layout = html.Div(
    style={"fontFamily": FONT, "maxWidth": "1400px", "margin": "0 auto", "padding": "12px"},
    children=[
        dcc.Store(id="rows", data=rows0, storage_type="local"),  # sample only until the user has data
        dcc.Store(id="view", storage_type="local"),
        dcc.Store(id="undo", data=[]),
        dcc.Store(id="expanded", data=[]),  # compressed gaps opened with their x; reset by the toggle
        dcc.Store(id="width", data=1100),
        dcc.Interval(id="tick", interval=1500),
        dcc.Download(id="download"),
        html.H2("Timeline Visualiser", style={"margin": "0 0 4px"}),
        # Row 1: title and which panels to show.
        html.Div(
            style=bar,
            children=[
                dcc.Input(
                    id="title",
                    placeholder="Timeline title (optional)",
                    debounce=True,
                    persistence=True,
                    style={**btn, "cursor": "text", "width": "260px"},
                ),
                dcc.Checklist(
                    id="show",
                    options=["Timeline", "Table", "Details"],
                    value=["Timeline", "Table"],
                    inline=True,
                    persistence=True,
                    inputStyle={"marginRight": "4px"},
                    labelStyle={"marginRight": "12px"},
                ),
            ],
        ),
        # Row 2: moving through time, and pictures.
        html.Div(
            style=bar,
            children=[
                html.Button("◀", id="prev", style=btn, title="Earlier"),
                html.Button("▶", id="next", style=btn, title="Later"),
                html.Button("Today", id="today", style=btn),
                html.Button("First event", id="first", style=btn),
                html.Button("Fit all", id="fit", style=btn, title="Show every event (up to six months)"),
                dcc.Checklist(
                    id="compress",
                    options=["Compress gaps"],
                    value=[],
                    persistence=True,
                    inputStyle={"marginRight": "4px"},
                    style={"marginLeft": "10px"},
                ),
                html.Span("Zoom:", style={"marginLeft": "10px"}),
                *[html.Button(name, id={"zoom": days}, style=btn) for name, days in ZOOMS.items()],
                html.Button("Capture PNG", id="capture", style={**btn, "marginLeft": "10px", "fontWeight": "600"}),
                html.Button("Copy PNG", id="copy", style=btn, title="Copy the picture to the clipboard"),
            ],
        ),
        # Row 3: filters. They change what is shown, never the stored data.
        html.Div(
            style=bar,
            children=[
                dcc.Input(
                    id="search",
                    placeholder="Search events",
                    debounce=True,
                    persistence=True,
                    style={**btn, "cursor": "text", "width": "180px"},
                ),
                dcc.Dropdown(
                    id="hide", multi=True, placeholder="Hide classes", persistence=True, style={"minWidth": "220px"}
                ),
                dcc.Dropdown(id="timeline-pick", placeholder="All timelines", persistence=True),
            ],
        ),
        html.Div(
            id="timeline-box",
            children=dcc.Graph(id="graph", config={"scrollZoom": True, "displayModeBar": False, "doubleClick": False}),
        ),
        html.Div(id="break-buttons", style={**bar, "margin": "4px 0"}),
        html.Div(id="caption", style={"color": "#6b6a62", "margin": "6px 0"}),
        html.Div(
            id="table-box",
            children=[
                html.Div(
                    style=bar,
                    children=[
                        html.Button("Add row", id="add", style=btn),
                        dcc.Upload(
                            html.Button("Load CSV / Excel", style=btn), id="upload", accept=".csv,.tsv,.txt,.xlsx"
                        ),
                        html.Button("Download CSV", id="save", style=btn),
                        html.Button("Undo", id="undo-btn", style=btn, title="Take back the last change to the events"),
                        html.Button("Clear all", id="clear", style=btn),
                        html.Span(id="status", style={"color": "#6b6a62"}),
                        dcc.RadioItems(
                            id="scope",
                            options=[
                                {"label": "Table: linked to view", "value": "view"},
                                {"label": "All events", "value": "all"},
                            ],
                            value="view",
                            inline=True,
                            persistence=True,
                            inputStyle={"marginRight": "4px"},
                            labelStyle={"marginRight": "12px"},
                            style={"marginLeft": "10px"},
                        ),
                    ],
                ),
                html.Div(DEP_HINT, id="dep-hint", style={"color": "#6b6a62", "margin": "4px 0", "fontSize": "14px"}),
                dash_table.DataTable(
                    id="table",
                    editable=True,
                    row_deletable=True,
                    columns=table_columns(False),
                    style_cell={
                        "textAlign": "left",
                        "padding": "6px",
                        "fontFamily": FONT,
                        "fontSize": "14px",
                        "whiteSpace": "normal",
                        "height": "auto",
                    },
                    style_cell_conditional=[
                        {"if": {"column_id": "date"}, "width": "190px"},
                        {"if": {"column_id": "end"}, "width": "150px"},
                        {"if": {"column_id": "gap"}, "width": "90px", "color": "#6b6a62"},
                        {"if": {"column_id": "check"}, "width": "180px", "color": "#b3261e"},
                        {"if": {"column_id": "class"}, "width": "160px", "fontWeight": "600"},
                    ],
                    style_data_conditional=[{"if": {"filter_query": '{key} = "yes"'}, "backgroundColor": "#fff8e1"}],
                    style_header={"fontWeight": "600", "backgroundColor": "#f3f2ee"},
                ),
                html.Details(
                    style={"marginTop": "10px"},
                    children=[
                        html.Summary("Paste rows from Excel or CSV"),
                        dcc.Textarea(
                            id="paste",
                            style={"width": "100%", "height": "110px", "marginTop": "6px"},
                            placeholder="date, class, description  or  start, end, class, description - one per line (tab or comma separated)",
                        ),
                        html.Button("Add pasted rows", id="paste-add", style=btn),
                    ],
                ),
            ],
        ),
    ],
)


# ------------------------------------------------- browser-side snippets ----
# Measure the graph width so label layout matches the real screen.
clientside_callback(
    """function(n, old) {
        const el = document.getElementById('graph');
        const w = el && el.offsetWidth ? el.offsetWidth : old;
        return w === old ? window.dash_clientside.no_update : w;
    }""",
    Output("width", "data"),
    Input("tick", "n_intervals"),
    State("width", "data"),
)

# Capture: save the timeline exactly as shown, at 2x resolution.
clientside_callback(
    """function(n) {
        const gd = document.querySelector('#graph .js-plotly-plot');
        if (n && gd) Plotly.downloadImage(gd, {format: 'png', scale: 2, filename: 'timeline'});
        return window.dash_clientside.no_update;
    }""",
    Output("capture", "title"),
    Input("capture", "n_clicks"),
)

# Copy: the same picture, put on the clipboard. The button text reports the result.
clientside_callback(
    """function(n) {
        const gd = document.querySelector('#graph .js-plotly-plot');
        if (!n || !gd) return window.dash_clientside.no_update;
        return Plotly.toImage(gd, {format: 'png', scale: 2})
            .then(url => fetch(url)).then(r => r.blob())
            .then(b => navigator.clipboard.write([new ClipboardItem({'image/png': b})]))
            .then(() => "Copied " + new Date().toLocaleTimeString(), () => "Copy blocked - use Capture PNG");
    }""",
    Output("copy", "children"),
    Input("copy", "n_clicks"),
)


# ------------------------------------------------------------- callbacks ----
@callback(
    Output("view", "data"),
    Input("graph", "relayoutData"),
    Input("prev", "n_clicks"),
    Input("next", "n_clicks"),
    Input("today", "n_clicks"),
    Input("first", "n_clicks"),
    Input("fit", "n_clicks"),
    Input({"zoom": ALL}, "n_clicks"),
    Input("rows", "data"),
    State("view", "data"),
    State("hide", "value"),
    State("timeline-pick", "value"),
    State("search", "value"),
    State("compress", "value"),
    State("expanded", "data"),
    State("width", "data"),
)
def update_view(relayout, _p, _n, _t, _f, _fit, _z, rows, view, hidden, timeline, search, compress, expanded, width):
    """Every pan, zoom and button press ends up here and sets the visible range.

    Moves are worked out in axis positions (see timeline.squash), so with
    compressed gaps one step still moves half a screen.
    """
    if view is None:  # first ever run: one month around the data
        return view_dict(*tl.default_view(rows or []))
    if ctx.triggered_id in (None, "rows"):
        return no_update
    start, _end = view_range(view)
    span, trig = view_span(view), ctx.triggered_id
    kept = kept_rows(rows, hidden, timeline, search)
    breaks = gap_breaks(kept, compress, expanded, span, width)
    pos = tl.squash(breaks, tl.datetime_num(start))
    if trig == "graph":
        r = relayout or {}
        lo, hi = r.get("xaxis.range[0]"), r.get("xaxis.range[1]")
        if "xaxis.range" in r:
            lo, hi = r["xaxis.range"]
        if lo is None or hi is None:
            return no_update
        lo, hi = (tl.datetime_num(pd.Timestamp(v).to_pydatetime()) for v in (lo, hi))
        pos, span = tl.squash(breaks, lo), tl.squash(breaks, hi) - tl.squash(breaks, lo)
    elif trig in ("prev", "next"):
        pos += span / 2 if trig == "next" else -span / 2
    elif trig == "today":
        pos = tl.squash(breaks, tl.datetime_num(datetime.now())) - span / 2
    elif trig == "first" and rows:
        pos = tl.squash(breaks, tl.when_num(rows[0]["date"])) - span / 31
    elif trig == "fit":
        fit_start, fit_end = tl.fit_view(rows or [])
        pos, span = tl.datetime_num(fit_start), (fit_end - fit_start).total_seconds() / 86400
        breaks = []
    elif isinstance(trig, dict):
        pos, span = pos + span / 2 - trig["zoom"] / 2, trig["zoom"]
    clamped = min(max(span, tl.MIN_DAYS), tl.MAX_DAYS)
    pos, span = pos + (span - clamped) / 2, clamped
    start = tl.num_datetime(tl.unsquash(breaks, pos))
    end = start + timedelta(days=span)  # the real end is worked out in render
    return view_dict(start, end, view["n"] + 1, span)  # n forces a redraw even if clamped back


@callback(
    Output("expanded", "data"),
    Input({"expand": ALL}, "n_clicks"),
    Input("compress", "value"),
    State("expanded", "data"),
    prevent_initial_call=True,
)
def expand_gap(_clicks, _compress, expanded):
    """The x on a gap button opens that gap only; switching the toggle closes them all again."""
    trig = ctx.triggered_id
    if trig == "compress":
        return []
    if isinstance(trig, dict) and ctx.triggered[0]["value"]:
        return (expanded or []) + [trig["expand"]]
    return no_update


def read_upload(contents: str, filename: str | None) -> tuple[list[dict], int]:
    """Rows from an uploaded file: Excel by extension, anything else as text."""
    content = base64.b64decode(contents.split(",", 1)[1])
    if (filename or "").lower().endswith((".xlsx", ".xlsm")):
        return tl.rows_from_excel(content)
    return tl.rows_from_text(content.decode("utf-8-sig"))


@callback(
    Output("rows", "data"),
    Output("status", "children"),
    Output("paste", "value"),
    Output("undo", "data"),
    Input("table", "data_timestamp"),
    Input("add", "n_clicks"),
    Input("upload", "contents"),
    Input("paste-add", "n_clicks"),
    Input("clear", "n_clicks"),
    Input("undo-btn", "n_clicks"),
    State("table", "data"),
    State("table", "data_previous"),
    State("rows", "data"),
    State("view", "data"),
    State("upload", "filename"),
    State("paste", "value"),
    State("undo", "data"),
    prevent_initial_call=True,
)
def update_rows(_ts, _a, contents, _pa, _c, _u, table, previous, rows, view, filename, pasted, history):
    """Every change to the data ends up here; the result is always sorted.

    The rows as they were before the change are pushed onto the undo list.
    """
    trig, status, paste_out = ctx.triggered_id, "", no_update
    rows, history = rows or [], history or []
    before = rows
    if trig == "undo-btn":
        if not history:
            return no_update, "Nothing to undo.", no_update, no_update
        return history[-1], "Last change undone.", no_update, history[:-1]
    if trig == "clear":
        rows, status = [], "All events cleared. Undo brings them back."
    elif trig == "add":
        start, end = view_range(view)
        rows = rows + [tl.make_row((start + (end - start) / 2).date())]
        status = "Blank row added at the middle of the visible range."
    elif trig in ("upload", "paste-add"):
        try:
            new, bad = read_upload(contents, filename) if trig == "upload" else tl.rows_from_text(pasted or "")
        except Exception as err:  # unreadable file: say so, keep existing data
            return no_update, f"Could not read that data ({err}).", no_update, no_update
        if trig == "paste-add":
            paste_out = ""
        rows, fresh = tl.merge_new(rows, new)
        status = f"Added {len(fresh)} event(s)" + (f", skipped {bad} unreadable row(s)." if bad else ".")
        if fresh:
            status += f" First is on {fresh[0]['date']}."
    elif trig == "table":
        rows, status = tl.apply_table(rows, table or [], previous)
    rows = tl.sort_rows(rows)
    if rows != before:
        history = (history + [before])[-UNDO_DEPTH:]
    return rows, status, paste_out, history


@callback(
    Output("graph", "figure"),
    Output("table", "data"),
    Output("table", "columns"),
    Output("caption", "children"),
    Output("timeline-box", "style"),
    Output("table-box", "style"),
    Output("hide", "options"),
    Output("timeline-pick", "options"),
    Output("timeline-pick", "style"),
    Output("break-buttons", "children"),
    Output("dep-hint", "style"),
    Input("rows", "data"),
    Input("view", "data"),
    Input("width", "data"),
    Input("show", "value"),
    Input("title", "value"),
    Input("search", "value"),
    Input("hide", "value"),
    Input("timeline-pick", "value"),
    Input("compress", "value"),
    Input("expanded", "data"),
    Input("scope", "value"),
)
def render(rows, view, width, show, title, search, hidden, timeline, compress, expanded, scope="view"):
    """Redraw the timeline and fill the table (events in view, or all events).

    This is the only place that draws, so timeline and table can never disagree.
    """
    if view is None:
        return (no_update,) * 11
    rows = rows or []
    start, _end = view_range(view)
    span, names = view_span(view), tl.timelines(rows)
    kept = tl.flag_rows(kept_rows(rows, hidden, timeline, search), tl.dependency_issues(rows))
    breaks = gap_breaks(kept, compress, expanded, span, width)
    end = tl.num_datetime(tl.unsquash(breaks, tl.squash(breaks, tl.datetime_num(start)) + span))
    in_view = tl.in_view(kept, start, end)
    listed = tl.with_gaps(kept if scope == "all" else in_view)  # the table: everything, or only what is in view
    table = [{**{k: v for k, v in r.items() if k != "warn"}, "check": "; ".join(r.get("warn") or [])} for r in listed]
    hourly = tl.tick_step(plot_px(width) / span)[0] == "hour"
    stamp = "%d %b %Y %H:%M" if hourly else "%d %b %Y"  # show times in the caption once the axis shows hours
    caption = f"Showing {start:{stamp}} – {end:{stamp}} · {len(in_view)} of {len(rows)} events"
    if len(kept) < len(rows):
        caption += f" · filter on ({len(rows) - len(kept)} hidden)"
    shown_breaks = [b for b in breaks if tl.datetime_num(start) < b["lo"] < tl.datetime_num(end)]
    if shown_breaks:
        caption += f" · {len(shown_breaks)} gap(s) compressed"
    drawable = [r for r in kept if r["class"] or r["description"]]
    colours = tl.class_colours(rows)
    fig = build_figure(drawable, start, end, width or 1100, title or "", datetime.now(), colours, breaks)
    buttons = [
        html.Button(f"({tl.break_text(b['gap'])}) ×", id={"expand": b["key"]}, title="Expand this gap", style=btn)
        for b in shown_breaks
    ]
    hide = {"display": "none"}
    flagged = [r for r in kept if r.get("warn")]
    if flagged:
        caption += f" · ⚠ {len(flagged)} dependency problem(s)"
    return (
        fig,
        table,
        table_columns("Details" in show, any(r["check"] for r in table)),
        caption,
        {} if "Timeline" in show else hide,
        {} if "Table" in show else hide,
        sorted({r["class"] for r in rows if r["class"]}, key=str.lower),
        names,
        {"minWidth": "180px"} if names else hide,
        buttons,
        {"color": "#6b6a62", "margin": "4px 0", "fontSize": "14px"} if "Details" in show else hide,
    )


@callback(Output("download", "data"), Input("save", "n_clicks"), State("rows", "data"), prevent_initial_call=True)
def download_csv(_n, rows):
    """All events, whatever the filters show."""
    return {"content": tl.to_csv(rows or []), "filename": "timeline_events.csv"}


if __name__ == "__main__":
    threading.Timer(1.0, webbrowser.open, ["http://127.0.0.1:8050"]).start()
    app.run(debug=False)
