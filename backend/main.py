import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.agent.graph import build_graph
from backend.agent.state import AgentState
from backend.config import settings
from backend.db.connection import close_db_pool, get_db_pool
from backend.services.template_seeder import seed_templates

app = FastAPI(title="Legal Contract Risk Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    pool = await get_db_pool()
    schema = Path(__file__).parent / "db" / "schema.sql"
    await pool.execute(schema.read_text())
    await seed_templates()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db_pool()


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    job_id = str(uuid.uuid4())
    pool = await get_db_pool()
    await pool.execute(
        "INSERT INTO analysis_jobs (id, filename) VALUES ($1, $2)",
        job_id, file.filename,
    )

    asyncio.create_task(_run_agent(job_id, pdf_bytes, file.filename))
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    pool = await get_db_pool()
    row = await pool.fetchrow(
        "SELECT id, filename, status, created_at, report_path, error FROM analysis_jobs WHERE id=$1",
        job_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    clauses = []
    if row["status"] in ("comparing", "reporting", "done"):
        rows = await pool.fetch(
            """SELECT clause_number, clause_type, risk_severity, risk_score,
                      risk_rationale, similarity_score, deviation_notes
               FROM extracted_clauses WHERE job_id=$1
               ORDER BY clause_number""",
            job_id,
        )
        clauses = [dict(r) for r in rows]

    return {
        "job_id": str(row["id"]),
        "filename": row["filename"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "has_report": bool(row["report_path"]),
        "error": row["error"],
        "clauses": clauses,
    }


@app.get("/api/jobs/{job_id}/report")
async def download_report(job_id: str):
    pool = await get_db_pool()
    row = await pool.fetchrow(
        "SELECT report_path, filename FROM analysis_jobs WHERE id=$1 AND status='done'",
        job_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Report not ready or job not found")

    report_path = row["report_path"]
    if not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="Report file missing")

    safe_name = "".join(c for c in row["filename"] if c.isalnum() or c in "._- ").rstrip()
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"risk_report_{safe_name}",
    )


async def _run_agent(job_id: str, pdf_bytes: bytes, filename: str) -> None:
    graph = build_graph()
    initial_state: AgentState = {
        "job_id": job_id,
        "pdf_bytes": pdf_bytes,
        "filename": filename,
        "raw_text": "",
        "clauses": [],
        "classified_clauses": [],
        "compared_clauses": [],
        "report_path": None,
        "error": None,
        "retry_count": 0,
    }
    try:
        await graph.ainvoke(initial_state)
    except Exception as e:
        pool = await get_db_pool()
        await pool.execute(
            "UPDATE analysis_jobs SET status='error', error=$1 WHERE id=$2",
            str(e), job_id,
        )
