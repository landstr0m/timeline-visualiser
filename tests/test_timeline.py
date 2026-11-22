import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

import timeline as tl
from figure import build_figure


def test_parse_date_formats():
    assert tl.parse_date("2025-03-10") == date(2025, 3, 10)
    assert tl.parse_date("10-Mar-2025") == date(2025, 3, 10)
    assert tl.parse_date("10.03.2025") == date(2025, 3, 10)
    assert tl.parse_date("10-Mar") == date(date.today().year, 3, 10)
    assert tl.parse_date(datetime(2025, 3, 10, 8)) == date(2025, 3, 10)
    assert tl.parse_date("soon") is None and tl.parse_date("") is None


def test_text_with_header_is_sorted_and_bad_rows_counted():
    rows, bad = tl.rows_from_text("Date,Title,Description\n2025-03-12,Results,B\n2025-03-10,Approval,A\nnope,X,Y\n")
    assert [r["date"] for r in rows] == ["2025-03-10", "2025-03-12"]
    assert rows[0]["class"] == "Approval" and bad == 1


def test_two_column_activity_format_and_tabs():
    rows, _ = tl.rows_from_text("10-Mar-2025\tResults: buffer data expected\n")
    assert rows[0]["class"] == "Results" and rows[0]["description"] == "buffer data expected"


def test_csv_round_trip():
    rows, _ = tl.rows_from_text('2025-03-10,Results,"a, b"\n')
    again, _ = tl.rows_from_text(tl.to_csv(rows))
    assert [(r["date"], r["end"], r["class"], r["description"]) for r in again] == [
        ("2025-03-10", "", "Results", "a, b")
    ]


def test_clamp_view_limits():
    s = datetime(2025, 3, 1)
    lo = tl.clamp_view(s, s + timedelta(days=1))
    hi = tl.clamp_view(s, s + timedelta(days=900))
    assert (lo[1] - lo[0]).days == tl.MIN_DAYS and (hi[1] - hi[0]).days == tl.MAX_DAYS


def test_in_view_filters_by_range():
    rows, _ = tl.rows_from_text("2025-03-10,A,x\n2025-04-10,A,y\n")
    assert len(tl.in_view(rows, datetime(2025, 3, 1), datetime(2025, 3, 31))) == 1


def test_colour_is_stable_per_class():
    rows, _ = tl.rows_from_text("2025-03-10,Results,x\n2025-03-11,Approval,y\n")
    assert tl.class_colours(rows)["Results"] == tl.class_colours(rows[::-1])["Results"]


def test_labels_never_overlap_and_shorten_when_crowded():
    rows = [
        tl.make_row(date(2025, 3, 1 + i % 5), "Results", "a fairly long description of the event") for i in range(20)
    ]
    placed = tl.layout_labels(rows, px_per_day=30)
    for a in placed:
        for b in placed:
            if a is not b and a["lane"] == b["lane"]:
                assert a["x_end"] <= b["x"] or b["x_end"] <= a["x"]
    roomy = tl.layout_labels(rows[:2], px_per_day=30)
    assert len(roomy[0]["lines"]) > len(placed[0]["lines"])


def test_bands_parse_overlap_view_and_label_follows_view():
    rows, _ = tl.rows_from_text(
        "start,end,class,description\n2025-03-01,2025-03-20,Phase,Run\n2025-03-25,2025-03-21,Phase,Swapped\n"
    )
    assert rows[0]["end"] == "2025-03-20" and (rows[1]["date"], rows[1]["end"]) == ("2025-03-21", "2025-03-25")
    assert len(tl.in_view(rows, datetime(2025, 3, 10), datetime(2025, 3, 12))) == 1  # band spans the view
    headerless, _ = tl.rows_from_text("2025-03-01,2025-03-20,Phase,Run\n2025-03-05,,Results,x\n")
    assert headerless[0]["end"] == "2025-03-20" and headerless[1]["end"] == ""
    band = tl.layout_bands(rows[:1], 30, date(2025, 3, 10).toordinal())[0]
    assert band["label_x"] == date(2025, 3, 10).toordinal()
    assert build_figure(rows, datetime(2025, 3, 1), datetime(2025, 4, 1)).layout.shapes


# ---- v1.1: times of day, optional columns, filters, gaps, fit, undo helpers ----
def test_times_of_day_are_read_sorted_and_round_trip():
    assert tl.parse_when("2025-03-10 14:30") == "2025-03-10 14:30"
    assert tl.parse_when("10.03.2025 8:05") == "2025-03-10 08:05"
    assert tl.parse_when("2025-03-10T14:30:00") == "2025-03-10 14:30"
    assert tl.parse_when("10-Mar-2025 00:00") == "2025-03-10"  # midnight = no time
    assert tl.parse_when(datetime(2025, 3, 10, 8)) == "2025-03-10 08:00"
    assert tl.parse_when("2025-03-10 25:00") is None
    rows, _ = tl.rows_from_text("2025-03-10 14:30,A,late\n2025-03-10,A,whole day\n2025-03-10 09:00,A,early\n")
    assert [r["description"] for r in rows] == ["whole day", "early", "late"]
    again, _ = tl.rows_from_text(tl.to_csv(rows))
    assert [r["date"] for r in again] == [r["date"] for r in rows]
    assert tl.num_when(tl.when_num("2025-03-10 14:30")) == "2025-03-10 14:30"


def test_optional_columns_kept_and_plain_files_stay_plain():
    plain, _ = tl.rows_from_text("2025-03-10,Results,x\n")
    assert tl.to_csv(plain).splitlines()[0] == "date,end,class,description"
    text = "date,class,description,owner,key,id,source\n2025-03-10,Results,x,Ana,Y,E1,Batch record p4\n2025-03-11,Results,y,,,,\n"
    rows, _ = tl.rows_from_text(text)
    assert (rows[0]["owner"], rows[0]["key"], rows[0]["ref"], rows[0]["source"]) == (
        "Ana",
        "yes",
        "E1",
        "Batch record p4",
    )
    out = tl.to_csv(rows)
    assert out.splitlines()[0] == "date,end,class,description,id,owner,source,key"
    again, _ = tl.rows_from_text(out)
    assert tl.to_csv(again) == out


def test_filter_by_class_timeline_and_text():
    rows, _ = tl.rows_from_text(
        "date,class,description,timeline,owner\n2025-03-10,Results,pH data,Line 1,Ana\n"
        "2025-03-11,Review,Draft,Line 2,Ben\n2025-03-12,Results,Bioburden,Line 2,Ana\n"
    )
    assert tl.timelines(rows) == ["Line 1", "Line 2"]
    assert len(tl.filter_rows(rows)) == 3
    assert [r["description"] for r in tl.filter_rows(rows, hidden=["Results"])] == ["Draft"]
    assert len(tl.filter_rows(rows, timeline="Line 2")) == 2
    assert [r["description"] for r in tl.filter_rows(rows, text="ANA")] == ["pH data", "Bioburden"]
    assert tl.filter_rows(rows, ["Review"], "Line 2", "bio")[0]["description"] == "Bioburden"


def test_elapsed_time_and_gaps():
    assert tl.span_text("2025-03-10", "2025-03-13") == "3 d"
    assert tl.span_text("2025-03-10 09:15", "2025-03-10 11:40") == "2 h 25 min"
    assert tl.span_text("2025-03-10 09:00", "2025-03-11 13:00") == "1 d 4 h"
    assert tl.span_text("2025-03-10 09:00", "2025-03-11") == "1 d"  # one side has no time: whole days
    rows, _ = tl.rows_from_text("2025-03-10 09:15,A,x\n2025-03-10 11:40,A,y\n2025-03-14,A,z\n")
    assert [r["gap"] for r in tl.with_gaps(rows)] == ["", "+2 h 25 min", "+4 d"]


def test_in_view_treats_timed_events_as_points_and_dated_ones_as_whole_days():
    rows, _ = tl.rows_from_text("2025-03-10 08:00,A,early\n2025-03-10 20:00,A,late\n2025-03-10,A,all day\n")
    seen = tl.in_view(rows, datetime(2025, 3, 10, 12), datetime(2025, 3, 11, 12))
    assert sorted(r["description"] for r in seen) == ["all day", "late"]


def test_fit_view_shows_everything_within_zoom_limits():
    rows, _ = tl.rows_from_text("2025-03-10,A,x\n2025-03-20,A,y\n")
    start, end = tl.fit_view(rows)
    assert start < datetime(2025, 3, 10) and end > datetime(2025, 3, 20)
    assert len(tl.in_view(rows, start, end)) == 2
    one, _ = tl.rows_from_text("2025-03-10 09:00,A,x\n")
    start, end = tl.fit_view(one)
    assert (end - start).total_seconds() / 86400 == pytest.approx(tl.MIN_DAYS)
    long, _ = tl.rows_from_text("2025-01-01,A,x\n2027-01-01,A,y\n")
    start, end = tl.fit_view(long)
    assert (end - start).days == tl.MAX_DAYS and tl.in_view(long, start, end)[0]["description"] == "x"


def test_tick_step_goes_from_hours_to_months():
    assert tl.tick_step(1040) == ("hour", 2)  # one day on a wide screen
    assert tl.tick_step(1100) == ("hour", 1)
    assert tl.tick_step(150) == ("hour", 12)  # one week
    assert tl.tick_step(34) == ("day", 1)  # one month
    assert tl.tick_step(11) == ("week", 1)
    assert tl.tick_step(5) == ("month", 1)


def test_key_events_and_times_show_in_labels_and_tooltips():
    row = tl.make_row("2026-11-03 09:15", "Deviation", "Alarm", owner="Ana", source="Alarm log", key="x")
    assert tl.label_head(row) == "★ Deviation · 09:15"
    assert tl.label_head(row, show_date=True) == "★ Deviation · 03 Nov 09:15"
    assert tl.tip_lines(row) == ["Tue 03 Nov 2026 09:15", "★ Deviation", "Alarm", "Owner: Ana", "Source: Alarm log"]
    band = tl.make_row("2026-11-03", "Phase", "Run", end="2026-11-27")
    assert tl.tip_lines(band)[0] == "03 Nov 2026 – 27 Nov 2026 (24 d)"


def test_merge_new_skips_duplicates():
    rows, _ = tl.rows_from_text("2025-03-10,A,x\n")
    new, _ = tl.rows_from_text("2025-03-10,A,x\n2025-03-11,A,y\n")
    merged, fresh = tl.merge_new(rows, new)
    assert len(merged) == 2 and [r["description"] for r in fresh] == ["y"]


def test_apply_table_edits_deletes_and_rejects_bad_dates():
    rows, _ = tl.rows_from_text(
        "date,class,description,owner\n2025-03-10,A,x,Ana\n2025-03-11,A,y,Ben\n2025-03-12,A,z,\n"
    )
    a, b, c = rows
    table = [
        {"id": a["id"], "date": "soon", "end": "", "class": "A", "description": "x2"},
        dict(b, end="2025-03-15 12:00"),
    ]
    out, message = tl.apply_table(rows, table, previous=[a, b, c])  # c was deleted in the table
    assert [r["description"] for r in out] == ["x2", "y"]
    assert out[0]["date"] == "2025-03-10" and "not a date" in message  # bad date: old one kept
    assert out[0]["owner"] == "Ana"  # a column not shown in the table keeps its value
    assert out[1]["end"] == "2025-03-15 12:00"


def test_figure_has_today_line_key_marker_and_stable_colours():
    rows, _ = tl.rows_from_text("date,class,description,key\n2025-03-10 09:00,Deviation,x,yes\n2025-03-11,Results,y,\n")
    colours = tl.class_colours(rows)
    fig = build_figure(
        rows[1:], datetime(2025, 3, 1), datetime(2025, 4, 1), now=datetime(2025, 3, 12, 15), colours=colours
    )
    assert fig.data[0].line.color == colours["Results"]  # filtering a class away must not repaint the rest
    assert any(a.text == "Today" for a in fig.layout.annotations)
    fig = build_figure(rows, datetime(2025, 3, 10), datetime(2025, 3, 11))
    assert "diamond" in fig.data[0].marker.symbol and fig.layout.xaxis.dtick == 2 * 3600000
    assert not any(a.text == "Today" for a in fig.layout.annotations)


# ------------------------------------------------------------ compressed gaps ----
def _rows(*specs):
    return [tl.make_row(d, c, "x", end=e) for d, e, c in specs]


def test_breaks_cut_long_gaps_only_between_events():
    rows = _rows(("2026-01-01", None, "A"), ("2026-01-16", None, "A"), ("2026-01-25", None, "A"))
    breaks = tl.find_breaks(rows, 30, 30)
    # 15 days and 9 days are both at least 30% of a 30-day view; 5% (1.5 days) stays either side
    assert [b["gap"] for b in breaks] == [15, 9]
    first = tl.when_num("2026-01-01")
    assert breaks[0]["lo"] == pytest.approx(first + 1.5) and breaks[0]["hi"] == pytest.approx(first + 13.5)
    assert breaks[0]["key"] == "2026-01-01|2026-01-16"
    assert tl.find_breaks(rows, 60, 30) == []  # at 2 months neither gap is long enough
    assert len(tl.find_breaks(rows, 30, 30, expanded=["2026-01-01|2026-01-16"])) == 1


def test_band_through_a_gap_is_compressed_and_keeps_label_room():
    rows = _rows(("2026-01-01", "2026-03-01", "Phase"))
    (b,) = tl.find_breaks(rows, 30, 30)  # a band's start and end are the activity
    assert b["gap"] == 59
    room = (len("Phase") + len("x") + 2) * tl.CHAR_PX + 16  # px; 30 px per day
    assert b["lo"] == pytest.approx(tl.when_num("2026-01-01") + max(1.5, room / 30))


def test_squash_and_unsquash_are_inverse():
    breaks = [{"lo": 10, "hi": 20}, {"lo": 30, "hi": 40}]
    assert [tl.squash(breaks, x) for x in (5, 10, 15, 20, 25, 45)] == [5, 10, 10, 10, 15, 25]
    assert [tl.unsquash(breaks, d) for d in (5, 10, 15, 25)] == [5, 10, 25, 45]


def test_break_text():
    assert [tl.break_text(d) for d in (0.3, 1, 15, 59.6, 92, 800)] == [
        "7 h",
        "1 day",
        "15 days",
        "60 days",
        "3 months",
        "2.2 years",
    ]


# --------------------------------------------------------------- dependencies ----
def test_dependency_flags_never_move_dates():
    text = "id,date,end,class,description,depends_on\nA,2025-03-01,2025-03-10,Phase,Run,\n"
    text += 'B,2025-03-05,,Review,Early,A\nC,2025-03-10,,Review,On time,A\nD,2025-03-12,,Review,Late,"A, X"\n'
    rows, _ = tl.rows_from_text(text)
    issues = tl.dependency_issues(rows)
    by_ref = {r["ref"]: issues.get(r["id"], []) for r in rows}
    assert by_ref == {
        "A": [],
        "B": ["Starts before A is due (10 Mar 2025)"],  # due = the end of A's band
        "C": [],
        "D": ["Depends on X, which is not in the data"],
    }
    flagged = tl.flag_rows(rows, issues)
    early = next(r for r in flagged if r["ref"] == "B")
    assert early["date"] == "2025-03-05"  # flagged, not moved
    assert tl.label_head(early).startswith(tl.WARN_MARK) and tl.tip_lines(early)[-1].startswith(tl.WARN_MARK)
