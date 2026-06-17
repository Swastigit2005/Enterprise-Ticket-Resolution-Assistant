import pandas as pd

from inference import resolve_issue

# ==========================================
# LOAD TEST DATASET
# ==========================================

df = pd.read_excel(
    "evaluation_test_dataset.xlsx"
)

evaluation_rows = []

# ==========================================
# RUN EVALUATION
# ==========================================

for index, row in df.iterrows():

    query = row["Issue_Description"]

    ground_truth = row["Resolution_Steps"]

    print(
        f"\nRunning {index + 1}/{len(df)}"
    )

    try:

        result = resolve_issue(
            query
        )

        # ----------------------------------
        # Generated Answer
        # ----------------------------------

        generated_answer = result.get(
            "recommended_resolution",
            ""
        )

        if isinstance(
            generated_answer,
            list
        ):

            generated_answer = "\n".join(
                generated_answer
            )

        # ----------------------------------
        # Retrieved Context
        # ----------------------------------

        contexts = []

        for ticket in result.get(
            "source_tickets",
            []
        ):

            contexts.append(
                ticket.get(
                    "issue_description",
                    ""
                )
            )

        evaluation_rows.append(
            {
                "question":
                    query,

                "answer":
                    generated_answer,

                "contexts":
                    str(contexts),

                "ground_truth":
                    ground_truth
            }
        )

    except Exception as e:

        print(
            f"Failed: {e}"
        )

# ==========================================
# SAVE DATASET
# ==========================================

evaluation_df = pd.DataFrame(
    evaluation_rows
)

evaluation_df.to_csv(
    "ragas_input.csv",
    index=False
)

print(
    "\nRAGAS dataset created successfully."
)




















# import pandas as pd

# from inference_eval import resolve_issue

# # ==========================================
# # LOAD EXISTING RESULTS
# # ==========================================

# existing_df = pd.read_csv(
#     "ragas_input.csv"
# )

# evaluation_rows = existing_df.to_dict(
#     orient="records"
# )

# start_index = len(
#     evaluation_rows
# )

# print(
#     f"Resuming from row {start_index + 1}"
# )

# # ==========================================
# # LOAD TEST DATASET
# # ==========================================

# test_df = pd.read_excel(
#     "evaluation_test_dataset.xlsx"
# )

# # Skip already processed rows

# test_df = test_df.iloc[
#     start_index:
# ]

# # ==========================================
# # RUN EVALUATION
# # ==========================================

# total_rows = start_index + len(test_df)

# for index, row in enumerate(
#     test_df.iterrows(),
#     start=start_index + 1
# ):

#     _, row = row

#     query = row[
#         "Issue_Description"
#     ]

#     ground_truth = row[
#         "Resolution_Steps"
#     ]

#     print(
#         f"\nRunning {index}/{total_rows}"
#     )

#     try:

#         result = resolve_issue(
#             query
#         )

#         # ----------------------------------
#         # GENERATED ANSWER
#         # ----------------------------------

#         generated_answer = result.get(
#             "recommended_resolution",
#             ""
#         )

#         if isinstance(
#             generated_answer,
#             list
#         ):

#             generated_answer = "\n".join(
#                 generated_answer
#             )

#         # ----------------------------------
#         # RETRIEVED CONTEXTS
#         # ----------------------------------

#         contexts = []

#         for ticket in result.get(
#             "source_tickets",
#             []
#         ):

#             contexts.append(
#                 ticket.get(
#                     "issue_description",
#                     ""
#                 )
#             )

#         row_data = {
#             "question":
#                 query,

#             "answer":
#                 generated_answer,

#             "contexts":
#                 str(contexts),

#             "ground_truth":
#                 ground_truth
#         }

#         evaluation_rows.append(
#             row_data
#         )

#         # ----------------------------------
#         # SAVE AFTER EVERY ROW
#         # ----------------------------------

#         pd.DataFrame(
#             evaluation_rows
#         ).to_csv(
#             "ragas_input.csv",
#             index=False
#         )

#         print(
#             "Saved."
#         )

#     except Exception as e:

#         print(
#             f"Failed: {e}"
#         )

# # ==========================================
# # COMPLETE
# # ==========================================

# print(
#     "\nDataset generation completed."
# )

# print(
#     f"Total rows: {len(evaluation_rows)}"
# )