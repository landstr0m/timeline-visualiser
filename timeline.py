"""Timeline Visualiser - pure logic (no web code).

Three jobs: clean incoming rows, lay out labels so they stay legible,
and build the Plotly figure. Everything here is unit-testable.
"""
from __future__ import annotations

import io
import textwrap
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go

COLUMNS = ["date", "end", "class", "description"]
MIN_DAYS, MAX_DAYS, DEFAULT_DAYS = 7, 184, 31

# Colour-blind-checked categorical palette, assigned in fixed order.
# Classes beyond the 8th share the neutral OTHER colour (never a recycled hue).
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
           "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#8a897f"
INK, MUTED, GRID = "#1a1a19", "#6b6a62", "#e6e5df"

ALIASES = {
    "date": "date", "day": "date", "when": "date", "start": "date", "start date": "date", "from": "date",
    "end": "end", "end date": "end", "finish": "end", "to": "end", "until": "end",
    "class": "class", "title": "class", "type": "class", "category": "class",
    "description": "description", "desc": "description", "details": "description",
    "text": "description", "activity": "activity", "event": "activity",
}
DATE_FORMATS = ["%d-%b-%Y", "%d-%b-%y", "%d %b %Y", "%d %B %Y", "%d%b%Y",
                "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"]
NO_YEAR_FORMATS = ["%d-%b", "%d %b", "%d %B", "%d.%m.", "%d/%m"]


# ---------------------------------------------------------------- data ----
def parse_date(value) -> date | None:
    """Return a date, or None if the value cannot be read as one.

    ISO (2025-03-10) is preferred; day-first forms such as 10-Mar-2025,
    10.03.2025 and 10-Mar (current year) are also accepted.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    for fmt in NO_YEAR_FORMATS:
        try:
            parsed = datetime.strptime(f"{text} 2000", f"{fmt} %Y")
            return parsed.date().replace(year=date.today().year)
        except ValueError:
            pass
    return None


def _cell(value) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()


def make_row(day: date, cls: str = "", description: str = "", row_id: str | None = None,
             end: date | None = None) -> dict:
    """One event. With an end date it is a band; without, a single-date event."""
    if end and end < day:
        day, end = end, day
    return {"id": row_id or uuid.uuid4().hex[:10], "date": day.isoformat(),
            "end": end.isoformat() if end and end != day else "",
            "class": cls.strip().rstrip(":").strip(), "description": description.strip()}


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["date"], r.get("end") or "", r["class"].lower(), r["description"].lower()))


def rows_from_frame(raw: pd.DataFrame) -> tuple[list[dict], int]:
    """Turn a header-less DataFrame into event rows. Returns (rows, rejected).

    A first row whose first cell is not a date is treated as a header.
    Without a header: 2 columns = date + "Class: description",
    3 = date, class, description; 4 = date, end, class, description.
    """
    raw = raw.dropna(how="all")
    if raw.empty:
        return [], 0
    first = raw.iloc[0].tolist()
    if parse_date(first[0]) is None:  # header row
        names = [ALIASES.get(_cell(c).lower(), f"_{i}") for i, c in enumerate(first)]
        raw = raw.iloc[1:]
    else:
        names = {2: ["date", "activity"], 3: ["date", "class", "description"]}.get(raw.shape[1], COLUMNS)
        names = (names + [f"_{i}" for i in range(raw.shape[1])])[:raw.shape[1]]
    raw.columns = names
    rows, rejected = [], 0
    for rec in raw.to_dict("records"):
        day = parse_date(rec.get("date"))
        cls, desc = _cell(rec.get("class")), _cell(rec.get("description"))
        if "activity" in rec and not cls:
            head, sep, tail = _cell(rec["activity"]).partition(":")
            cls, desc = (head, tail) if sep else ("", head)
        if day is None or not (cls or desc):
            rejected += 1
            continue
        rows.append(make_row(day, cls, desc, end=parse_date(rec.get("end"))))
    return sort_rows(rows), rejected


def rows_from_text(text: str) -> tuple[list[dict], int]:
    """Parse pasted or uploaded CSV/TSV text."""
    if not text.strip():
        return [], 0
    sep = "\t" if "\t" in text else (";" if text.count(";") > text.count(",") else ",")
    raw = pd.read_csv(io.StringIO(text), sep=sep, header=None, dtype=str,
                      skipinitialspace=True, keep_default_na=False)
    return rows_from_frame(raw)


def rows_from_excel(content: bytes) -> tuple[list[dict], int]:
    return rows_from_frame(pd.read_excel(io.BytesIO(content), header=None))


def to_csv(rows: list[dict]) -> str:
    return pd.DataFrame(sort_rows(rows), columns=COLUMNS).to_csv(index=False)


def class_colours(rows: list[dict]) -> dict[str, str]:
    """Colour follows the class name (alphabetical order), not what is on screen."""
    classes = sorted({r["class"] for r in rows if r["class"]}, key=str.lower)
    return {c: PALETTE[i] if i < len(PALETTE) else OTHER for i, c in enumerate(classes)}


# ---------------------------------------------------------------- view ----
def clamp_view(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Keep the visible span between one week and six months, same centre."""
    span = (end - start).total_seconds() / 86400
    clamped = min(max(span, MIN_DAYS), MAX_DAYS)
    if clamped != span:
        centre = start + (end - start) / 2
        start = centre - timedelta(days=clamped / 2)
        end = centre + timedelta(days=clamped / 2)
    return start, end


def default_view(rows: list[dict]) -> tuple[datetime, datetime]:
    """One month: the current month if it has events, else the first event's month."""
    today = date.today()
    months = {r["date"][:7] for r in rows}
    if rows and today.isoformat()[:7] not in months:
        today = date.fromisoformat(rows[0]["date"])
    start = datetime(today.year, today.month, 1)
    return start, start + timedelta(days=DEFAULT_DAYS)


def in_view(rows: list[dict], start: datetime, end: datetime) -> list[dict]:
    """Events on screen: single dates inside the range, bands that overlap it."""
    lo, hi = start.date().isoformat(), end.date().isoformat()
    return [r for r in rows if r["date"] <= hi and (r.get("end") or r["date"]) >= lo]


# -------------------------------------------------------------- layout ----
CHAR_PX, LINE_PX, LANE_GAP, MAX_LANES, BAND_PX = 7.0, 16, 10, 5, 28
# Detail levels, tried in order until the labels fit in MAX_LANES lanes:
# (wrap width in characters, max description lines)
LEVELS = [(34, 2), (24, 1), (0, 0)]


def _label_lines(row: dict, wrap: int, max_lines: int, show_date: bool) -> list[str]:
    head = row["class"] or "Event"
    if show_date:
        head += " · " + date.fromisoformat(row["date"]).strftime("%d %b")
    body = []
    if wrap and row["description"]:
        body = textwrap.wrap(row["description"], wrap, max_lines=max_lines, placeholder="…")
    return [head] + body


def layout_labels(rows: list[dict], px_per_day: float, show_date: bool = False) -> list[dict]:
    """Give each event a text label and a lane (1 = nearest the axis).

    Labels sit to the right of their date line. Each one takes the lowest lane
    whose previous label has ended, so labels never overlap. If that needs more
    than MAX_LANES lanes, the text is shortened and the layout retried.
    """
    placed: list[dict] = []
    for wrap, max_lines in LEVELS:
        placed, lane_end = [], []
        for row in sort_rows(rows):
            lines = _label_lines(row, wrap, max_lines, show_date)
            x = date.fromisoformat(row["date"]).toordinal()
            width = (max(len(s) for s in lines) * CHAR_PX + 16) / px_per_day
            lane = next((i for i, e in enumerate(lane_end) if e <= x), len(lane_end))
            if lane == len(lane_end):
                lane_end.append(0)
            lane_end[lane] = x + width
            placed.append({**row, "lines": lines, "lane": lane + 1, "x": x, "x_end": x + width})
        if len(lane_end) <= MAX_LANES:
            break
    return placed


def layout_bands(rows: list[dict], px_per_day: float, view_start: int) -> list[dict]:
    """Give each band (event with an end date) a lane and a label position.

    The label sits at the band's start, or at the left edge of the view when
    the band started earlier. A lane is reused once the previous band and its
    label have both ended.
    """
    placed, lane_end = [], []
    for row in sort_rows(rows):
        x0 = date.fromisoformat(row["date"]).toordinal()
        x1 = date.fromisoformat(row["end"]).toordinal()
        label_x = min(max(x0, view_start), x1)
        name = row["class"] or "Event"
        chars = len(name) + len(row["description"]) + 2
        right = max(x1, label_x + (chars * CHAR_PX + 16) / px_per_day)
        lane = next((i for i, e in enumerate(lane_end) if e <= x0), len(lane_end))
        if lane == len(lane_end):
            lane_end.append(0)
        lane_end[lane] = right
        placed.append({**row, "lane": lane + 1, "label_x": label_x, "x": x0, "x_end": right,
                       "text": f"<b>{name}</b>  {row['description']}".strip()})
    return placed


# -------------------------------------------------------------- figure ----
def build_figure(rows: list[dict], start: datetime, end: datetime,
                 width_px: int = 1100, title: str = "") -> go.Figure:
    span = (end - start).total_seconds() / 86400
    margin = dict(l=30, r=30, t=70 if title else 40, b=50)
    px_per_day = max(width_px - margin["l"] - margin["r"], 200) / span
    daily = px_per_day >= 22  # room for a tick label on every day
    colours = class_colours(rows)

    # Lay out one extra screen either side so dragging reveals finished labels.
    pad = timedelta(days=span)
    shown = in_view(rows, start - pad, end + pad)
    labels = layout_labels([r for r in shown if not r.get("end")], px_per_day, show_date=not daily)
    view_start = start.date().toordinal() + (start.time() != datetime.min.time())
    bands = layout_bands([r for r in shown if r.get("end")], px_per_day, view_start)
    n_lines = max((len(p["lines"]) for p in labels), default=1)
    lane_px = n_lines * LINE_PX + LANE_GAP
    points_top = 24 + max((p["lane"] for p in labels), default=0) * lane_px
    # Bands run in their own strip above the single-date labels.
    top = points_top + (10 + max(b["lane"] for b in bands) * BAND_PX if bands else 0)

    fig = go.Figure()
    for cls in sorted({p["class"] for p in labels}, key=str.lower):
        xs, ys, hover = [], [], []
        for p in (p for p in labels if p["class"] == cls):
            y = 24 + (p["lane"] - 1) * lane_px + (len(p["lines"]) * LINE_PX) / 2 + 4
            tip = f"{date.fromisoformat(p['date']):%a %d %b %Y}<br><b>{cls or 'Event'}</b><br>{p['description']}"
            xs += [p["date"], p["date"], None]
            ys += [0, y, None]
            hover += [tip, tip, None]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers", name=cls or "Event",
            line=dict(color=colours.get(cls, OTHER), width=2),
            marker=dict(size=8, color=colours.get(cls, OTHER), line=dict(color="#fff", width=2)),
            hovertext=hover, hoverinfo="text", cliponaxis=False))
    for p in labels:
        text = "<br>".join([f"<b>{p['lines'][0]}</b>"] + p["lines"][1:])
        fig.add_annotation(
            x=p["date"], y=24 + (p["lane"] - 1) * lane_px, xanchor="left", yanchor="bottom",
            xshift=5, text=text, align="left", showarrow=False,
            font=dict(size=12, color=INK), bgcolor="rgba(255,255,255,0.92)", borderpad=2)

    if span <= 100:  # shade weekends
        day = (start - pad).date()
        while day <= (end + pad).date():
            if day.weekday() == 5:
                fig.add_vrect(x0=datetime.combine(day, datetime.min.time()) - timedelta(hours=12),
                              x1=datetime.combine(day, datetime.min.time()) + timedelta(hours=36),
                              fillcolor="#f6f5f1", line_width=0, layer="below")
            day += timedelta(days=1)

    for b in bands:
        y0 = points_top + 10 + (b["lane"] - 1) * BAND_PX
        colour = colours.get(b["class"], OTHER)
        tip = (f"{date.fromisoformat(b['date']):%d %b %Y} – {date.fromisoformat(b['end']):%d %b %Y}"
               f"<br><b>{b['class'] or 'Event'}</b><br>{b['description']}")
        fig.add_shape(type="rect", x0=b["date"], x1=b["end"], y0=y0, y1=y0 + BAND_PX - 6,
                      fillcolor=colour, opacity=0.3, line=dict(color=colour, width=1), layer="below")
        fig.add_annotation(x=date.fromordinal(b["label_x"]).isoformat(), y=y0 + (BAND_PX - 6) / 2,
                           xanchor="left", yanchor="middle", xshift=6, text=b["text"], showarrow=False,
                           font=dict(size=12, color=INK))
        # Invisible hover target (annotation hover text would block dragging).
        fig.add_trace(go.Scatter(x=[date.fromordinal(b["label_x"]).isoformat()], y=[y0 + (BAND_PX - 6) / 2],
                                 mode="markers", marker=dict(size=16, opacity=0), hovertext=[tip],
                                 hoverinfo="text", showlegend=False))

    if px_per_day >= 48:
        ticks = dict(dtick=86400000, tickformat="%a %d\n%b %Y")
    elif daily:
        ticks = dict(dtick=86400000, tickformat="%d\n%b %Y")
    elif px_per_day * 7 >= 50:
        ticks = dict(dtick=7 * 86400000, tick0="2024-01-01", tickformat="%d %b\n%Y")
    else:
        ticks = dict(dtick="M1", tickformat="%b\n%Y")
    fig.update_layout(
        title=dict(text=title, x=0.01, font=dict(size=20, color=INK)) if title else None,
        height=top + margin["t"] + margin["b"], margin=margin,
        paper_bgcolor="#fff", plot_bgcolor="#fff", dragmode="pan",
        font=dict(family="Segoe UI, Helvetica, Arial, sans-serif", color=INK),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                    itemclick=False, itemdoubleclick=False, font=dict(color=MUTED)),
        showlegend=len({p['class'] for p in labels}) > 1,
        hoverlabel=dict(bgcolor="#fff", font=dict(color=INK)),
        xaxis=dict(type="date", range=[start, end], showline=True, linecolor=MUTED,
                   ticks="outside", tickcolor=MUTED, tickfont=dict(color=MUTED),
                   showgrid=not daily, gridcolor=GRID, **ticks),
        yaxis=dict(range=[0, top], visible=False, fixedrange=True),
    )
    return fig
