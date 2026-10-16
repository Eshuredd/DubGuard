import json

from fastapi.testclient import TestClient

from dubguard.api import app
from dubguard.cli import main
from dubguard.evaluation import calculate_metrics, evaluate, export_report

client = TestClient(app)


def test_api_health_and_openapi():
    assert client.get("/health").json()["asr_integrated"] is True
    assert client.get("/openapi.json").status_code == 200


def test_api_validation_and_verification(case_request):
    request = case_request("C01").model_dump(mode="json")
    policy = {k: v for k, v in request.items() if k != "transcript"}
    assert client.post("/validate", json=policy).json()["valid"] is True
    result = client.post("/verify", json=request)
    assert result.status_code == 200
    assert result.json()["decision"] == "CRITICAL_DEVIATION"
    assert any(f["rule_id"] == "POLARITY.REVERSED" for f in result.json()["findings"])


def test_api_rejects_invalid_input(case_request):
    request = case_request("A01").model_dump(mode="json")
    request["policy"]["constraints"][0]["instruction_id"] = "unknown"
    assert client.post("/verify", json=request).status_code == 422


def test_api_hybrid_disabled_requires_review(case_request, monkeypatch):
    monkeypatch.setenv("DUBGUARD_SEMANTIC_PROVIDER", "disabled")
    response = client.post("/verify?mode=hybrid", json=case_request("A01").model_dump(mode="json"))
    assert response.json()["decision"] == "REVIEW_REQUIRED"


def test_api_reports_and_format_validation():
    response = client.get("/evaluation/reports")
    assert response.json()["dataset"]["count"] == 60
    assert response.json()["paths"]["C_hybrid"]["status"] == "skipped"
    response = client.get("/evaluation/reports?format=markdown")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "C22" in response.text
    assert client.get("/evaluation/reports?format=html").status_code == 422


def test_metrics_known_confusion_matrix():
    rows = [
        {"category":"x","label":"CRITICAL","decision":"CRITICAL_DEVIATION"},
        {"category":"x","label":"CRITICAL","decision":"REVIEW_REQUIRED"},
        {"category":"x","label":"ACCEPTABLE","decision":"CRITICAL_DEVIATION"},
        {"category":"x","label":"ACCEPTABLE","decision":"PASS_CANDIDATE"},
        {"category":"x","label":"UNRESOLVED","decision":"CRITICAL_DEVIATION"},
        {"category":"x","label":"UNRESOLVED","decision":"PASS_CANDIDATE"},
    ]
    m = calculate_metrics(rows)
    assert m["critical_deviation_recall"] == 0.5
    assert m["critical_deviation_precision"] == 0.333333
    assert m["false_alert_rate_on_acceptable"] == 0.5
    assert m["unresolved_rate"] == 0.166667
    assert m["decision_errors"] == 4
    assert m["unsafe_passes"] == 1
    assert m["per_category"]["x"]["errors"] == 4


def test_undefined_metrics_are_null():
    m = calculate_metrics([])
    assert m["critical_deviation_recall"] is None
    assert m["critical_deviation_precision"] is None
    assert m["unresolved_rate"] is None


def test_reports_are_byte_reproducible(tmp_path):
    first = export_report(evaluate(), tmp_path / "first")
    second = export_report(evaluate(), tmp_path / "second")
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]


def test_report_counts_and_honest_failures():
    report = evaluate()
    m = report["paths"]["B_policy_engine"]["metrics"]
    assert m["label_counts"] == {"ACCEPTABLE":24,"CRITICAL":24,"UNRESOLVED":12}
    assert m["true_positives"] == 22
    assert m["false_negatives"] == 2
    assert {r["id"] for r in report["paths"]["B_policy_engine"]["failures"]} == {"C22","C23","A18","A23"}
    assert m["unsafe_passes"] == 0


def test_cli_commands(case_request, tmp_path, capsys):
    request = case_request("C01").model_dump(mode="json")
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    assert main(["verify", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "CRITICAL_DEVIATION"
    del request["transcript"]
    path.write_text(json.dumps(request))
    assert main(["validate", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["evaluate", "--output", str(tmp_path / "reports")]) == 0
    assert (tmp_path / "reports/evaluation.md").exists()
    capsys.readouterr()
    path.write_text("invalid json")
    assert main(["verify", str(path)]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "ValidationError"
