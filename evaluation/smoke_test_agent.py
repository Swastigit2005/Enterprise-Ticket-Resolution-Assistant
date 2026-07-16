"""Smoke-test the current compact autonomous agent.

Compatible with:
- diagnose_retrieval(issue) -> context_id
- generate_advocate_resolution(context_id, validation_feedback)
- validate_advocate_resolution(generation_id)
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys

import inference as agent
from inference import (
    diagnose_retrieval,
    generate_advocate_resolution,
    resolve_issue,
    validate_advocate_resolution,
)


def parse_tool_output(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def print_versions() -> None:
    print("PACKAGE VERSIONS")
    for package in [
        "langchain",
        "langgraph",
        "langchain-groq",
        "groq",
        "chromadb",
        "sentence-transformers",
        "pydantic",
    ]:
        try:
            print(f"{package}: {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            print(f"{package}: NOT INSTALLED")
    print()


def direct_tools(issue: str) -> dict:
    retrieval = diagnose_retrieval(issue)
    print("RETRIEVAL")
    print(json.dumps(retrieval, indent=2, ensure_ascii=False))

    if retrieval.get("status") != "context_found":
        return {"stage": "retrieval", "result": retrieval}

    context_id = retrieval.get("context_id")
    generation = parse_tool_output(
        generate_advocate_resolution.invoke(
            {
                "context_id": context_id,
                "validation_feedback": "",
            }
        )
    )
    print("\nGENERATION TOOL RESULT")
    print(json.dumps(generation, indent=2, ensure_ascii=False))

    if generation.get("status") != "generated":
        return {"stage": "generation", "result": generation}

    generation_id = generation.get("generation_id")
    stored_generation = agent._GENERATIONS.get(generation_id, {})
    print("\nSTORED GENERATED RESOLUTION")
    print(json.dumps(stored_generation, indent=2, ensure_ascii=False))

    validation = parse_tool_output(
        validate_advocate_resolution.invoke(
            {"generation_id": generation_id}
        )
    )
    print("\nVALIDATION")
    print(json.dumps(validation, indent=2, ensure_ascii=False))

    return {
        "stage": "complete",
        "retrieval": retrieval,
        "generation": stored_generation,
        "validation": validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", required=True)
    parser.add_argument(
        "--mode",
        choices=["retrieval", "direct-tools", "agent", "all"],
        default="retrieval",
    )
    args = parser.parse_args()

    print_versions()

    if args.mode in {"retrieval", "all"}:
        print("=== RETRIEVAL-ONLY TEST ===")
        print(
            json.dumps(
                diagnose_retrieval(args.issue),
                indent=2,
                ensure_ascii=False,
            )
        )
        print()

    direct_result = None
    if args.mode in {"direct-tools", "all"}:
        print("=== DIRECT TOOL TEST ===")
        direct_result = direct_tools(args.issue)
        print()

    if (
        args.mode == "all"
        and direct_result is not None
        and direct_result.get("stage") != "complete"
    ):
        print(
            "AUTONOMOUS AGENT TEST SKIPPED because the direct tool test failed "
            f"at stage: {direct_result.get('stage')}."
        )
        return

    if args.mode in {"agent", "all"}:
        print("=== AUTONOMOUS AGENT TEST ===")
        result = resolve_issue(args.issue)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result.get("status") != "resolved":
            print(
                "\nAgent did not resolve the issue. Review reasoning, handoff_reason, "
                "retrieval_attempts, and tool_sequence above.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
