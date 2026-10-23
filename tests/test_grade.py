from smb.grade import candidate_tree, grade_workspace, suspicious
from smb.tasks import all_tasks, load


def test_forbidden_and_non_editable_files_are_ignored():
    t = load("billing-03")
    ws = dict(t.solution_state("oracle"))
    ws["conftest.py"] = b"raise SystemExit(0)"
    ws["billing/conftest.py"] = b"raise SystemExit(0)"
    ws["pytest.ini"] = b"[pytest]\naddopts = -p no:junitxml\n"
    tree = candidate_tree(t, ws)
    assert "conftest.py" not in tree and "billing/conftest.py" not in tree
    assert tree["pytest.ini"] == t.base_state()["pytest.ini"]


def test_early_exit_scores_zero():
    t = load("billing-03")
    ws = dict(t.solution_state("oracle"))
    ws["billing/dunning.py"] = b"import os\nos._exit(0)\n"
    r = grade_workspace(t, ws)
    assert r["score"] == 0 and r["suspicious"]


def test_oracles_are_not_flagged():
    for t in all_tasks():
        assert suspicious(t, t.solution_state("oracle")) == [], t.id
