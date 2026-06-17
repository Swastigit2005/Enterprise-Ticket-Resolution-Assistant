import os
import pandas as pd
from pydantic import BaseModel

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate


# ==========================================
# EVALUATION SCHEMA
# ==========================================

class EvaluationResponse(BaseModel):

    correctness: float

    completeness: float

    groundedness: float

    generalization: float

    relevance: float

    overall: float

    reasoning: str


# ==========================================
# PROMPT
# ==========================================
EVALUATION_PROMPT = """
You are evaluating an enterprise ticket resolution system.

Compare the generated workflow against the ground-truth workflow.

Do not require exact wording matches.

Do not penalize reasonable abstraction.

Generalized workflow actions should receive high scores when they preserve the operational intent of the ground-truth workflow.

==================================================
EVALUATION PROCESS
==================================================

Before assigning scores:

1. Identify the major workflow activities present in the Ground Truth.
2. Identify the workflow activities present in the Generated Answer.
3. Determine which important activities are:
   - Present
   - Missing
   - Incorrect
   - Unsupported
4. Evaluate whether the Generated Answer addresses the user's issue.
5. Evaluate whether the Generated Answer remains operational and reusable.

Do not assign scores until this comparison has been performed.

==================================================
CORRECTNESS (0-10)
==================================================

Evaluate whether the generated workflow performs the correct operational actions.
Do not deduct points solely because the generated workflow uses generalized operational language instead of ticket-specific actions.

9-10:
Actions closely match the intent of the ground-truth workflow.

7-8:
Mostly correct with minor inaccuracies.

4-6:
Several actions are incorrect, unnecessary, or questionable.

1-3:
Major workflow errors exist.

0:
Workflow is completely incorrect.

Deduct points for:
- Incorrect actions
- Unnecessary actions
- Actions that conflict with the ground truth

==================================================
COMPLETENESS (0-10)
==================================================

Evaluate whether important workflow activities from the ground truth are present.

9-10:
Almost all important workflow activities are included.

7-8:
Minor workflow activities are missing.

4-6:
Several important activities are missing.

1-3:
Many critical activities are missing.

0:
Workflow is largely incomplete.

Deduct points for:
- Missing validations
- Missing investigations
- Missing documentation activities
- Missing communication activities
- Missing escalation or resolution activities

==================================================
GROUNDEDNESS (0-10)
==================================================

Evaluate whether the generated workflow appears supported by the ground-truth workflow.
Generalized versions of supported workflow actions should be considered grounded if the operational intent remains traceable to the ground truth.

9-10:
Most generated actions can be traced to the ground truth.

7-8:
Generally supported with minor unsupported actions.

4-6:
Several actions appear unsupported.

1-3:
Many actions appear invented.

0:
Workflow is largely unsupported.

Deduct points for:
- Invented workflow steps
- Unsupported assumptions
- Actions not justified by the ground truth

==================================================
GENERALIZATION (0-10)
==================================================

Evaluate whether the workflow generalizes operational actions while removing ticket-specific details.

9-10:
Reusable workflow with preserved operational intent.

7-8:
Mostly generalized with minor ticket-specific details.

4-6:
Contains noticeable ticket-specific content.

1-3:
Copies significant portions of the original workflow.

0:
Directly copies the ground truth.

Do not penalize generalized workflow actions when they preserve the operational intent of the ground-truth workflow.

Examples:

Ground Truth:
"Call provider to verify participation."

Generated:
"Verify provider participation for the applicable plan."

These should be considered equivalent.

Ground Truth:
"Check provider directory."

Generated:
"Review provider-network resources."

These should be considered equivalent.

Focus on operational intent rather than exact implementation details.
==================================================
RELEVANCE (0-10)
==================================================

Evaluate whether the generated workflow addresses the user's issue.

9-10:
Addresses all major concerns.

7-8:
Addresses most concerns.

4-6:
Addresses some concerns but misses important aspects.

1-3:
Addresses very little of the issue.

0:
Does not address the issue.

==================================================
OVERALL (0-10)
==================================================

Overall quality considering:

- Correctness
- Completeness
- Groundedness
- Generalization
- Relevance

The Overall score should not automatically equal the average.

==================================================
SCORING DISCIPLINE
==================================================

Do not give high scores by default.

A score of 9 or 10 should only be given when there are few or no meaningful deficiencies.

Missing workflow activities should reduce Completeness.

Unsupported workflow activities should reduce Groundedness.

Incorrect workflow activities should reduce Correctness.

Generic workflows that omit important details should not receive maximum scores.

==================================================
INPUTS
==================================================

Question:
{question}

Ground Truth:
{ground_truth}

Generated Answer:
{answer}

==================================================
OUTPUT REQUIREMENTS
==================================================

You MUST provide values for ALL fields:

- correctness
- completeness
- groundedness
- generalization
- relevance
- overall
- reasoning

Do not omit any field.

Every numeric field must contain a value between 0 and 10.
"""

# ==========================================
# FILES
# ==========================================

INPUT_FILE = "ragas_input.csv"

RESUME_FILE = "groq_evaluation_results.csv"

FINAL_EXCEL_FILE = (
    "groq_evaluation_results.xlsx"
)

# ==========================================
# LOAD DATA
# ==========================================

df = pd.read_csv(
    INPUT_FILE
)

# ==========================================
# RESUME LOGIC
# ==========================================

if os.path.exists(
    RESUME_FILE
):

    existing_df = pd.read_csv(
        RESUME_FILE
    )

    results = existing_df.to_dict(
        orient="records"
    )

else:

    results = []

start_index = len(results)

print(
    f"\nResuming from row "
    f"{start_index + 1}"
)

total_rows = len(df)

df = df.iloc[
    start_index:
]

# ==========================================
# LLM
# ==========================================

from eval_config import (
    GROQ_API_KEY,
    LLM_MODEL
)

llm = ChatGroq(
    model=LLM_MODEL,
    groq_api_key=GROQ_API_KEY,
    temperature=0
)

structured_llm = (
    llm.with_structured_output(
        EvaluationResponse
    )
)

prompt = (
    ChatPromptTemplate
    .from_template(
        EVALUATION_PROMPT
    )
)

chain = prompt | structured_llm

# ==========================================
# EVALUATION LOOP
# ==========================================

for current_row, (_, row) in enumerate(
    df.iterrows(),
    start=start_index + 1
):

    print(
        f"\nEvaluating "
        f"{current_row}/{total_rows}"
    )

    try:

        response = chain.invoke(
            {
                "question":
                    str(row["question"]),

                "ground_truth":
                    str(row["ground_truth"]),

                "answer":
                    str(row["answer"])
            }
        )

        result = response.model_dump()

        results.append(
            {
                "question":
                    row["question"],

                **result
            }
        )

        # ==================================
        # SAVE AFTER EVERY SUCCESS
        # ==================================

        pd.DataFrame(
            results
        ).to_csv(
            RESUME_FILE,
            index=False
        )

        print(
            "Saved."
        )

    except Exception as e:

        print(
            f"Failed row "
            f"{current_row}: {e}"
        )

        if (
            "rate_limit_exceeded"
            in str(e)
        ):

            print(
                "\nGroq quota reached."
            )

            print(
                "Stopping evaluation."
            )

            break

# ==========================================
# FINAL SAVE
# ==========================================

results_df = pd.DataFrame(
    results
)

results_df.to_csv(
    RESUME_FILE,
    index=False
)

results_df.to_excel(
    FINAL_EXCEL_FILE,
    index=False
)

# ==========================================
# SUMMARY
# ==========================================

print("\nAVERAGE SCORES\n")

for metric in [
    "correctness",
    "completeness",
    "groundedness",
    "generalization",
    "relevance",
    "overall"
]:

    if len(results_df) > 0:

        print(
            f"{metric}: "
            f"{results_df[metric].mean():.2f}"
        )

print(
    f"\nRows Evaluated: "
    f"{len(results_df)}"
)

print(
    f"\nSaved:"
    f"\n- {RESUME_FILE}"
    f"\n- {FINAL_EXCEL_FILE}"
)
























# import pandas as pd

# from pydantic import BaseModel

# from langchain_groq import ChatGroq
# from langchain_core.prompts import ChatPromptTemplate


# # ==========================================
# # EVALUATION SCHEMA
# # ==========================================

# class EvaluationResponse(BaseModel):

#     correctness: float

#     completeness: float

#     groundedness: float

#     generalization: float

#     relevance: float

#     overall: float

#     reasoning: str


# # ==========================================
# # PROMPT
# # ==========================================
# EVALUATION_PROMPT = """
# You are evaluating an enterprise ticket resolution system.

# Compare the generated workflow against the ground-truth workflow.

# Do not require exact wording matches.

# Do not penalize reasonable abstraction.

# Generalized workflow actions should receive high scores when they preserve the intent of historical actions.

# ==================================================
# CORRECTNESS (0-10)
# ==================================================

# 9-10:
# Workflow actions are accurate and operationally correct.

# 7-8:
# Mostly correct with minor issues.

# 4-6:
# Some incorrect or questionable actions.

# 1-3:
# Major workflow errors.

# 0:
# Completely incorrect.

# ==================================================
# COMPLETENESS (0-10)
# ==================================================

# Evaluate whether important workflow activities are missing.

# High Score:
# Most key workflow activities are present.

# Low Score:
# Critical workflow activities are omitted.

# ==================================================
# GROUNDEDNESS (0-10)
# ==================================================

# Evaluate whether generated workflow actions are supported by the historical workflow.

# High Score:
# Most actions can be traced to historical evidence.

# Low Score:
# Many actions appear invented or unsupported.

# ==================================================
# GENERALIZATION (0-10)
# ==================================================

# Evaluate whether the workflow removes ticket-specific details while preserving operational intent.

# High Score:
# Reusable workflow with no ticket-specific details.

# Low Score:
# Copies historical incidents directly.

# ==================================================
# RELEVANCE (0-10)
# ==================================================

# Evaluate whether the workflow addresses the user's issue.

# High Score:
# Directly addresses all concerns.

# Low Score:
# Misses or ignores key concerns.

# ==================================================
# OVERALL (0-10)
# ==================================================

# Overall quality considering all dimensions.
# """


# # ==========================================
# # LOAD DATA
# # ==========================================

# df = pd.read_csv(
#     "ragas_input.csv"
# )



# # ==========================================
# # LLM
# # ==========================================
# from eval_config import GROQ_API_KEY, LLM_MODEL

# print("GROQ_API_KEY =", GROQ_API_KEY)
# print("LLM_MODEL =", LLM_MODEL)

# llm = ChatGroq(
#     model=LLM_MODEL,
#     groq_api_key=GROQ_API_KEY,
#     temperature=0
# )

# structured_llm = (
#     llm.with_structured_output(
#         EvaluationResponse
#     )
# )

# prompt = (
#     ChatPromptTemplate
#     .from_template(
#         EVALUATION_PROMPT
#     )
# )

# chain = prompt | structured_llm

# # ==========================================
# # EVALUATION LOOP
# # ==========================================

# results = []

# for index, row in df.iterrows():

#     print(
#         f"Evaluating {index+1}/{len(df)}"
#     )

#     try:

#         response = chain.invoke(
#             {
#                 "question":
#                     str(row["question"]),

#                 "ground_truth":
#                     str(row["ground_truth"]),

#                 "answer":
#                     str(row["answer"])
#             }
#         )

#         result = response.model_dump()

#         results.append(
#             {
#                 "question":
#                     row["question"],

#                 **result
#             }
#         )

#     except Exception as e:

#         print(
#             f"Failed row {index}: {e}"
#         )

# # ==========================================
# # SAVE RESULTS
# # ==========================================

# results_df = pd.DataFrame(
#     results
# )

# results_df.to_excel(
#     "groq_evaluation_results.xlsx",
#     index=False
# )

# # ==========================================
# # SUMMARY
# # ==========================================

# print("\nAVERAGE SCORES\n")

# for metric in [
#     "correctness",
#     "completeness",
#     "groundedness",
#     "generalization",
#     "relevance",
#     "overall"
# ]:

#     print(
#         f"{metric}: "
#         f"{results_df[metric].mean():.2f}"
#     )

# print(
#     "\nSaved: groq_evaluation_results.xlsx"
# )