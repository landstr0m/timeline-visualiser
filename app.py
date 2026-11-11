"""Timeline Visualiser - Dash web app.  Run:  python app.py

State lives in two browser-side stores:
  rows : every event (the table only shows those inside the visible range)
  view : the visible date range {start, end, n}
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dash import (ALL, Dash, Input, Output, State, callback, clientside_callback,
                  ctx, dash_table, dcc, html, no_update)

import timeline as tl

SAMPLE = Path(__file__).with_name("sample_events.csv")
ZOOMS = {"1 week": 7, "2 weeks": 14, "1 month": 31, "3 months": 92, "6 months": 184}


def view_dict(start: datetime, end: datetime, n: int = 0) -> dict:
    return {"start": start.isoformat(), "end": end.isoformat(), "n": n}


def view_range(view: dict) -> tuple[datetime, datetime]:
    return datetime.fromisoformat(view["start"]), datetime.fromisoformat(view["end"])


rows0, _ = tl.rows_from_text(SAMPLE.read_text()) if SAMPLE.exists() else ([], 0)
btn = {"padding": "6px 10px", "border": "1px solid #c9c8c0", "borderRadius": "6px",
       "background": "#fff", "cursor": "pointer", "fontSize": "14px"}
bar = {"display": "flex", "flexWrap": "wrap", "gap": "6px", "alignItems": "center", "margin": "8px 0"}

app = Dash(__name__, title="Timeline Visualiser")
app.layout = html.Div(style={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
                             "maxWidth": "1400px", "margin": "0 auto", "padding": "12px"}, children=[
    dcc.Store(id="rows", data=rows0),
    dcc.Store(id="view", data=view_dict(*tl.default_view(rows0))),
    dcc.Store(id="width", data=1100),
    dcc.Interval(id="tick", interval=1500),
    dcc.Download(id="download"),
    html.H2("Timeline Visualiser", style={"margin": "0 0 4px"}),
    html.Div(style=bar, children=[
        dcc.Input(id="title", placeholder="Timeline title (optional)", debounce=True,
                  style={**btn, "cursor": "text", "width": "260px"}),
        dcc.Checklist(id="show", options=["Timeline", "Table"], value=["Timeline", "Table"], inline=True,
                      inputStyle={"marginRight": "4px"}, labelStyle={"marginRight": "12px"}),
    ]),
    html.Div(style=bar, children=[
        html.Button("◀", id="prev", style=btn, title="Earlier"),
        html.Button("▶", id="next", style=btn, title="Later"),
        html.Button("Today", id="today", style=btn),
        html.Button("First event", id="first", style=btn),
        html.Span("Zoom:", style={"marginLeft": "10px"}),
        *[html.Button(name, id={"zoom": days}, style=btn) for name, days in ZOOMS.items()],
        html.Button("Capture PNG", id="capture", style={**btn, "marginLeft": "10px", "fontWeight": "600"}),
    ]),
    html.Div(id="timeline-box", children=dcc.Graph(
        id="graph", config={"scrollZoom": True, "displayModeBar": False, "doubleClick": False})),
    html.Div(id="caption", style={"color": "#6b6a62", "margin": "6px 0"}),
    html.Div(id="table-box", children=[
        html.Div(style=bar, children=[
            html.Button("Add row", id="add", style=btn),
            dcc.Upload(html.Button("Load CSV / Excel", style=btn), id="upload", accept=".csv,.tsv,.txt,.xlsx"),
            html.Button("Download CSV", id="save", style=btn),
            html.Button("Clear all", id="clear", style=btn),
            html.Span(id="status", style={"color": "#6b6a62"}),
        ]),
        dash_table.DataTable(
            id="table", editable=True, row_deletable=True,
            columns=[{"name": "Date (YYYY-MM-DD)", "id": "date"}, {"name": "Class", "id": "class"},
                     {"name": "Description", "id": "description"}],
            style_cell={"textAlign": "left", "padding": "6px", "fontFamily": "Segoe UI, Helvetica, Arial, sans-serif", "fontSize": "14px",
                        "whiteSpace": "normal", "height": "auto"},
            style_cell_conditional=[{"if": {"column_id": "date"}, "width": "150px"},
                                    {"if": {"column_id": "class"}, "width": "160px", "fontWeight": "600"}],
            style_header={"fontWeight": "600", "backgroundColor": "#f3f2ee"}),
        html.Details(style={"marginTop": "10px"}, children=[
            html.Summary("Paste rows from Excel or CSV"),
            dcc.Textarea(id="paste", style={"width": "100%", "height": "110px", "marginTop": "6px"},
                         placeholder="date, class, description - one event per line (tab or comma separated)"),
            html.Button("Add pasted rows", id="paste-add", style=btn),
        ]),
    ]),
])


# Measure the graph width so label layout matches the real screen.
clientside_callback(
    """function(n, old) {
        const el = document.getElementById('graph');
        const w = el && el.offsetWidth ? el.offsetWidth : old;
        return w === old ? window.dash_clientside.no_update : w;
    }""",
    Output("width", "data"), Input("tick", "n_intervals"), State("width", "data"))

# Capture: save the timeline exactly as shown, at 2x resolution.
clientside_callback(
    """function(n) {
        const gd = document.querySelector('#graph .js-plotly-plot');
        if (n && gd) Plotly.downloadImage(gd, {format: 'png', scale: 2, filename: 'timeline'});
        return window.dash_clientside.no_update;
    }""",
    Output("capture", "title"), Input("capture", "n_clicks"))


@callback(Output("view", "data"),
          Input("graph", "relayoutData"), Input("prev", "n_clicks"), Input("next", "n_clicks"),
          Input("today", "n_clicks"), Input("first", "n_clicks"), Input({"zoom": ALL}, "n_clicks"),
          State("view", "data"), State("rows", "data"), prevent_initial_call=True)
def update_view(relayout, _p, _n, _t, _f, _z, view, rows):
    """Every pan, zoom and button press ends up here and sets the visible range."""
    start, end = view_range(view)
    span, centre, trig = end - start, start + (end - start) / 2, ctx.triggered_id
    if trig == "graph":
        r = relayout or {}
        lo, hi = r.get("xaxis.range[0]"), r.get("xaxis.range[1]")
        if "xaxis.range" in r:
            lo, hi = r["xaxis.range"]
        if lo is None or hi is None:
            return no_update
        start, end = pd.Timestamp(lo).to_pydatetime(), pd.Timestamp(hi).to_pydatetime()
    elif trig in ("prev", "next"):
        shift = span / 2 if trig == "next" else -span / 2
        start, end = start + shift, end + shift
    elif trig in ("today", "first"):
        centre = datetime.now()
        if trig == "first" and rows:
            centre = datetime.fromisoformat(rows[0]["date"]) + span / 2 - timedelta(days=1)
        start, end = centre - span / 2, centre + span / 2
    elif isinstance(trig, dict):
        half = timedelta(days=trig["zoom"] / 2)
        start, end = centre - half, centre + half
    start, end = tl.clamp_view(start, end)
    return view_dict(start, end, view["n"] + 1)  # n forces a redraw even if clamped back


@callback(Output("rows", "data"), Output("status", "children"), Output("paste", "value"),
          Input("table", "data_timestamp"), Input("add", "n_clicks"), Input("upload", "contents"),
          Input("paste-add", "n_clicks"), Input("clear", "n_clicks"),
          State("table", "data"), State("table", "data_previous"), State("rows", "data"),
          State("view", "data"), State("upload", "filename"), State("paste", "value"),
          prevent_initial_call=True)
def update_rows(_ts, _a, contents, _pa, _c, table, previous, rows, view, filename, pasted):
    """Every change to the data ends up here; the result is always sorted."""
    trig, status, paste_out = ctx.triggered_id, "", no_update
    if trig == "clear":
        return [], "All events cleared.", no_update
    if trig == "add":
        start, end = view_range(view)
        rows = rows + [tl.make_row((start + (end - start) / 2).date())]
        status = "Blank row added at the middle of the visible range."
    elif trig in ("upload", "paste-add"):
        try:
            if trig == "upload":
                content = base64.b64decode(contents.split(",", 1)[1])
                excel = (filename or "").lower().endswith((".xlsx", ".xlsm"))
                new, bad = tl.rows_from_excel(content) if excel else tl.rows_from_text(content.decode("utf-8-sig"))
            else:
                new, bad = tl.rows_from_text(pasted or "")
                paste_out = ""
        except Exception as err:  # unreadable file: say so, keep existing data
            return no_update, f"Could not read that data ({err}).", no_update
        seen = {(r["date"], r["class"], r["description"]) for r in rows}
        fresh = [r for r in new if (r["date"], r["class"], r["description"]) not in seen]
        rows = rows + fresh
        status = f"Added {len(fresh)} event(s)" + (f", skipped {bad} unreadable row(s)." if bad else ".")
        if fresh:
            status += f" First is on {fresh[0]['date']}."
    elif trig == "table":
        by_id = {r["id"]: r for r in rows}
        kept = {r.get("id") for r in table}
        for old in previous or []:  # rows deleted in the table
            if old.get("id") not in kept:
                by_id.pop(old.get("id"), None)
        for r in table:
            day = tl.parse_date(r.get("date"))
            old = by_id.get(r.get("id"))
            if day is None:
                status = f"'{r.get('date')}' is not a date - use YYYY-MM-DD. Kept the previous date."
                if old is None:
                    continue
                day = tl.parse_date(old["date"])
            new = tl.make_row(day, r.get("class") or "", r.get("description") or "", r.get("id"))
            by_id[new["id"]] = new
        rows = list(by_id.values())
    return tl.sort_rows(rows), status, paste_out


@callback(Output("graph", "figure"), Output("table", "data"), Output("caption", "children"),
          Output("timeline-box", "style"), Output("table-box", "style"),
          Input("rows", "data"), Input("view", "data"), Input("width", "data"),
          Input("show", "value"), Input("title", "value"))
def render(rows, view, width, show, title):
    """Redraw the timeline and filter the table to the visible range."""
    start, end = view_range(view)
    visible = tl.in_view(rows, start, end)
    caption = f"Showing {start:%d %b %Y} – {end:%d %b %Y} · {len(visible)} of {len(rows)} events"
    drawable = [r for r in rows if r["class"] or r["description"]]
    fig = tl.build_figure(drawable, start, end, width or 1100, title or "")
    hide = {"display": "none"}
    return (fig, visible, caption,
            {} if "Timeline" in show else hide, {} if "Table" in show else hide)


@callback(Output("download", "data"), Input("save", "n_clicks"), State("rows", "data"),
          prevent_initial_call=True)
def download_csv(_n, rows):
    return {"content": tl.to_csv(rows), "filename": "timeline_events.csv"}


if __name__ == "__main__":
    app.run(debug=False)
