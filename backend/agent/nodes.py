import asyncio
import io
import json
import os
import traceback

import anthropic
import pdfplumber
from pydantic import BaseModel

from backend.agent.state import AgentState
from backend.config import settings
from backend.db.connection import get_db_pool
from backend.services.embedder import embed_text
from backend.services.report_generator import build_pdf

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


# ── Pydantic models for structured outputs ──────────────────────────────────

class Clause(BaseModel):
    clause_number: int
    clause_type: str
    clause_text: str


class ClauseList(BaseModel):
    clauses: list[Clause]


class RiskedClause(BaseModel):
    clause_number: int
    risk_severity: str
    risk_score: float
    risk_rationale: str


class RiskReport(BaseModel):
    results: list[RiskedClause]


# ── Helper ───────────────────────────────────────────────────────────────────

async def _update_status(job_id: str, status: str) -> None:
    pool = await get_db_pool()
    await pool.execute("UPDATE analysis_jobs SET status=$1 WHERE id=$2", status, job_id)


# ── Nodes ────────────────────────────────────────────────────────────────────

async def extract_node(state: AgentState) -> AgentState:
    await _update_status(state["job_id"], "extracting")
    try:
        with pdfplumber.open(io.BytesIO(state["pdf_bytes"])) as pdf:
            raw_text = "\n\n".join(p.extract_text() or "" for p in pdf.pages)

        response = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=8192,
            tools=[{
                "name": "submit_clauses",
                "description": "Submit the extracted clauses from the contract",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "clauses": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "clause_number": {"type": "integer"},
                                    "clause_type": {
                                        "type": "string",
                                        "enum": [
                                            "liability",
                                            "indemnification",
                                            "termination",
                                            "IP",
                                            "confidentiality",
                                            "payment",
                                            "representations_warranties",
                                            "governing_law",
                                            "dispute_resolution",
                                            "force_majeure",
                                            "assignment",
                                            "non_compete",
                                            "non_solicitation",
                                            "data_privacy",
                                            "audit_rights",
                                            "notice",
                                            "amendment",
                                            "entire_agreement",
                                            "severability",
                                            "waiver",
                                            "definitions",
                                            "other"
                                        ]
                                    },
                                    "clause_text": {"type": "string"}
                                },
                                "required": ["clause_number", "clause_type", "clause_text"]
                            }
                        }
                    },
                    "required": ["clauses"]
                }
            }],
            tool_choice={"type": "tool", "name": "submit_clauses"},
            messages=[{
                "role": "user",
                "content": (
                    "You are a legal analyst. Extract and enumerate every distinct clause from this contract.\n\n"
                    "For each clause, choose the MOST SPECIFIC clause_type from the enum. Only use 'other' "
                    "as a true last resort when no other type fits. Guidance:\n"
                    "- liability → limitation of liability, damage caps, exclusions of consequential damages\n"
                    "- indemnification → indemnify, defend, hold harmless\n"
                    "- termination → termination for cause/convenience, expiration, survival\n"
                    "- IP → intellectual property, ownership, work for hire, licenses, patents, copyrights\n"
                    "- confidentiality → NDA, non-disclosure, confidential information\n"
                    "- payment → fees, invoices, pricing, late fees, taxes\n"
                    "- representations_warranties → reps, warranties, covenants, 'represents and warrants'\n"
                    "- governing_law → choice of law, jurisdiction, venue\n"
                    "- dispute_resolution → arbitration, mediation, litigation process\n"
                    "- force_majeure → acts of God, unforeseeable events, excuse of performance\n"
                    "- assignment → assignment, transfer of rights, change of control\n"
                    "- non_compete → non-competition, restricted activities\n"
                    "- non_solicitation → no-hire, no-solicit of employees or customers\n"
                    "- data_privacy → data protection, GDPR, CCPA, personal data\n"
                    "- audit_rights → right to audit, inspection, records\n"
                    "- notice → notice provisions, how to send notices\n"
                    "- amendment → modification, amendment of agreement\n"
                    "- entire_agreement → integration clause, merger clause\n"
                    "- severability → severability of provisions\n"
                    "- waiver → waiver of rights\n"
                    "- definitions → defined terms section\n\n"
                    f"{raw_text[:50000]}"
                )
            }]
        )

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise ValueError(f"No tool_use block in response. Content types: {[b.type for b in response.content]}")
        clauses = tool_use.input.get("clauses")
        if not clauses:
            raise ValueError(f"tool_use.input missing 'clauses'. Got keys: {list(tool_use.input.keys())}")

        pool = await get_db_pool()
        for c in clauses:
            embedding = await embed_text(c["clause_text"])
            await pool.execute(
                """INSERT INTO extracted_clauses
                   (job_id, clause_number, clause_type, clause_text, embedding)
                   VALUES ($1, $2, $3, $4, $5::vector)""",
                state["job_id"], c["clause_number"], c["clause_type"],
                c["clause_text"], str(embedding),
            )

        return {**state, "raw_text": raw_text, "clauses": clauses, "error": None, "retry_count": 0}

    except Exception as e:
        return {**state, "error": str(e), "retry_count": state.get("retry_count", 0) + 1}


async def classify_node(state: AgentState) -> AgentState:
    await _update_status(state["job_id"], "classifying")
    try:
        clause_text = "\n\n".join(
            f"[{c['clause_number']}] ({c['clause_type']}): {c['clause_text']}"
            for c in state["clauses"]
        )

        response = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=8192,
            tools=[{
                "name": "submit_risk_analysis",
                "description": "Submit the risk analysis results for each clause",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "clause_number": {"type": "integer"},
                                    "risk_severity": {
                                        "type": "string",
                                        "enum": ["critical", "high", "medium", "low"]
                                    },
                                    "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
                                    "risk_rationale": {"type": "string"}
                                },
                                "required": ["clause_number", "risk_severity", "risk_score", "risk_rationale"]
                            }
                        }
                    },
                    "required": ["results"]
                }
            }],
            tool_choice={"type": "tool", "name": "submit_risk_analysis"},
            messages=[{
                "role": "user",
                "content": (
                    "You are a senior legal risk analyst. For each numbered clause below, assign:\n"
                    "- risk_severity: critical|high|medium|low\n"
                    "- risk_score: float 0.0 (no risk) to 1.0 (extreme risk)\n"
                    "- risk_rationale: one sentence explaining the key risk\n\n"
                    f"{clause_text[:50000]}"
                )
            }]
        )

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise ValueError(f"No tool_use block in classify response. Content types: {[b.type for b in response.content]}")
        results = tool_use.input.get("results")
        if not results:
            raise ValueError(f"tool_use.input missing 'results'. Got keys: {list(tool_use.input.keys())}")
        risk_map = {r["clause_number"]: r for r in results}

        classified = []
        pool = await get_db_pool()
        for c in state["clauses"]:
            r = risk_map.get(c["clause_number"], {})
            enriched = {
                **c,
                "risk_severity": r.get("risk_severity", "unknown"),
                "risk_score": r.get("risk_score", 0.0),
                "risk_rationale": r.get("risk_rationale", ""),
            }
            classified.append(enriched)
            await pool.execute(
                """UPDATE extracted_clauses
                   SET risk_severity=$1, risk_score=$2, risk_rationale=$3
                   WHERE job_id=$4 AND clause_number=$5""",
                enriched["risk_severity"], enriched["risk_score"],
                enriched["risk_rationale"], state["job_id"], c["clause_number"],
            )

        return {**state, "classified_clauses": classified, "error": None, "retry_count": 0}

    except Exception as e:
        return {**state, "error": str(e), "retry_count": state.get("retry_count", 0) + 1}


async def compare_node(state: AgentState) -> AgentState:
    await _update_status(state["job_id"], "comparing")
    try:
        pool = await get_db_pool()
        compared = []

        for clause in state["classified_clauses"]:
            embedding = await embed_text(clause["clause_text"])

            row = await pool.fetchrow(
                """
                SELECT id, standard_text, risk_baseline,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM clause_templates
                ORDER BY embedding <=> $1::vector
                LIMIT 1
                """,
                str(embedding),
            )

            deviation = ""
            similar_id = None
            similarity = 0.0

            if row and float(row["similarity"]) > 0.5:
                similar_id = int(row["id"])
                similarity = float(row["similarity"])

                dev_response = await client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=256,
                    messages=[{"role": "user", "content": (
                        f"Standard clause:\n{row['standard_text']}\n\n"
                        f"Contract clause:\n{clause['clause_text']}\n\n"
                        "In one concise sentence, describe the key deviation or risk compared to standard."
                    )}]
                )
                deviation = next((b.text for b in dev_response.content if hasattr(b, "text")), "")

            enriched = {
                **clause,
                "similar_template_id": similar_id,
                "similarity_score": similarity,
                "deviation_notes": deviation,
            }
            compared.append(enriched)

            await pool.execute(
                """UPDATE extracted_clauses
                   SET similar_template_id=$1, similarity_score=$2, deviation_notes=$3
                   WHERE job_id=$4 AND clause_number=$5""",
                similar_id, similarity, deviation,
                state["job_id"], clause["clause_number"],
            )

        return {**state, "compared_clauses": compared, "error": None, "retry_count": 0}

    except Exception as e:
        return {**state, "error": str(e), "retry_count": state.get("retry_count", 0) + 1}


async def report_node(state: AgentState) -> AgentState:
    await _update_status(state["job_id"], "reporting")
    try:
        clauses = state["compared_clauses"]
        n_critical = sum(1 for c in clauses if c.get("risk_severity") == "critical")
        n_high = sum(1 for c in clauses if c.get("risk_severity") == "high")
        n_medium = sum(1 for c in clauses if c.get("risk_severity") == "medium")
        n_low = sum(1 for c in clauses if c.get("risk_severity") == "low")

        summary_response = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            messages=[{"role": "user", "content": (
                f"Write a 3-paragraph executive summary for a legal contract risk report.\n"
                f"Contract: {state['filename']}\n"
                f"Total clauses: {len(clauses)}\n"
                f"Critical risks: {n_critical}, High risks: {n_high}, "
                f"Medium risks: {n_medium}, Low risks: {n_low}\n\n"
                "Top risk findings:\n" +
                "\n".join(
                    f"- Clause {c['clause_number']} ({c['clause_type']}): {c['risk_rationale']}"
                    for c in sorted(clauses, key=lambda x: x.get("risk_score", 0), reverse=True)[:5]
                ) +
                "\n\nBe professional, specific, and actionable. Recommend next steps."
            )}]
        )
        executive_summary = next(
            (b.text for b in summary_response.content if hasattr(b, "text")), ""
        )

        os.makedirs(settings.reports_dir, exist_ok=True)
        report_path = f"{settings.reports_dir}/{state['job_id']}.pdf"
        await asyncio.to_thread(
            build_pdf,
            path=report_path,
            filename=state["filename"],
            executive_summary=executive_summary,
            clauses=clauses,
        )

        pool = await get_db_pool()
        await pool.execute(
            "UPDATE analysis_jobs SET status='done', report_path=$1 WHERE id=$2",
            report_path, state["job_id"],
        )

        return {**state, "report_path": report_path, "error": None}

    except Exception as e:
        tb = traceback.format_exc()
        return {**state, "error": f"{e}\n{tb}", "retry_count": state.get("retry_count", 0) + 1}


async def error_node(state: AgentState) -> AgentState:
    pool = await get_db_pool()
    await pool.execute(
        "UPDATE analysis_jobs SET status='error', error=$1 WHERE id=$2",
        state.get("error", "Unknown error"), state["job_id"],
    )
    return state
