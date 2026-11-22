"""Timeline Visualiser - pure logic (no web code, no plotting).

Sections, in the order data flows through them:

  dates   - read a date or date+time, convert to and from day numbers
  rows    - build, sort, read (CSV/Excel/paste) and write events
  edits   - merge loaded rows, apply table edits (used by app.py)
  filter  - hide classes, pick a timeline, search text
  view    - the visible date range: clamp, default, fit, what is in view
  text    - elapsed time, tooltips
  layout  - label and band lanes, axis tick choice

Everything here is unit-tested (tests/test_timeline.py) and mirrored in
web/index.html under the same names in camelCase (tests/test_web.py checks
that the two agree). Drawing lives in figure.py.

An event ("row") is a dict of strings:
  id           internal key for the table, random, never written to CSV
  date         "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"
  end          same forms, or "" for a single-date event; set = a band
  class        short bold heading; decides the colour
  description  free text
  ref          the CSV `id` column (stable id chosen by the user)
  timeline, owner, source, depends_on   optional text
  key          "yes" for a key event, else ""
"""

from __future__ import annotations

import io
import math
import re
import textwrap
import uuid
from datetime import date, datetime, timedelta

import pandas as pd

# ------------------------------------------------------------ constants ----
COLUMNS = ["date", "end", "class", "description"]  # always written to CSV
EXTRAS = ["id", "timeline", "owner", "source", "depends_on", "key"]  # written only when used
FIELD = {"id": "ref"}  # CSV column name -> row field, where they differ
EXTRA_FIELDS = [FIELD.get(c, c) for c in EXTRAS]
MIN_DAYS, MAX_DAYS, DEFAULT_DAYS = 1, 184, 31

# Colour-blind-checked categorical palette, assigned in fixed order.
# Classes beyond the 8th share the neutral OTHER colour (never a recycled hue).
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#8a897f"
INK, MUTED, GRID = "#1a1a19", "#6b6a62", "#e6e5df"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # date.weekday() order
KEY_MARK = "★ "  # shown before the class of a key event
WARN_MARK = "⚠ "  # shown before the class of an event with a dependency problem
TRUTHY = {"yes", "y", "true", "1", "x", "key", "★"}

# Header names accepted in files, mapped to the column they mean.
ALIASES = {
    "date": "date",
    "day": "date",
    "when": "date",
    "start": "date",
    "start date": "date",
    "from": "date",
    "end": "end",
    "end date": "end",
    "finish": "end",
    "to": "end",
    "until": "end",
    "class": "class",
    "title": "class",
    "type": "class",
    "category": "class",
    "description": "description",
    "desc": "description",
    "details": "description",
    "text": "description",
    "activity": "activity",
    "event": "activity",
    "id": "ref",
    "ref": "ref",
    "timeline": "timeline",
    "owner": "owner",
    "who": "owner",
    "responsible": "owner",
    "source": "source",
    "reference": "source",
    "evidence": "source",
    "depends_on": "depends_on",
    "depends on": "depends_on",
    "key": "key",
    "important": "key",
}
DATE_FORMATS = [
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%d%b%Y",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d.%m.%y",
    "%d/%m/%y",
]
NO_YEAR_FORMATS = ["%d-%b", "%d %b", "%d %B", "%d.%m.", "%d/%m"]
# "<date> 14:30", "<date>T14:30:00" - the time is split off, the rest read as a date.
TIME_RE = re.compile(r"^(.*?)[ T]+(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?Z?$")


# ---------------------------------------------------------------- dates ----
def _missing(value) -> bool:
    """True for None, NaN and NaT (empty spreadsheet cells)."""
    return value is None or (not isinstance(value, str) and bool(pd.isna(value)))


def _cell(value) -> str:
    return "" if _missing(value) else str(value).strip()


def _parse_day(text: str) -> date | None:
    """Read a date without a time. ISO first, then day-first forms."""
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


def _when(day: date, hour: int = 0, minute: int = 0) -> str:
    """Canonical text form. Midnight means "no time given"."""
    return day.isoformat() + (f" {hour:02d}:{minute:02d}" if hour or minute else "")


def parse_when(value) -> str | None:
    """Return "YYYY-MM-DD" or "YYYY-MM-DD HH:MM", or None if unreadable.

    ISO (2025-03-10) is preferred; day-first forms such as 10-Mar-2025,
    10.03.2025 and 10-Mar (current year) are also accepted, each optionally
    followed by a 24-hour time (14:30). A time of 00:00 counts as no time.
    """
    if _missing(value):
        return None
    if isinstance(value, datetime):
        return _when(value.date(), value.hour, value.minute)
    if isinstance(value, date):
        return _when(value)
    text, hour, minute = str(value).strip(), 0, 0
    match = TIME_RE.match(text)
    if match:
        text, hour, minute = match[1].strip(), int(match[2]), int(match[3])
        if hour > 23 or minute > 59:
            return None
    day = _parse_day(text)
    return None if day is None else _when(day, hour, minute)


def parse_date(value) -> date | None:
    """The date part only (any time of day is dropped)."""
    when = parse_when(value)
    return date.fromisoformat(when[:10]) if when else None


def has_time(when: str) -> bool:
    return len(when) > 10


def when_num(when: str) -> float:
    """Day number (whole days, plus a fraction for the time of day)."""
    day = date.fromisoformat(when[:10]).toordinal()
    return day + (int(when[11:13]) * 60 + int(when[14:16])) / 1440 if has_time(when) else float(day)


def num_when(num: float) -> str:
    """Inverse of when_num, rounded to the minute."""
    minutes = round(num * 1440)
    return _when(date.fromordinal(minutes // 1440), minutes % 1440 // 60, minutes % 60)


def num_datetime(num: float) -> datetime:
    return datetime.fromordinal(int(num // 1)) + timedelta(days=num % 1)


def datetime_num(moment: datetime) -> float:
    return moment.toordinal() + (moment - datetime.combine(moment.date(), datetime.min.time())).total_seconds() / 86400


def fmt_when(when: str, weekday: bool = False) -> str:
    """ "06 Nov 2026", with "Fri " in front and " 14:30" behind when asked for / present.

    Month and weekday names are fixed English, so output is the same on every machine.
    """
    day = date.fromisoformat(when[:10])
    text = f"{day.day:02d} {MON[day.month - 1]} {day.year}"
    return (DOW[day.weekday()] + " " if weekday else "") + text + when[10:]


# ----------------------------------------------------------------- rows ----
def make_row(day, cls: str = "", description: str = "", row_id: str | None = None, end=None, **extra) -> dict:
    """One event. With an end it is a band; without, a single-date event.

    `day` and `end` may be a date, a datetime or text. `extra` holds any of
    EXTRA_FIELDS. A band entered backwards is turned round; an end equal to
    the start is dropped.
    """
    start, finish = parse_when(day), parse_when(end)
    if start is None:
        raise ValueError(f"not a date: {day!r}")
    if finish and when_num(finish) < when_num(start):
        start, finish = finish, start
    row = {
        "id": row_id or uuid.uuid4().hex[:10],
        "date": start,
        "end": finish if finish and finish != start else "",
        "class": str(cls or "").strip().rstrip(":").strip(),
        "description": str(description or "").strip(),
    }
    for field in EXTRA_FIELDS:
        row[field] = _cell(extra.get(field))
    row["key"] = "yes" if row["key"].lower() in TRUTHY else ""
    return row


def sort_rows(rows: list[dict]) -> list[dict]:
    """Chronological; ties broken by end, class, description so the order is stable."""
    return sorted(rows, key=lambda r: (r["date"], r.get("end") or "", r["class"].lower(), r["description"].lower()))


def rows_from_frame(raw: pd.DataFrame) -> tuple[list[dict], int]:
    """Turn a header-less DataFrame into event rows. Returns (rows, rejected).

    A first row whose first cell is not a date is treated as a header and may
    name any column in ALIASES, in any order. Without a header: 2 columns =
    date + "Class: description", 3 = date, class, description;
    4 = date, end, class, description.
    """
    raw = raw.dropna(how="all")
    if raw.empty:
        return [], 0
    first = raw.iloc[0].tolist()
    if parse_when(first[0]) is None:  # header row
        names = [ALIASES.get(_cell(c).lower(), f"_{i}") for i, c in enumerate(first)]
        raw = raw.iloc[1:]
    else:
        names = {2: ["date", "activity"], 3: ["date", "class", "description"]}.get(raw.shape[1], COLUMNS)
        names = (names + [f"_{i}" for i in range(raw.shape[1])])[: raw.shape[1]]
    raw.columns = names
    rows, rejected = [], 0
    for rec in raw.to_dict("records"):
        day = parse_when(rec.get("date"))
        cls, desc = _cell(rec.get("class")), _cell(rec.get("description"))
        if "activity" in rec and not cls:
            head, sep, tail = _cell(rec["activity"]).partition(":")
            cls, desc = (head, tail) if sep else ("", head)
        if day is None or not (cls or desc):
            rejected += 1
            continue
        extra = {f: rec.get(f) for f in EXTRA_FIELDS}
        rows.append(make_row(day, cls, desc, end=rec.get("end"), **extra))
    return sort_rows(rows), rejected


def rows_from_text(text: str) -> tuple[list[dict], int]:
    """Parse pasted or uploaded CSV/TSV text (tab, semicolon or comma separated)."""
    if not text.strip():
        return [], 0
    sep = "\t" if "\t" in text else (";" if text.count(";") > text.count(",") else ",")
    raw = pd.read_csv(io.StringIO(text), sep=sep, header=None, dtype=str, skipinitialspace=True, keep_default_na=False)
    return rows_from_frame(raw)


def rows_from_excel(content: bytes) -> tuple[list[dict], int]:
    """First sheet of an .xlsx file."""
    return rows_from_frame(pd.read_excel(io.BytesIO(content), header=None))


def to_csv(rows: list[dict]) -> str:
    """All rows in date order. Optional columns appear only if some row uses them,
    so a plain 4-column file is written back as a plain 4-column file."""
    rows = sort_rows(rows)
    columns = COLUMNS + [c for c in EXTRAS if any(r.get(FIELD.get(c, c)) for r in rows)]
    records = [{c: r.get(FIELD.get(c, c)) or "" for c in columns} for r in rows]
    return pd.DataFrame(records, columns=columns).to_csv(index=False, lineterminator="\n")


def class_colours(rows: list[dict]) -> dict[str, str]:
    """Colour follows the class name (alphabetical order), not what is on screen."""
    classes = sorted({r["class"] for r in rows if r["class"]}, key=str.lower)
    return {c: PALETTE[i] if i < len(PALETTE) else OTHER for i, c in enumerate(classes)}


# ---------------------------------------------------------------- edits ----
def _same_event(row: dict) -> tuple:
    return (row["date"], row.get("end") or "", row["class"], row["description"])


def merge_new(rows: list[dict], new: list[dict]) -> tuple[list[dict], list[dict]]:
    """Add loaded or pasted rows, skipping exact duplicates. Returns (all rows, rows added)."""
    seen = {_same_event(r) for r in rows}
    fresh = [r for r in new if _same_event(r) not in seen]
    return sort_rows(rows + fresh), fresh


def apply_table(rows: list[dict], table: list[dict], previous: list[dict] | None) -> tuple[list[dict], str]:
    """Apply an edit made in the on-screen table. Returns (all rows, message).

    The table shows only part of the data, so rows are matched by id: rows that
    were in `previous` but not in `table` were deleted; rows in `table` are
    rebuilt from their cells. An unreadable start date keeps the old date; an
    unreadable end date clears the end.
    """
    by_id = {r["id"]: r for r in rows}
    kept = {r.get("id") for r in table}
    for old in previous or []:
        if old.get("id") not in kept:
            by_id.pop(old.get("id"), None)
    message = ""
    for cells in table:
        old = by_id.get(cells.get("id"))
        day = parse_when(cells.get("date"))
        if day is None:
            message = (
                f"'{cells.get('date')}' is not a date - use YYYY-MM-DD or YYYY-MM-DD HH:MM. Kept the previous date."
            )
            if old is None:
                continue
            day = old["date"]
        end = parse_when(cells.get("end"))
        if end is None and _cell(cells.get("end")):
            message = f"'{cells.get('end')}' is not a date - end date cleared."
        merged = {**(old or {}), **cells}  # cells not shown in the table keep their old value
        extra = {f: merged.get(f) for f in EXTRA_FIELDS}
        new = make_row(day, merged.get("class") or "", merged.get("description") or "", cells.get("id"), end, **extra)
        by_id[new["id"]] = new
    return sort_rows(list(by_id.values())), message


# --------------------------------------------------------------- filter ----
def timelines(rows: list[dict]) -> list[str]:
    """Distinct timeline names in use, A-Z."""
    return sorted({r.get("timeline") or "" for r in rows} - {""}, key=str.lower)


def filter_rows(rows: list[dict], hidden=(), timeline: str = "", text: str = "") -> list[dict]:
    """Rows left after hiding classes, picking one timeline and searching.

    `hidden` is a list of class names to leave out. `text` matches anywhere in
    the class, description or optional fields, ignoring case. Filters only
    change what is shown; the stored data and the CSV download are not touched.
    """
    hidden, needle = set(hidden or ()), (text or "").strip().lower()
    out = []
    for r in rows:
        if r["class"] in hidden or (timeline and (r.get("timeline") or "") != timeline):
            continue
        hay = " ".join([r["class"], r["description"]] + [r.get(f) or "" for f in EXTRA_FIELDS[:-1]]).lower()
        if needle in hay:
            out.append(r)
    return out


# ----------------------------------------------------------------- view ----
def clamp_view(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Keep the visible span between one day and six months, same centre."""
    span = (end - start).total_seconds() / 86400
    clamped = min(max(span, MIN_DAYS), MAX_DAYS)
    if clamped != span:
        centre = start + (end - start) / 2
        start = centre - timedelta(days=clamped / 2)
        end = centre + timedelta(days=clamped / 2)
    return start, end


def default_view(rows: list[dict], today: date | None = None) -> tuple[datetime, datetime]:
    """One month: the current month if it has events, else the first event's month."""
    today = today or date.today()
    months = {r["date"][:7] for r in rows}
    if rows and today.isoformat()[:7] not in months:
        today = date.fromisoformat(rows[0]["date"][:10])
    start = datetime(today.year, today.month, 1)
    return start, start + timedelta(days=DEFAULT_DAYS)


def fit_span(rows: list[dict]) -> tuple[float, float] | None:
    """(start day number, span in days) that shows every event, or None without rows.

    5% of the span is left free before the first event and 10% after the last
    (labels run to the right). Data longer than MAX_DAYS shows its first six months.
    """
    if not rows:
        return None
    lo = min(when_num(r["date"]) for r in rows)
    hi = max(when_num(r.get("end") or r["date"]) for r in rows)
    span = min(max((hi - lo) / 0.85, MIN_DAYS), MAX_DAYS)
    return lo - span * 0.05, span


def fit_view(rows: list[dict]) -> tuple[datetime, datetime]:
    fitted = fit_span(rows)
    if fitted is None:
        return default_view(rows)
    return num_datetime(fitted[0]), num_datetime(fitted[0] + fitted[1])


def in_span(rows: list[dict], lo: float, hi: float) -> list[dict]:
    """Events between two day numbers.

    An event with a time is a point; one without occupies its whole day, so it
    counts as visible whenever any part of that day is.
    """
    out = []
    for r in rows:
        last = r.get("end") or r["date"]
        first, final = when_num(r["date"]), when_num(last) + (0 if has_time(last) else 1)
        if first <= hi and (final > lo or first >= lo):
            out.append(r)
    return out


def in_view(rows: list[dict], start: datetime, end: datetime) -> list[dict]:
    """Events on screen: single dates inside the range, bands that overlap it."""
    return in_span(rows, datetime_num(start), datetime_num(end))


# -------------------------------------------------------------- breaks ----
# "Compress gaps": a stretch with no activity that is at least GAP_SHARE of the
# visible span is cut out of the axis, leaving PAD_SHARE of the span on each side.
# Only event dates and band starts/ends count as activity, so a band running
# through a gap is shortened with it. Positions on a compressed axis are
# "display" day numbers: real day numbers minus the hidden time before them.
GAP_SHARE, PAD_SHARE = 0.3, 0.05


def find_breaks(rows: list[dict], span: float, px_per_day: float, expanded=()) -> list[dict]:
    """The stretches to cut out, in date order: {key, lo, hi, gap}.

    `lo`..`hi` is the hidden part (real day numbers); `gap` is the whole quiet
    stretch in days, for the label; `key` names the gap so it can be expanded.
    Breaks only fall between two moments of activity, so nothing is cut before
    the first event or after the last. A band starting just before a gap keeps
    room for its label.
    """
    moments: dict[float, float] = {}  # moment -> room needed to its right, in days
    for r in rows:
        moments.setdefault(when_num(r["date"]), 0)
        if r.get("end"):
            name = band_name(r)
            room = ((len(name) + len(r["description"]) + 2) * CHAR_PX + 16) / px_per_day
            start = when_num(r["date"])
            moments[start] = max(moments[start], room)
            moments.setdefault(when_num(r["end"]), 0)
    times, pad, out = sorted(moments), span * PAD_SHARE, []
    for a, b in zip(times, times[1:], strict=False):
        key = f"{num_when(a)}|{num_when(b)}"
        lo, hi = a + max(pad, moments[a]), b - pad
        if b - a >= span * GAP_SHARE and hi > lo and key not in expanded:
            out.append({"key": key, "lo": lo, "hi": hi, "gap": b - a})
    return out


def squash(breaks: list[dict], x: float) -> float:
    """Real day number -> display day number (hidden time removed)."""
    d = x
    for b in breaks:
        if x <= b["lo"]:
            break
        d -= min(x, b["hi"]) - b["lo"]
    return d


def unsquash(breaks: list[dict], d: float) -> float:
    """Display day number -> real day number. A break's own point maps to its start."""
    for b in breaks:
        if d <= b["lo"]:
            break
        d += b["hi"] - b["lo"]
    return d


def break_text(days: float) -> str:
    """Label for a compressed gap: "7 h", "15 days", "1 month", "2.5 years"."""
    half_up = math.floor  # same rounding as Math.round in the web version
    if days < 1:
        return f"{half_up(days * 24 + 0.5)} h"
    if days < 60:
        n = half_up(days + 0.5)
        return f"{n} day" + ("s" if n != 1 else "")
    if days < 730:
        return f"{half_up(days / 30.44 + 0.5)} months"
    return f"{half_up(days / 365.25 * 10 + 0.5) / 10:g} years"


# --------------------------------------------------------- dependencies ----
def dependency_issues(rows: list[dict]) -> dict[str, list[str]]:
    """Problems with `depends_on`, by row id. Dates are never changed, only flagged.

    `depends_on` lists the `id`s (CSV column) of events this one follows,
    separated by commas, semicolons or spaces. An event is flagged when it
    starts before one of them is due (its end, or its date if it has no end),
    or when it names an id that is not in the data.
    """
    by_ref = {r["ref"]: r for r in rows if r.get("ref")}
    out: dict[str, list[str]] = {}
    for r in rows:
        for ref in re.split(r"[\s,;]+", r.get("depends_on") or ""):
            before = by_ref.get(ref)
            if not ref:
                continue
            if before is None:
                message = f"Depends on {ref}, which is not in the data"
            elif when_num(r["date"]) < when_num(before.get("end") or before["date"]):
                message = f"Starts before {ref} is due ({fmt_when(before.get('end') or before['date'])})"
            else:
                continue
            out.setdefault(r["id"], []).append(message)
    return out


def flag_rows(rows: list[dict], issues: dict[str, list[str]]) -> list[dict]:
    """Copies of the rows, with `warn` (list of problems) on those that have any."""
    return [{**r, "warn": issues[r["id"]]} if r["id"] in issues else r for r in rows]


# ----------------------------------------------------------------- text ----
def span_text(a: str, b: str) -> str:
    """Elapsed time from a to b: "3 d", "1 d 4 h", "2 h 15 min".

    If either side has no time of day, whole calendar days are counted.
    With times, the two largest non-zero units are shown.
    """
    if not (has_time(a) and has_time(b)):
        return f"{date.fromisoformat(b[:10]).toordinal() - date.fromisoformat(a[:10]).toordinal()} d"
    minutes = round((when_num(b) - when_num(a)) * 1440)
    parts = [(minutes // 1440, "d"), (minutes % 1440 // 60, "h"), (minutes % 60, "min")]
    shown = [f"{n} {unit}" for n, unit in parts if n][:2]
    return " ".join(shown) or "0 min"


def with_gaps(rows: list[dict]) -> list[dict]:
    """Copy of the rows, in date order, each with `gap`: time since the previous row started."""
    out, previous = [], None
    for r in sort_rows(rows):
        out.append({**r, "gap": "+" + span_text(previous["date"], r["date"]) if previous else ""})
        previous = r
    return out


def tip_lines(row: dict) -> list[str]:
    """Tooltip: when, class, description, then owner / source / timeline if filled in."""
    if row.get("end"):
        when = f"{fmt_when(row['date'])} – {fmt_when(row['end'])} ({span_text(row['date'], row['end'])})"
    else:
        when = fmt_when(row["date"], weekday=True)
    lines = [when, (KEY_MARK if row.get("key") else "") + (row["class"] or "Event"), row["description"]]
    for label, field in (("Owner", "owner"), ("Source", "source"), ("Timeline", "timeline")):
        if row.get(field):
            lines.append(f"{label}: {row[field]}")
    return lines + [WARN_MARK + w for w in row.get("warn") or []]


def band_name(row: dict) -> str:
    """Bold part of a band label: marks, then the class."""
    return (WARN_MARK if row.get("warn") else "") + (KEY_MARK if row.get("key") else "") + (row["class"] or "Event")


# --------------------------------------------------------------- layout ----
CHAR_PX, LINE_PX, LANE_GAP, MAX_LANES, BAND_PX = 7.0, 16, 10, 5, 28
# Detail levels, tried in order until the labels fit in MAX_LANES lanes:
# (wrap width in characters, max description lines)
LEVELS = [(34, 2), (24, 1), (0, 0)]
DAILY_PX = 22  # px per day needed for a tick label on every day
HOUR_STEPS, HOUR_TICK_PX = [1, 2, 3, 6, 12], 44  # hour ticks need this many px each


def tick_step(px_per_day: float) -> tuple[str, int]:
    """Axis tick spacing for a zoom level: ("hour", n), ("day", 1), ("week", 1) or ("month", 1)."""
    for hours in HOUR_STEPS:
        if px_per_day * hours / 24 >= HOUR_TICK_PX:
            return "hour", hours
    if px_per_day >= DAILY_PX:
        return "day", 1
    return ("week", 1) if px_per_day * 7 >= 50 else ("month", 1)


def label_head(row: dict, show_date: bool = False) -> str:
    """Bold first line of a label: "★ Class · 06 Nov 14:30" (star, date and time only when needed)."""
    head = band_name(row)
    extra = [fmt_when(row["date"][:10])[:6]] if show_date else []
    if has_time(row["date"]):
        extra.append(row["date"][11:])
    return head + (" · " + " ".join(extra) if extra else "")


def _label_lines(row: dict, wrap: int, max_lines: int, show_date: bool) -> list[str]:
    body = []
    if wrap and row["description"]:
        body = textwrap.wrap(row["description"], wrap, max_lines=max_lines, placeholder="…")
    return [label_head(row, show_date)] + body


def layout_labels(rows: list[dict], px_per_day: float, show_date: bool = False, pos=None) -> list[dict]:
    """Give each single-date event a text label and a lane (1 = nearest the axis).

    Labels sit to the right of their date line. Each one takes the lowest lane
    whose previous label has ended, so labels never overlap. If that needs more
    than MAX_LANES lanes, the text is shortened and the layout retried.
    `pos` turns a day number into a position on the axis (see `squash`).
    """
    pos = pos or (lambda x: x)
    placed: list[dict] = []
    for wrap, max_lines in LEVELS:
        placed, lane_end = [], []
        for row in sort_rows(rows):
            lines = _label_lines(row, wrap, max_lines, show_date)
            x = pos(when_num(row["date"]))
            width = (max(len(s) for s in lines) * CHAR_PX + 16) / px_per_day
            lane = next((i for i, e in enumerate(lane_end) if e <= x), len(lane_end))
            if lane == len(lane_end):
                lane_end.append(0)
            lane_end[lane] = x + width
            placed.append({**row, "lines": lines, "lane": lane + 1, "x": x, "x_end": x + width})
        if len(lane_end) <= MAX_LANES:
            break
    return placed


def layout_bands(rows: list[dict], px_per_day: float, view_start: float, pos=None) -> list[dict]:
    """Give each band (event with an end) a lane and a label position.

    The label sits at the band's start, or at the left edge of the view when
    the band started earlier. A lane is reused once the previous band and its
    label have both ended. `pos` as in `layout_labels`.
    """
    pos = pos or (lambda x: x)
    placed, lane_end = [], []
    for row in sort_rows(rows):
        x0, x1 = when_num(row["date"]), when_num(row["end"])
        label_x = min(max(x0, view_start), x1)
        name = band_name(row)
        chars = len(name) + len(row["description"]) + 2
        right = max(pos(x1), pos(label_x) + (chars * CHAR_PX + 16) / px_per_day)
        lane = next((i for i, e in enumerate(lane_end) if e <= pos(x0)), len(lane_end))
        if lane == len(lane_end):
            lane_end.append(0)
        lane_end[lane] = right
        placed.append({**row, "lane": lane + 1, "label_x": label_x, "x": x0, "x_end": right, "name": name})
    return placed
