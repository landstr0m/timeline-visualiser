"""Checks the Dash page builds and its drawing callback runs end to end (no browser needed)."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app  # noqa: E402
import timeline as tl  # noqa: E402

VIEW = app.view_dict(datetime(2026, 11, 1), datetime(2026, 12, 2))


def find_ids(node, found=None):
    """Every component id on the page."""
    found = set() if found is None else found
    if getattr(node, "id", None) and isinstance(node.id, str):
        found.add(node.id)
    children = getattr(node, "children", None)
    for child in children if isinstance(children, (list, tuple)) else [children]:
        if hasattr(child, "to_plotly_json"):
            find_ids(child, found)
    return found


def test_page_has_every_control_the_callbacks_use():
    ids = find_ids(app.app.layout)
    wanted = "rows view undo graph table title show search hide timeline-pick prev next today first fit capture copy"
    wanted += " add upload save undo-btn clear paste paste-add status caption compress expanded break-buttons"
    assert set(wanted.split()) <= ids


def test_render_draws_sample_and_applies_filters():
    rows = app.rows0
    assert len(rows) == 18
    fig, table, columns, caption, tl_style, tb_style, classes, names, pick_style, gaps = app.render(
        rows, VIEW, 1100, ["Timeline", "Table"], "Demo", "", [], None, [], []
    )
    assert len(table) == 15 and "15 of 18" in caption and "filter" not in caption
    assert table[1]["gap"] == "+0 d" and table[2]["gap"] == "+2 h 25 min"
    assert [c["id"] for c in columns] == ["date", "end", "gap", "class", "description"]
    assert "Deviation" in classes and names == [] and pick_style == {"display": "none"}
    assert fig.layout.title.text == "Demo" and tl_style == {} and tb_style == {}

    fig2, table2, columns2, caption2, *_ = app.render(
        rows, VIEW, 1100, ["Table", "Details"], "", "lab", ["Phase"], "gone", [], []
    )
    assert [r["owner"] for r in table2] == ["Lab", "Lab", "Lab"] and "filter on (15 hidden)" in caption2
    assert "owner" in [c["id"] for c in columns2]
    # a class keeps its colour when others are filtered away
    results = next(t for t in fig2.data if t.name == "Results")
    assert results.line.color == tl.class_colours(rows)["Results"]


def test_upload_reader_handles_text_with_bom():
    import base64

    payload = "data:text/csv;base64," + base64.b64encode("﻿date,class,description\n2025-03-10,A,x\n".encode()).decode()
    rows, bad = app.read_upload(payload, "events.csv")
    assert rows[0]["date"] == "2025-03-10" and bad == 0


def test_compress_gaps_brings_far_events_into_view():
    rows = [tl.make_row(d, "A", "x") for d in ("2026-01-01", "2026-01-03", "2026-03-01", "2026-03-03")]
    view = app.view_dict(datetime(2025, 12, 31), datetime(2026, 1, 31))
    *_, caption, _a, _b, _c, _d, _e, gaps = app.render(rows, view, 1100, ["Table"], "", "", [], None, [], [])
    assert "2 of 4" in caption and gaps == []
    fig, table, _c, caption, *_rest, gaps = app.render(
        rows, view, 1100, ["Table"], "", "", [], None, ["Compress gaps"], []
    )
    assert len(table) == 4 and "1 gap(s) compressed" in caption
    assert gaps[0].children == "(57 days) ×" and len(fig.layout.xaxis.rangebreaks) == 1
    key = gaps[0].id["expand"]
    *_, caption, _a, _b, _c, _d, _e, gaps = app.render(
        rows, view, 1100, ["Table"], "", "", [], None, ["Compress gaps"], [key]
    )
    assert "2 of 4" in caption and gaps == []
