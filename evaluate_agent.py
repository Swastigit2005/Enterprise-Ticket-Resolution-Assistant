#!/usr/bin/env python
"""
Offline evaluator for the autonomous ticket-resolution agent.

Usage:
    python evaluate_agent.py --dataset evaluation_cases.json --runs 3
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from pathlib import Path
from typing import Any

from inference import resolve_issue


EXPECTED_FIRST_TOOLS = [
    "retrieve_ticket_context",
    "generate_advocate_resolution",
    "validate_advocate_resolution",
]


def normalize_steps(result: dict[str, Any]) -> list[str]:
    value = (
        result.get("recommended_resolution")
        or result.get("resolution_steps")
        or result.get("resolution_generated")
        or []
    )

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text:
        return []

    matches = re.findall(
        r"(?:^|\n)\s*Step\s+\d+\s*:\s*(.*?)(?=(?:\n\s*Step\s+\d+\s*:)|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if matches:
        return [match.strip() for match in matches if match.strip()]

    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_reference_ids(result: dict[str, Any]) -> list[str]:
    references = (
        result.get("source_tickets")
        or result.get("reference_tickets")
        or []
    )
    ids: list[str] = []

    for item in references:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            ticket_id = (
                item.get("ticket_id")
                or item.get("source_ticket_id")
                or item.get("id")
            )
            if ticket_id:
                ids.append(str(ticket_id))

    return list(dict.fromkeys(ids))


def normalize_status(result: dict[str, Any]) -> str:
    status = str(result.get("status", "")).strip().lower()
    if status:
        if status in {"resolved", "success", "approved"}:
            return "resolved"
        if "handoff" in status or "insufficient" in status:
            return "human_handoff"

    if result.get("human_handoff") is True:
        return "human_handoff"

    if result.get("resolution_available") is False:
        return "human_handoff"

    return "resolved"


def get_tool_sequence(result: dict[str, Any]) -> list[str]:
    diagnostics = result.get("agent_diagnostics") or {}
    sequence = diagnostics.get("tool_sequence") or []
    return [str(name) for name in sequence]


def contains_phrase(text: str, phrase: str) -> bool:
    return phrase.casefold() in text.casefold()


def evaluate_one(case: dict[str, Any], result: dict[str, Any], latency: float) -> dict[str, Any]:
    steps = normalize_steps(result)
    output_text = "\n".join(steps)
    reference_ids = normalize_reference_ids(result)
    actual_status = normalize_status(result)

    expected_status = case.get("expected_status")
    expected_refs = [str(x) for x in case.get("relevant_ticket_ids", [])]
    required_concerns = [str(x) for x in case.get("required_concerns", [])]
    forbidden_phrases = [str(x) for x in case.get("forbidden_phrases", [])]

    expected_ref_set = set(expected_refs)
    actual_ref_set = set(reference_ids)
    retrieval_recall = (
        len(expected_ref_set & actual_ref_set) / len(expected_ref_set)
        if expected_ref_set
        else None
    )

    concerns_found = {
        concern: contains_phrase(output_text, concern)
        for concern in required_concerns
    }
    concern_coverage = (
        sum(concerns_found.values()) / len(concerns_found)
        if concerns_found
        else None
    )

    forbidden_hits = [
        phrase for phrase in forbidden_phrases
        if contains_phrase(output_text, phrase)
    ]

    min_steps = int(case.get("min_steps", 5))
    max_steps = int(case.get("max_steps", 8))
    step_count_ok = min_steps <= len(steps) <= max_steps

    tool_sequence = get_tool_sequence(result)
    trajectory_ok = (
        tool_sequence[:3] == EXPECTED_FIRST_TOOLS
        if tool_sequence
        else None
    )

    validation_present = bool(
        result.get("validation_feedback")
        or (result.get("agent_diagnostics") or {}).get("latest_validation")
        or (result.get("agent_diagnostics") or {}).get("validation_calls")
    )

    return {
        "case_id": case["case_id"],
        "actual_status": actual_status,
        "expected_status": expected_status,
        "status_correct": (
            actual_status == expected_status
            if expected_status
            else None
        ),
        "reference_ids": reference_ids,
        "expected_reference_ids": expected_refs,
        "retrieval_recall_at_k": retrieval_recall,
        "required_concerns_found": concerns_found,
        "concern_coverage": concern_coverage,
        "forbidden_phrase_hits": forbidden_hits,
        "no_forbidden_phrases": not forbidden_hits,
        "step_count": len(steps),
        "step_count_ok": step_count_ok,
        "validation_present": validation_present,
        "tool_sequence": tool_sequence,
        "first_iteration_trajectory_ok": trajectory_ok,
        "latency_seconds": round(latency, 3),
        "confidence": result.get("confidence"),
        "steps": steps,
        "raw_result": result,
    }


def mean_available(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float(row[key])
        for row in rows
        if row.get(key) is not None
    ]
    return round(statistics.mean(values), 4) if values else None


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_runs": len(rows),
        "status_accuracy": mean_available(rows, "status_correct"),
        "mean_retrieval_recall_at_k": mean_available(rows, "retrieval_recall_at_k"),
        "mean_concern_coverage": mean_available(rows, "concern_coverage"),
        "no_forbidden_phrase_rate": mean_available(rows, "no_forbidden_phrases"),
        "step_format_pass_rate": mean_available(rows, "step_count_ok"),
        "validation_present_rate": mean_available(rows, "validation_present"),
        "trajectory_pass_rate": mean_available(rows, "first_iteration_trajectory_ok"),
        "mean_latency_seconds": mean_available(rows, "latency_seconds"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation_cases.json")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", default="agent_evaluation_results.json")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))

    rows: list[dict[str, Any]] = []

    for case in cases:
        for run_number in range(1, args.runs + 1):
            started = time.perf_counter()
            try:
                result = resolve_issue(case["member_issue"])
            except Exception as exc:
                result = {
                    "status": "error",
                    "resolution_available": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            latency = time.perf_counter() - started

            row = evaluate_one(case, result, latency)
            row["run_number"] = run_number
            rows.append(row)

            print(
                f'{case["case_id"]} run={run_number} '
                f'status={row["actual_status"]} '
                f'recall={row["retrieval_recall_at_k"]} '
                f'coverage={row["concern_coverage"]} '
                f'forbidden={row["forbidden_phrase_hits"]} '
                f'latency={row["latency_seconds"]}s'
            )

    report = {
        "summary": build_summary(rows),
        "runs": rows,
    }

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nSUMMARY")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nSaved detailed results to {args.output}")


if __name__ == "__main__":
    main()
