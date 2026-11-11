import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeline as tl


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
    rows, _ = tl.rows_from_text("2025-03-10,Results,\"a, b\"\n")
    again, _ = tl.rows_from_text(tl.to_csv(rows))
    assert [(r["date"], r["class"], r["description"]) for r in again] == [("2025-03-10", "Results", "a, b")]


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
    rows = [tl.make_row(date(2025, 3, 1 + i % 5), "Results", "a fairly long description of the event") for i in range(20)]
    placed = tl.layout_labels(rows, px_per_day=30)
    for a in placed:
        for b in placed:
            if a is not b and a["lane"] == b["lane"]:
                assert a["x_end"] <= b["x"] or b["x_end"] <= a["x"]
    roomy = tl.layout_labels(rows[:2], px_per_day=30)
    assert len(roomy[0]["lines"]) > len(placed[0]["lines"])
