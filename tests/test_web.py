"""Checks web/index.html gives the same results as timeline.py.

Runs the data functions of the web page (everything before the "state"
section, which needs a browser) in Node. Skipped if Node is not installed.
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

CASES = [
    (ROOT / "sample_events.csv").read_text(encoding="utf-8"),
    "Date,Title,Description\n2025-03-12,Results,B\n2025-03-10,Approval,A\nnope,X,Y\n",
    "10-Mar-2025\tResults: buffer data expected\n",
    "2025-03-10,Results,\"a, b\"\n",
    "start,end,class,description\n2025-03-01,2025-03-20,Phase,Run\n2025-03-25,2025-03-21,Phase,Swapped\n",
    "date;end;class;description\n10.03.2025;;Review;semicolons\n",
]


def run_web(cases):
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = html.split("<script>", 1)[1].split("// ---------------------------------------------------------------- state ----", 1)[0]
    js = script + """
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map(t => { const { rows, bad } = rowsFromText(t);
  return { csv: toCSV(rows), bad, colours: classColours(rows) }; });
process.stdout.write(JSON.stringify({ out, palette: PALETTE, min: MIN_DAYS, max: MAX_DAYS }));
"""
    res = subprocess.run(["node", "-e", js], input=json.dumps(cases), capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def test_web_matches_python():
    web = run_web(CASES)
    assert web["palette"] == tl.PALETTE
    assert (web["min"], web["max"]) == (tl.MIN_DAYS, tl.MAX_DAYS)
    for text, got in zip(CASES, web["out"]):
        rows, bad = tl.rows_from_text(text)
        assert got["csv"] == tl.to_csv(rows), text
        assert got["bad"] == bad, text
        assert got["colours"] == tl.class_colours(rows), text
