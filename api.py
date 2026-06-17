import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CONFIDENCE_THRESHOLD
from inference import resolve_issue

# ==========================================
# FASTAPI APP
# ==========================================

app = FastAPI(
    title="Enterprise Ticket Resolution API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# REQUEST MODEL
# ==========================================

class ResolutionRequest(BaseModel):

    issue: str

# ==========================================
# RESPONSE MODEL
# ==========================================

class ResolutionResponse(BaseModel):

    resolution_steps: str | list

    source_tickets: list

# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/")
def health_check():

    return {
        "status": "running"
    }
# ==========================================
# RESOLUTION ENDPOINT
# ==========================================
@app.post(
    "/resolve",
    response_model=ResolutionResponse
)
def resolve_ticket(
    request: ResolutionRequest
):
    if not request.issue.strip():

        raise HTTPException(
            status_code=400,
            detail="Issue description cannot be empty."
        )

    try:

        result = resolve_issue(
            request.issue
        )

        confidence = result.get(
            "confidence",
            0.0
        )

        if confidence < CONFIDENCE_THRESHOLD:

            return {
                "resolution_steps": "",
                "source_tickets": []
            }

        return {
            
            "resolution_steps":
                result.get(
                    "recommended_resolution",
                    ""
                ),

            "source_tickets":
                result.get(
                    "source_tickets",
                    []
                )
        }


    except Exception as e:

        print("\n" + "=" * 80)
        print("ERROR IN /resolve")
        traceback.print_exc()
        print("=" * 80)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    




# @app.post(
#     "/resolve",
#     response_model=ResolutionResponse
# )
# def resolve_ticket(
#     request: ResolutionRequest
# ):

#     try:

#         result = resolve_issue(
#             request.issue
#         )

#         confidence = result.get(
#             "confidence",
#             0.0
#         )

#         if confidence < CONFIDENCE_THRESHOLD:

#             return {
#                 "resolution_steps": "",
#                 "source_tickets": []
#             }

#         return {
#             "resolution_steps":
#                 result.get(
#                     "recommended_resolution",
#                     ""
#                 ),

#             "source_tickets":
#                 result.get(
#                     "source_tickets",
#                     []
#                 )
#         }
#     except Exception as e:

#     raise HTTPException(
#         status_code=500,
#         detail=str(e)
#     )