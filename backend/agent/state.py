from typing import TypedDict, Optional


class AgentState(TypedDict):
    job_id: str
    pdf_bytes: bytes
    filename: str
    raw_text: str
    clauses: list[dict]
    classified_clauses: list[dict]
    compared_clauses: list[dict]
    report_path: Optional[str]
    error: Optional[str]
    retry_count: int
