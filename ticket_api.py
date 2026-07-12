from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import BackgroundTasks

from pydantic import BaseModel
import asyncio
from db import execute_query
from inference import diagnose_retrieval, resolve_issue
from logger import logger

# ==========================================
# REQUEST MODEL
# ==========================================

class ResolutionUpdateRequest(
    BaseModel
):

    resolution: str

# ==========================================
# FASTAPI APP
# ==========================================

app = FastAPI(
    title="Advocate Workspace API",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/")
def health():

    return {
        "status": "running"
    }


# ==========================================
# ALL TICKETS
# ==========================================

@app.get("/tickets")
async def get_all_tickets():

    try:

        return await asyncio.to_thread(
            execute_query,
            """
            SELECT
                ticket_id,
                issue_title,
                status,
                priority,
                customer_name,
                customer_email,
                assigned_to,
                assigned_date,
                ticket_date
            FROM tickets
            ORDER BY ticket_date DESC
            """
        )

    except Exception:

        logger.exception(
            "Failed to fetch all tickets."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch tickets."
        )
# ==========================================
# OPEN TICKETS
# ==========================================

@app.get("/tickets/open")
async def get_open_tickets():

    try:

        return await asyncio.to_thread(
            execute_query,
            """
            SELECT
                ticket_id,
                issue_title,
                status,
                priority,
                customer_name,
                assigned_to,
                ticket_date
            FROM tickets
            WHERE status='Open'
            ORDER BY ticket_date DESC
            """
        )

    except Exception:

        logger.exception(
            "Failed to fetch open tickets."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch open tickets."
        )

# ==========================================
# IN PROGRESS TICKETS
# ==========================================

@app.get("/tickets/inprogress")
async def get_inprogress_tickets():

    try:

        return await asyncio.to_thread(
            execute_query,
            """
            SELECT
                ticket_id,
                issue_title,
                status,
                priority,
                customer_name,
                assigned_to,
                ticket_date
            FROM tickets
            WHERE status='Inprogress'
            ORDER BY ticket_date DESC
            """
        )

    except Exception:

        logger.exception(
            "Failed to fetch in-progress tickets."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch in-progress tickets."
        )


# ==========================================
# RESOLVED TICKETS
# ==========================================

@app.get("/tickets/resolved")
async def get_resolved_tickets():

    try:

        return await asyncio.to_thread(
            execute_query,
            """
            SELECT
                ticket_id,
                issue_title,
                status,
                priority,
                customer_name,
                assigned_to,
                resolved_date
            FROM tickets
            WHERE status='Resolved'
            ORDER BY resolved_date DESC
            """
        )

    except Exception:

        logger.exception(
            "Failed to fetch resolved tickets."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch resolved tickets."
        )


# ==========================================
# SINGLE TICKET
# ==========================================

@app.get("/ticket/{ticket_id}")
async def get_ticket(
    ticket_id: str
):

    try:

        ticket = await asyncio.to_thread(
            execute_query,
            """
            SELECT *
            FROM tickets
            WHERE ticket_id=%s
            """,
            (ticket_id,),
            True
        )

        if not ticket:

            logger.warning(
                f"Ticket not found : {ticket_id}"
            )

            raise HTTPException(
                status_code=404,
                detail="Ticket not found."
            )

        return ticket

    except HTTPException:

        raise

    except Exception:

        logger.exception(
            f"Failed to fetch ticket : {ticket_id}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch ticket."
        )


# ==========================================
# GENERATE RESOLUTION
# ==========================================

@app.post(
    "/ticket/{ticket_id}/generate-resolution"
)
async def generate_resolution(
    ticket_id: str
):

    try:

        ticket = await asyncio.to_thread(
            execute_query,
            """
            SELECT *
            FROM tickets
            WHERE ticket_id=%s
            """,
            (ticket_id,),
            True
        )

        if not ticket:

            logger.warning(
                f"Ticket not found : {ticket_id}"
            )

            raise HTTPException(
                status_code=404,
                detail="Ticket not found."
            )

        result = await asyncio.to_thread(
            resolve_issue,
            ticket["issue_description"]
        )

        generated_resolution = result.get(
            "recommended_resolution",
            ""
        )

        if isinstance(
            generated_resolution,
            list
        ):
            generated_resolution = "\n".join(
                generated_resolution
            )

        source_tickets = result.get(
            "source_tickets",
            []
        )

        tasks = []

        for source in source_tickets:

            tasks.append(

                asyncio.to_thread(

                    execute_query,

                    """
                    INSERT IGNORE INTO
                    ticket_references
                    (
                        ticket_id,
                        source_ticket_id
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    """,

                    (
                        ticket_id,
                        source["ticket_id"]
                    ),

                    False,
                    True

                )

            )

        await asyncio.gather(*tasks)

        logger.info(
            f"Resolution generated : {ticket_id}"
        )

        return {

            "ticket_id": ticket_id,

            "resolution_generated": generated_resolution,

            "source_tickets": source_tickets,

            "status": result.get("status", "resolved"),

            "resolution_available": result.get("resolution_available", False),

            "confidence": result.get("confidence", 0.0),

            "validation_feedback": result.get("validation_feedback", ""),

            "human_handoff": result.get("human_handoff", False),

            "handoff_reason": result.get("handoff_reason"),

            "agent_diagnostics": result.get("agent_diagnostics", {})

        }

    except HTTPException:

        raise

    except Exception:

        logger.exception(
            f"Resolution generation failed : {ticket_id}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to generate resolution."
        )

# ==========================================
# RETRIEVAL DIAGNOSTICS
# ==========================================

@app.get("/ticket/{ticket_id}/retrieval-diagnostics")
async def retrieval_diagnostics(ticket_id: str):

    try:
        ticket = await asyncio.to_thread(
            execute_query,
            """
            SELECT issue_description
            FROM tickets
            WHERE ticket_id=%s
            """,
            (ticket_id,),
            True
        )

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found.")

        return await asyncio.to_thread(
            diagnose_retrieval,
            ticket["issue_description"]
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            f"Retrieval diagnostics failed : {ticket_id}"
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to run retrieval diagnostics."
        )


# ==========================================
# SOURCE REFERENCES
# ==========================================

@app.get(
    "/ticket/{ticket_id}/references"
)
async def get_ticket_references(
    ticket_id: str
):

    try:

        return await asyncio.to_thread(
            execute_query,
            """
            SELECT
                tr.source_ticket_id,
                t.issue_title,
                t.status
            FROM ticket_references tr
            INNER JOIN tickets t
                ON tr.source_ticket_id = t.ticket_id
            WHERE tr.ticket_id=%s
            """,
            (ticket_id,)
        )

    except Exception:

        logger.exception(
            f"Failed to fetch source tickets : {ticket_id}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch source tickets."
        )


# ==========================================
# SAVE RESOLUTION
# ==========================================

@app.put(
    "/ticket/{ticket_id}/save-resolution"
)
async def save_resolution(
    ticket_id: str,
    request: ResolutionUpdateRequest
):

    try:

        await asyncio.to_thread(
            execute_query,
            """
            UPDATE tickets
            SET
                resolution_final=%s
            WHERE ticket_id=%s
            """,
            (
                request.resolution,
                ticket_id
            ),
            False,
            True
        )

        logger.info(
            f"Resolution saved : {ticket_id}"
        )

        return {
            "message": "Resolution saved"
        }

    except Exception:

        logger.exception(
            f"Failed to save resolution : {ticket_id}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to save resolution."
        )

# ==========================================
# RESOLVE TICKET
# ==========================================

@app.put(
    "/ticket/{ticket_id}/resolve"
)
async def resolve_ticket(
    ticket_id: str
):

    try:

        await asyncio.to_thread(
            execute_query,
            """
            UPDATE tickets
            SET
                status='Resolved',
                resolved_date=NOW(),
                ingested=FALSE
            WHERE ticket_id=%s
            """,
            (ticket_id,),
            False,
            True
        )

        logger.info(
            f"Ticket resolved : {ticket_id}"
        )

        return {
            "message": "Ticket resolved"
        }

    except Exception:

        logger.exception(
            f"Failed to resolve ticket : {ticket_id}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to resolve ticket."
        )

# ==========================================
# ADMIN DASHBOARD STATS
# ==========================================

@app.get("/admin/stats")
async def admin_stats():

    try:

        total = asyncio.to_thread(
            execute_query,
            """
            SELECT COUNT(*) AS count
            FROM tickets
            """,
            None,
            True
        )

        open_count = asyncio.to_thread(
            execute_query,
            """
            SELECT COUNT(*) AS count
            FROM tickets
            WHERE status='Open'
            """,
            None,
            True
        )

        inprogress_count = asyncio.to_thread(
            execute_query,
            """
            SELECT COUNT(*) AS count
            FROM tickets
            WHERE status='Inprogress'
            """,
            None,
            True
        )

        resolved_count = asyncio.to_thread(
            execute_query,
            """
            SELECT COUNT(*) AS count
            FROM tickets
            WHERE status='Resolved'
            """,
            None,
            True
        )

        vectorized_count = asyncio.to_thread(
            execute_query,
            """
            SELECT COUNT(*) AS count
            FROM tickets
            WHERE ingested=1
            """,
            None,
            True
        )

        not_ingested_count = asyncio.to_thread(
            execute_query,
            """
            SELECT COUNT(*) AS count
            FROM tickets
            WHERE status='Resolved'
            AND ingested=0
            """,
            None,
            True
        )

        (
            total,
            open_count,
            inprogress_count,
            resolved_count,
            vectorized_count,
            not_ingested_count

        ) = await asyncio.gather(

            total,
            open_count,
            inprogress_count,
            resolved_count,
            vectorized_count,
            not_ingested_count

        )

        return {

            "total": total["count"],

            "open": open_count["count"],

            "inprogress": inprogress_count["count"],

            "resolved": resolved_count["count"],

            "not_ingested": not_ingested_count["count"],

            "vectorized": vectorized_count["count"]

        }

    except Exception:

        logger.exception(
            "Failed to load admin dashboard statistics."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to load dashboard statistics."
        )
    
# ==========================================
# TRIGGER KNOWLEDGE INGESTION
# ==========================================

@app.post("/admin/trigger-ingestion")
async def trigger_ingestion(
    background_tasks: BackgroundTasks
):

    try:

        from ingestion import ingest_tickets

        background_tasks.add_task(
            ingest_tickets
        )

        logger.info(
            "Knowledge ingestion triggered."
        )

        return {

            "status": "success",

            "message": "Knowledge ingestion started successfully."

        }

    except Exception:

        logger.exception(
            "Knowledge ingestion failed."
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to start knowledge ingestion."
        )