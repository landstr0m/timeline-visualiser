"""Timeline Visualiser - drawing (Plotly). All decisions come from timeline.py.

build_figure() is the only entry point. It works in pixels on the y axis
(0 = the date axis, growing upwards) and dates on the x axis:

    top  ───────────────────────────────
          bands      (one lane per BAND_PX)
    points_top ─────────────────────────
          labels     (one lane per lane_px)
    0    ─────────── date axis ─────────

web/index.html draws the same picture as SVG.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import plotly.graph_objects as go

import timeline as tl

LABEL_BASE = 24  # px between the axis and the lowest label
TODAY_PX = 16  # headroom above the top lane for the "Today" caption
HOUR_MS, DAY_MS = 3600000, 86400000


def _lines_and_markers(fig: go.Figure, labels: list[dict], colours: dict, lane_px: float) -> None:
    """One trace per class: a vertical line from the axis up to each label."""
    for cls in sorted({p["class"] for p in labels}, key=str.lower):
        xs, ys, hover, sizes, symbols = [], [], [], [], []
        for p in (p for p in labels if p["class"] == cls):
            y = LABEL_BASE + (p["lane"] - 1) * lane_px + (len(p["lines"]) * tl.LINE_PX) / 2 + 4
            tip = tl.tip_lines(p)
            tip = "<br>".join([tip[0], f"<b>{tip[1]}</b>"] + tip[2:])
            xs += [p["date"], p["date"], None]
            ys += [0, y, None]
            hover += [tip, tip, None]
            # One marker on the axis and one where the line meets its label.
            # A key event gets a larger diamond on the axis.
            sizes += [13 if p.get("key") else 8, 8, 8]
            symbols += ["diamond" if p.get("key") else "circle", "circle", "circle"]
        colour = colours.get(cls, tl.OTHER)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                name=cls or "Event",
                line=dict(color=colour, width=2),
                marker=dict(size=sizes, symbol=symbols, color=colour, line=dict(color="#fff", width=2)),
                hovertext=hover,
                hoverinfo="text",
                cliponaxis=False,
            )
        )


def _label_text(fig: go.Figure, labels: list[dict], lane_px: float) -> None:
    """Label text on a white box, so lines to higher labels pass behind lower ones."""
    for p in labels:
        fig.add_annotation(
            x=p["date"],
            y=LABEL_BASE + (p["lane"] - 1) * lane_px,
            xanchor="left",
            yanchor="bottom",
            xshift=5,
            text="<br>".join([f"<b>{p['lines'][0]}</b>"] + p["lines"][1:]),
            align="left",
            showarrow=False,
            font=dict(size=12, color=tl.INK),
            bgcolor="rgba(255,255,255,0.92)",
            borderpad=2,
        )


def _weekends(fig: go.Figure, first: datetime, last: datetime, hourly: bool, breaks=()) -> None:
    """Grey weekend stripes.

    Date-only events sit on the midnight tick of their day, so at day zoom the
    stripe is centred on the Saturday and Sunday ticks (noon Friday to noon
    Sunday). With hour ticks the true weekend, midnight to midnight, is shaded.
    """
    shift = timedelta(0) if hourly else timedelta(hours=12)
    day = first.date()
    while day <= last.date():
        n = tl.datetime_num(datetime.combine(day, datetime.min.time()))
        hidden = any(b["lo"] < n + 2 and n - 1 < b["hi"] for b in breaks)  # touches a compressed gap
        if day.weekday() == 5 and not hidden:
            saturday = datetime.combine(day, datetime.min.time())
            fig.add_vrect(
                x0=saturday - shift,
                x1=saturday + timedelta(days=2) - shift,
                fillcolor="#f6f5f1",
                line_width=0,
                layer="below",
            )
        day += timedelta(days=1)


def _bands(fig: go.Figure, bands: list[dict], colours: dict, points_top: float) -> None:
    """Coloured bars in their own strip above the single-date labels."""
    for b in bands:
        y0 = points_top + 10 + (b["lane"] - 1) * tl.BAND_PX
        colour = colours.get(b["class"], tl.OTHER)
        tip = tl.tip_lines(b)
        fig.add_shape(
            type="rect",
            x0=b["date"],
            x1=b["end"],
            y0=y0,
            y1=y0 + tl.BAND_PX - 6,
            fillcolor=colour,
            opacity=0.3,
            line=dict(color=colour, width=3 if b.get("key") else 1),
            layer="below",
        )
        fig.add_annotation(
            x=tl.num_when(b["label_x"]),
            y=y0 + (tl.BAND_PX - 6) / 2,
            xanchor="left",
            yanchor="middle",
            xshift=6,
            text=f"<b>{b['name']}</b>  {b['description']}".strip(),
            showarrow=False,
            font=dict(size=12, color=tl.INK),
        )
        # Invisible hover target (annotation hover text would block dragging).
        fig.add_trace(
            go.Scatter(
                x=[tl.num_when(b["label_x"])],
                y=[y0 + (tl.BAND_PX - 6) / 2],
                mode="markers",
                marker=dict(size=16, opacity=0),
                hovertext=["<br>".join([tip[0], f"<b>{tip[1]}</b>"] + tip[2:])],
                hoverinfo="text",
                showlegend=False,
            )
        )


def _today(fig: go.Figure, now: datetime, hourly: bool, top: float) -> None:
    """Dashed "Today" line. At day zoom it sits on today's tick; with hour ticks, at the current time."""
    x = now if hourly else datetime.combine(now.date(), datetime.min.time())
    fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=top, line=dict(color=tl.MUTED, width=1, dash="dash"))
    fig.add_annotation(
        x=x, y=top, yanchor="bottom", text="Today", showarrow=False, font=dict(size=11, color=tl.MUTED), name="today"
    )


def _breaks(fig: go.Figure, breaks: list[dict], top: float) -> None:
    """Each compressed gap: a dotted line, "//" on the axis and the hidden time as a label.

    Plotly's rangebreaks cut the time out; these marks make the cut impossible to miss.
    """
    for b in breaks:
        x = tl.num_datetime(b["lo"])
        fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=top, line=dict(color=tl.MUTED, width=1, dash="dot"))
        fig.add_annotation(
            x=x, y=0, text="<b>//</b>", showarrow=False, font=dict(size=14, color=tl.INK), bgcolor="#fff", borderpad=0
        )
        fig.add_annotation(
            x=x,
            y=0,
            yanchor="top",
            yshift=-44,  # under the two lines of tick text
            text=f"({tl.break_text(b['gap'])})",
            showarrow=False,
            font=dict(size=11, color=tl.INK),
            bgcolor="#fff",
        )


def _ticks(px_per_day: float) -> dict:
    """Plotly axis settings for the tick spacing chosen by timeline.tick_step."""
    unit, step = tl.tick_step(px_per_day)
    if unit == "hour":
        return dict(dtick=step * HOUR_MS, tickformat="%H:%M\n%a %d %b %Y")
    if unit == "day":
        return dict(dtick=DAY_MS, tickformat="%a %d\n%b %Y" if px_per_day >= 48 else "%d\n%b %Y")
    if unit == "week":
        return dict(dtick=7 * DAY_MS, tick0="2024-01-01", tickformat="%d %b\n%Y")
    return dict(dtick="M1", tickformat="%b\n%Y")


def build_figure(
    rows: list[dict],
    start: datetime,
    end: datetime,
    width_px: int = 1100,
    title: str = "",
    now: datetime | None = None,
    colours: dict | None = None,
    breaks: list[dict] | None = None,
) -> go.Figure:
    """The timeline for the visible range `start`..`end`.

    `rows` are the events to draw (already filtered). `colours` maps class to
    colour; pass the map for the whole data set so filtering never repaints a
    class. `now` places the Today line (omit to leave it out). `breaks`
    (from timeline.find_breaks) are cut out of the axis.
    """
    breaks = breaks or []
    squash = lambda x: tl.squash(breaks, x)  # noqa: E731
    span = squash(tl.datetime_num(end)) - squash(tl.datetime_num(start))
    margin = dict(l=30, r=30, t=70 if title else 40, b=72 if breaks else 50)  # room for gap labels under the dates
    px_per_day = max(width_px - margin["l"] - margin["r"], 200) / span
    daily = px_per_day >= tl.DAILY_PX
    hourly = tl.tick_step(px_per_day)[0] == "hour"
    colours = colours if colours is not None else tl.class_colours(rows)

    # Lay out one extra screen either side so dragging reveals finished labels.
    pad = timedelta(days=span)
    shown = tl.in_view(rows, start - pad, end + pad)
    labels = tl.layout_labels([r for r in shown if not r.get("end")], px_per_day, not daily, squash)
    bands = tl.layout_bands([r for r in shown if r.get("end")], px_per_day, tl.datetime_num(start), squash)

    n_lines = max((len(p["lines"]) for p in labels), default=1)
    lane_px = n_lines * tl.LINE_PX + tl.LANE_GAP
    points_top = LABEL_BASE + max((p["lane"] for p in labels), default=0) * lane_px
    top = points_top + (10 + max(b["lane"] for b in bands) * tl.BAND_PX if bands else 0)

    fig = go.Figure()
    _lines_and_markers(fig, labels, colours, lane_px)
    _label_text(fig, labels, lane_px)
    if span <= 100:
        _weekends(fig, start - pad, end + pad, hourly, breaks)
    _bands(fig, bands, colours, points_top)
    if now is not None:
        _today(fig, now, hourly, top)
    _breaks(fig, breaks, top)

    fig.update_layout(
        title=dict(text=title, x=0.01, font=dict(size=20, color=tl.INK)) if title else None,
        height=top + TODAY_PX + margin["t"] + margin["b"],
        margin=margin,
        paper_bgcolor="#fff",
        plot_bgcolor="#fff",
        dragmode="pan",
        font=dict(family="Segoe UI, Helvetica, Arial, sans-serif", color=tl.INK),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
            xanchor="right",
            x=1,
            itemclick=False,
            itemdoubleclick=False,
            font=dict(color=tl.MUTED),
        ),
        showlegend=len({p["class"] for p in labels}) > 1,
        hoverlabel=dict(bgcolor="#fff", font=dict(color=tl.INK)),
        xaxis=dict(
            type="date",
            range=[start, end],
            showline=True,
            linecolor=tl.MUTED,
            ticks="outside",
            tickcolor=tl.MUTED,
            tickfont=dict(color=tl.MUTED),
            tickangle=0,  # never rotate: rotated labels grow the margin and squash the lanes
            automargin=False,
            showgrid=not daily or hourly,
            gridcolor=tl.GRID,
            rangebreaks=[dict(bounds=[tl.num_datetime(b["lo"]), tl.num_datetime(b["hi"])]) for b in breaks],
            **_ticks(px_per_day),
        ),
        yaxis=dict(range=[0, top + TODAY_PX], visible=False, fixedrange=True),
    )
    return fig
