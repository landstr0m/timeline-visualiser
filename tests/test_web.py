"""Checks web/index.html gives the same results as timeline.py.

Runs the pure functions of the web page (everything before the "state"
section, which needs a browser) in Node and compares each result with the
Python function of the same name. Skipped if Node is not installed.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import timeline as tl  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node not installed")

SAMPLE = (ROOT / "sample_events.csv").read_text(encoding="utf-8")
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
STATE_MARK = "// ---------------------------------------------------------------- state ----"

# Each case is CSV or pasted text; every function below is compared on every case.
CASES = [
    SAMPLE,
    "Date,Title,Description\n2025-03-12,Results,B\n2025-03-10,Approval,A\nnope,X,Y\n",
    "10-Mar-2025\tResults: buffer data expected\n",
    '2025-03-10,Results,"a, b"\n',
    "start,end,class,description\n2025-03-01,2025-03-20,Phase,Run\n2025-03-25,2025-03-21,Phase,Swapped\n",
    "date;end;class;description\n10.03.2025;;Review;semicolons\n",
    # v1.1: times of day, optional columns in any order, key flag spellings
    "2025-03-10 14:30,A,late\n2025-03-10,A,whole day\n10.03.2025 8:05,A,early\n2025-03-10T23:59:30,B,iso\n",
    "when,until,type,text,who,evidence,timeline,id,depends on,important\n"
    "2025-03-10 09:15,2025-03-10 11:40,Hold,Tank on hold,Ana,Batch record p4,Line 1,E1,,x\n"
    "2025-03-11,,Results,pH data,Ben,,Line 2,E2,E1,\n2025-03-12 25:00,,Results,bad time,,,,,,\n",
    "2025-01-01,A,x\n2027-01-01,A,y\n",
    "2025-03-10 00:00,A,midnight is a plain date\n",
    # dependencies: B starts before A's band ends, D names a missing id
    "id,date,end,class,description,depends_on\nA,2025-03-01,2025-03-10,Phase,Run,\nB,2025-03-05,,Review,Early,A\n"
    'C,2025-03-10,,Review,On time,A\nD,2025-03-12,,Review,Late,"A; X"\n',
]

# Runs after the page's pure functions; prints one JSON object with every result.
HARNESS = """
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map(t => {
  const { rows, bad } = rowsFromText(t), fit = fitSpan(rows), lo = rows.length ? num(rows[0].date) : 0;
  const strip = rs => rs.map(r => [r.date, r.description]);
  return { csv: toCSV(rows), bad, colours: classColours(rows),
    gaps: withGaps(rows).map(r => r.gap), tips: rows.map(tipLines), heads: rows.map(r => labelHead(r, true)),
    timelines: timelines(rows), found: strip(filterRows(rows, ["Results"], "", "a")),
    fit: fit && [fit[0] - lo, fit[1]], seen: strip(inSpan(rows, lo + 0.5, lo + 1.5)),
    back: rows.map(r => numWhen(num(r.date))),
    issues: (iss => rows.map(r => iss[r.id] || []))(dependencyIssues(rows)),
    flaggedHeads: flagRows(rows, dependencyIssues(rows)).map(r => [labelHead(r, false), tipLines(r)]),
    breaks: [7, 30].map(span => findBreaks(rows, span, 40, []).map(b => [b.key, b.lo - lo, b.hi - lo, b.gap])) };
});
const ticks = [5, 11, 22, 34, 87, 88, 150, 351, 1040, 1100].map(tickStep);
const cut = [{ lo: 10, hi: 20 }, { lo: 30, hi: 40 }];
const squashed = [[5, 10, 15, 20, 25, 45].map(x => squash(cut, x)), [5, 10, 15, 25].map(d => unsquash(cut, d))];
const labels = [0.3, 1, 15, 59.6, 92, 800, 1100].map(breakText);
process.stdout.write(JSON.stringify({ out, ticks, squashed, labels, shares: [GAP_SHARE, PAD_SHARE, CHAR_PX], palette: PALETTE, min: MIN_DAYS, max: MAX_DAYS, sample: SAMPLE,
  aliases: ALIASES, levels: LEVELS, columns: [COLUMNS, EXTRAS, EXTRA_FIELDS] }));
"""


def run_web(cases):
    script = HTML.split("<script>", 1)[1].split(STATE_MARK, 1)[0]
    res = subprocess.run(
        ["node", "-e", script + HARNESS], input=json.dumps(cases), capture_output=True, text=True, encoding="utf-8"
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


@pytest.fixture(scope="module")
def web():
    return run_web(CASES)


def test_constants_match(web):
    assert web["palette"] == tl.PALETTE
    assert (web["min"], web["max"]) == (tl.MIN_DAYS, tl.MAX_DAYS)
    assert web["aliases"] == tl.ALIASES
    assert web["levels"] == [list(level) for level in tl.LEVELS]
    assert web["columns"] == [tl.COLUMNS, tl.EXTRAS, tl.EXTRA_FIELDS]
    assert web["shares"] == [tl.GAP_SHARE, tl.PAD_SHARE, tl.CHAR_PX]
    assert web["sample"] == SAMPLE  # the sample built into the page is the sample file


def test_gap_compression_matches(web):
    cut = [{"lo": 10, "hi": 20}, {"lo": 30, "hi": 40}]
    assert web["squashed"] == [
        [tl.squash(cut, x) for x in [5, 10, 15, 20, 25, 45]],
        [tl.unsquash(cut, d) for d in [5, 10, 15, 25]],
    ]
    assert web["labels"] == [tl.break_text(d) for d in [0.3, 1, 15, 59.6, 92, 800, 1100]]


def test_tick_steps_match(web):
    assert web["ticks"] == [list(tl.tick_step(p)) for p in [5, 11, 22, 34, 87, 88, 150, 351, 1040, 1100]]


@pytest.mark.parametrize("i", range(len(CASES)))
def test_web_matches_python(web, i):
    text, got = CASES[i], web["out"][i]
    rows, bad = tl.rows_from_text(text)
    lo = tl.when_num(rows[0]["date"]) if rows else 0

    def strip(found):
        return [[r["date"], r["description"]] for r in found]

    assert got["csv"] == tl.to_csv(rows)
    assert got["bad"] == bad
    assert got["colours"] == tl.class_colours(rows)
    assert got["gaps"] == [r["gap"] for r in tl.with_gaps(rows)]
    assert got["tips"] == [tl.tip_lines(r) for r in rows]
    assert got["heads"] == [tl.label_head(r, True) for r in rows]
    assert got["timelines"] == tl.timelines(rows)
    assert got["found"] == strip(tl.filter_rows(rows, ["Results"], "", "a"))
    assert got["seen"] == strip(tl.in_span(rows, lo + 0.5, lo + 1.5))
    want = [
        [[b["key"], b["lo"] - lo, b["hi"] - lo, b["gap"]] for b in tl.find_breaks(rows, span, 40)] for span in (7, 30)
    ]
    keys = [[x[0] for x in w] for w in got["breaks"]]
    assert keys == [[x[0] for x in w] for w in want]
    numbers = [n for w in got["breaks"] for x in w for n in x[1:]]
    assert numbers == pytest.approx([n for w in want for x in w for n in x[1:]])
    issues = tl.dependency_issues(rows)
    assert got["issues"] == [issues.get(r["id"], []) for r in rows]
    assert got["flaggedHeads"] == [[tl.label_head(r), tl.tip_lines(r)] for r in tl.flag_rows(rows, issues)]
    assert got["back"] == [tl.num_when(tl.when_num(r["date"])) for r in rows]
    fit = tl.fit_span(rows)
    assert got["fit"] == pytest.approx([fit[0] - lo, fit[1]])
