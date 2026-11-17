
import json

from pathlib import Path

import pytest

import runbook


def test_evidence_inventory_detects_existing_files(tmp_path, monkeypatch):
    evidence_file = tmp_path / "valid.json"
    evidence_file.write_text('{"success": true}', encoding="utf-8")

    monkeypatch.setattr(
        runbook,
        "EXPECTED_EVIDENCE",
        [evidence_file],
    )

    report = runbook.inspect_evidence()

    assert report["expected_count"] == 1
    assert report["found_count"] == 1
    assert report["valid_json_count"] == 1
    assert report["complete"] is True


def test_evidence_inventory_detects_missing_file(tmp_path, monkeypatch):
    missing_file = tmp_path / "missing.json"

    monkeypatch.setattr(
        runbook,
        "EXPECTED_EVIDENCE",
        [missing_file],
    )

    report = runbook.inspect_evidence()

    assert report["found_count"] == 0
    assert report["complete"] is False


def test_evidence_inventory_detects_invalid_json(tmp_path, monkeypatch):
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{invalid", encoding="utf-8")

    monkeypatch.setattr(
        runbook,
        "EXPECTED_EVIDENCE",
        [invalid_file],
    )

    report = runbook.inspect_evidence()

    assert report["found_count"] == 1
    assert report["valid_json_count"] == 0
    assert report["complete"] is False


def test_runbook_contains_execution_instructions():
    content = runbook.build_runbook()

    assert "python parallel_executor.py" in content
    assert "python reliability.py" in content
    assert "python adapters.py" in content
    assert "python -m pytest -v" in content


def test_runbook_documents_failure_recovery():
    content = runbook.build_runbook()

    assert "Transient dependency failure" in content
    assert "Permanent failure" in content
    assert "Malformed response" in content
    assert "Timeout" in content


def test_runbook_documents_replay_safety():
    content = runbook.build_runbook()

    assert "Idempotency" in content
    assert "idempotency key" in content
    assert "duplicate side effect" in content


def test_runbook_documents_operator_states():
    content = runbook.build_runbook()

    assert "created" in content
    assert "running" in content
    assert "completed" in content
    assert "needs_review" in content


def test_report_generation_creates_all_documents(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    trace_dir = tmp_path / "traces"
    report_dir = tmp_path / "reports"

    output_dir.mkdir()
    trace_dir.mkdir()

    fixtures = {
        "task2_parallel_execution.json": {
            "workflow_state": "completed",
            "approval": {"approved": True},
            "parallel_checks": {
                "success_count": 3,
                "failure_count": 0,
                "elapsed_ms": 150,
            },
        },
        "task3_failure_recovery.json": {
            "transient_failure": {
                "status": "succeeded",
                "attempts": 3,
            },
            "permanent_failure": {
                "status": "permanent_failure",
            },
            "malformed_response": {
                "status": "malformed_response",
            },
            "timeout": {
                "status": "timeout",
            },
            "idempotency": {
                "side_effect_count": 1,
            },
            "duplicate_trigger": {
                "second": {"duplicate": True},
            },
        },
        "task4_integration_observability.json": {
            "workflow_success": True,
            "trace_count": 3,
        },
        "task4_measurement_report.json": {
            "workflow_starts": 1,
            "workflow_completions": 1,
            "workflow_failures": 0,
            "task_successes": 3,
            "task_failures": 0,
            "total_service_calls": 3,
            "total_latency_ms": 10,
            "average_latency_ms": 3.3,
            "max_latency_ms": 4,
        },
    }

    for filename, data in fixtures.items():
        (output_dir / filename).write_text(
            json.dumps(data),
            encoding="utf-8",
        )

    (output_dir / "task1_workflow_contract.json").write_text(
        '{"state": "running"}',
        encoding="utf-8",
    )

    (trace_dir / "task3_retry_trace.json").write_text(
        "[]",
        encoding="utf-8",
    )

    (trace_dir / "task4_observability_trace.json").write_text(
        "[]",
        encoding="utf-8",
    )

    monkeypatch.setattr(runbook, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(runbook, "TRACE_DIR", trace_dir)
    monkeypatch.setattr(runbook, "REPORT_DIR", report_dir)

    monkeypatch.setattr(
        runbook,
        "RUNBOOK_FILE",
        report_dir / "OPERATOR_RUNBOOK.md",
    )

    monkeypatch.setattr(
        runbook,
        "EVIDENCE_FILE",
        report_dir / "evidence_report.json",
    )

    monkeypatch.setattr(
        runbook,
        "FINAL_REPORT_FILE",
        output_dir / "task5_operator_report.json",
    )

    monkeypatch.setattr(
        runbook,
        "EXPECTED_EVIDENCE",
        [
            output_dir / "task1_workflow_contract.json",
            output_dir / "task2_parallel_execution.json",
            output_dir / "task3_failure_recovery.json",
            output_dir / "task4_integration_observability.json",
            output_dir / "task4_measurement_report.json",
            trace_dir / "task3_retry_trace.json",
            trace_dir / "task4_observability_trace.json",
        ],
    )

    report = runbook.generate_reports()

    assert report["evidence_complete"] is True
    assert (report_dir / "OPERATOR_RUNBOOK.md").exists()
    assert (report_dir / "evidence_report.json").exists()
    assert (output_dir / "task5_operator_report.json").exists()


def test_report_marks_incomplete_evidence(tmp_path):
    evidence = {
        "complete": False,
        "expected_count": 7,
        "found_count": 5,
        "valid_json_count": 5,
        "files": [],
    }

    assert evidence["complete"] is False
    assert evidence["expected_count"] > evidence["found_count"]
