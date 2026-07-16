"""LLM-as-judge evaluation for agent answers plus validator quality."""

from __future__ import annotations

import os

import pandas as pd
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from eval_config import GROQ_API_KEY, LLM_MODEL


INPUT_FILE = "ragas_input.csv"
RESUME_FILE = "agent_evaluation_results.csv"
FINAL_EXCEL_FILE = "agent_evaluation_results.xlsx"


class EvaluationResponse(BaseModel):
    correctness: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    groundedness: float = Field(ge=0, le=10)
    generalization: float = Field(ge=0, le=10)
    relevance: float = Field(ge=0, le=10)
    validation_quality: float = Field(ge=0, le=10)
    overall: float = Field(ge=0, le=10)
    reasoning: str


EVALUATION_PROMPT = """
Evaluate an autonomous ticket-resolution agent.

Compare operational intent, not exact wording.

INPUTS

Current ticket:
{question}

Expected workflow:
{ground_truth}

Retrieved historical evidence:
{contexts}

Agent answer:
{answer}

Agent status:
{actual_status}

Agent validation feedback:
{validation_feedback}

Human handoff:
{human_handoff}

Tool sequence:
{tool_sequence}

SCORING

correctness:
Are the actions operationally correct compared with the expected workflow?
Deduct for incorrect conclusions, invented requirements, or contradictory actions.

completeness:
Are the important investigation, validation, documentation, communication,
and resolution activities from the expected workflow present?

groundedness:
Judge against the retrieved historical evidence, not merely the expected answer.
Every material generated action should be traceable to the retrieved evidence.
If evidence is empty, a substantive generated answer cannot receive a high score.

generalization:
Allow names and details that appear in the CURRENT ticket.
Penalize historical names, plan details, claim IDs, amounts, causes, or conclusions
that appear only in retrieved evidence and were copied into the answer.
Do not penalize reasonable abstraction that preserves operational intent.

relevance:
Does the answer address every major concern in the current ticket?

validation_quality:
Did the agent's validator make the correct decision?
- Approval deserves a high score only when the answer is complete and grounded.
- Approval of unsupported or incomplete steps deserves a low score.
- Handoff deserves a high score only when evidence is genuinely insufficient.
- Handoff despite useful relevant evidence and an available expected workflow deserves a low score.

overall:
Use professional judgment across all dimensions. Do not automatically average.

SCORING DISCIPLINE

Use 0-10 for every score.
9-10 means very few meaningful deficiencies.
7-8 means mostly good with minor defects.
4-6 means material deficiencies.
1-3 means major failure.
0 means unusable.

Return every required field.
Keep reasoning concise but identify the main defects.
"""

df = pd.read_csv(INPUT_FILE)

if os.path.exists(RESUME_FILE):
    results = pd.read_csv(RESUME_FILE).to_dict(orient="records")
else:
    results = []

start_index = len(results)
print(f"Resuming from row {start_index + 1}/{len(df)}")

llm = ChatGroq(
    model=LLM_MODEL,
    groq_api_key=GROQ_API_KEY,
    temperature=0,
    max_retries=0,
)

chain = (
    ChatPromptTemplate.from_template(EVALUATION_PROMPT)
    | llm.with_structured_output(EvaluationResponse)
)

for index in range(start_index, len(df)):
    row = df.iloc[index]
    print(f"\nEvaluating {index + 1}/{len(df)}: {row.get('case_id', index + 1)}")

    try:
        response = chain.invoke(
            {
                "question": str(row["question"]),
                "ground_truth": str(row["ground_truth"]),
                "contexts": str(row.get("contexts", "[]")),
                "answer": str(row.get("answer", "")),
                "actual_status": str(row.get("actual_status", "")),
                "validation_feedback": str(row.get("validation_feedback", "")),
                "human_handoff": str(row.get("human_handoff", False)),
                "tool_sequence": str(row.get("tool_sequence", "[]")),
            }
        )

        results.append(
            {
                "case_id": row.get("case_id", index + 1),
                "question": row["question"],
                "actual_status": row.get("actual_status", ""),
                "status_correct": row.get("status_correct", False),
                "trajectory_valid": row.get("trajectory_valid", False),
                "latency_seconds": row.get("latency_seconds", 0.0),
                **response.model_dump(),
            }
        )

        pd.DataFrame(results).to_csv(RESUME_FILE, index=False)
        print("Saved.")

    except Exception as exc:
        print(f"Failed row {index + 1}: {type(exc).__name__}: {exc}")

        error_text = str(exc).lower()
        if "rate_limit" in error_text or "429" in error_text:
            print("Groq quota/rate limit reached. Stopping safely.")
            break

results_df = pd.DataFrame(results)
results_df.to_csv(RESUME_FILE, index=False)
results_df.to_excel(FINAL_EXCEL_FILE, index=False)

print("\nLLM-JUDGE AVERAGES")
for metric in [
    "correctness",
    "completeness",
    "groundedness",
    "generalization",
    "relevance",
    "validation_quality",
    "overall",
]:
    if metric in results_df and len(results_df):
        print(f"{metric}: {results_df[metric].mean():.2f}")

if len(results_df):
    print("\nDETERMINISTIC AVERAGES")
    print(
        "status_accuracy: "
        f"{results_df['status_correct'].astype(float).mean():.4f}"
    )
    print(
        "trajectory_pass_rate: "
        f"{results_df['trajectory_valid'].astype(float).mean():.4f}"
    )
    print(
        "mean_latency_seconds: "
        f"{results_df['latency_seconds'].mean():.3f}"
    )

print(f"\nSaved:\n- {RESUME_FILE}\n- {FINAL_EXCEL_FILE}")
