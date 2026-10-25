import csv
import json
import statistics

import numpy as np
import pytest

from libra_check.cli import main
from libra_check.core import InputError
from libra_check.io import load_counts, load_individuals


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def test_scoring_rate_uses_full_sample_median(tmp_path):
    rng = np.random.default_rng(1)
    rows = []
    for i in range(400):
        sex = ["Female", "Male", "Unknown", ""][i % 4]
        race = ["White", "Black", "Asian", "Hispanic"][(i // 4) % 4]
        rows.append({"sex": sex, "race": race, "score": round(float(rng.normal(50 + (sex == "Male") * 2, 10)), 0)})
    p = tmp_path / "a.csv"; _write(p, rows)
    units, info = load_individuals(p, score_col="score")
    med = statistics.median(r["score"] for r in rows)
    assert info["median"] == med and info["ties_at_median"] == sum(r["score"] == med for r in rows)
    sex = {c["label"]: c for c in units[0]["categories"]}
    assert sex["Unknown"]["n"] == 200 and sex["Unknown"]["unknown"]
    exp_f = sum(1 for r in rows if r["sex"] == "Female" and r["score"] > med)
    assert sex["Female"]["k"] == exp_f
    inter = units[2]["categories"]
    assert all(c["unknown"] for c in inter if "Unknown" in c["label"])
    assert sum(c["n"] for c in inter) == 400


def test_selection_counts_and_bad_values(tmp_path):
    rows = [{"sex": "F", "race": "W", "selected": v} for v in ("1", "0", "yes", "no")]
    p = tmp_path / "s.csv"; _write(p, rows)
    units, _ = load_individuals(p, selected_col="selected")
    assert units[0]["categories"][0] == {"label": "F", "n": 4, "k": 2, "unknown": False}
    _write(p, rows + [{"sex": "F", "race": "W", "selected": "maybe"}])
    with pytest.raises(InputError):
        load_individuals(p, selected_col="selected")


def test_counts_csv_with_dimensions(tmp_path):
    p = tmp_path / "c.csv"
    p.write_text("dimension,category,n,k,rate\nsex,Male,100,50,\nsex,Female,100,,0.40\nrace,A,50,20,\nrace,B,60,30,\n")
    units, _ = load_counts(p)
    assert [u["dimension"] for u in units] == ["sex", "race"]
    assert units[0]["categories"][1]["rate"] == "0.40"


def test_cli_end_to_end(tmp_path, capsys, full_prov):
    p = tmp_path / "c.csv"; p.write_text("category,n,k\nA,1000,500\nB,1000,420\nUnknown,20,4\n")
    prov = tmp_path / "prov.json"; prov.write_text(json.dumps(full_prov))
    meta = tmp_path / "meta.json"; meta.write_text(json.dumps({"system": "S", "decision_point": "screen", "data_source": "historical"}))
    out, md, ht = tmp_path / "r.json", tmp_path / "r.md", tmp_path / "r.html"
    assert main(["analyze", str(p), "--provenance", str(prov), "--meta", str(meta), "--out", str(out),
                 "--md", str(md), "--html", str(ht), "--require-provenance"]) == 0
    assert main(["validate", str(out)]) == 0
    assert main(["conform", str(out)]) == 0
    assert "CONFORMS" in capsys.readouterr().out
    assert main(["analyze", str(p), "--require-provenance", "--out", str(out)]) == 2
    assert main(["analyze", str(p), "--provenance", str(prov), "--theta", "0.9", "--out", str(out)]) == 2


def test_cli_ll144_raw(tmp_path):
    rows = [{"sex": "F" if i % 2 else "M", "race": "W" if i % 3 else "B", "score": i % 17} for i in range(300)]
    p = tmp_path / "raw.csv"; _write(p, rows)
    out = tmp_path / "r.json"
    assert main(["ll144", str(p), "--score-col", "score", "--out", str(out), "--no-power"]) == 0
    rep = json.loads(out.read_text())
    assert rep["selection_rule"] == "scoring_rate" and rep["score_cut"] == "median_full_sample"
    assert [u["dimension"] for u in rep["units"]] == ["sex", "race_ethnicity", "intersectional"]
