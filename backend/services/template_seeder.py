"""Seed standard clause templates into the database. Run once at startup."""
import asyncio
import json
import pathlib
from backend.db.connection import get_db_pool
from backend.services.embedder import embed_text

TEMPLATES_DIR = pathlib.Path(__file__).parents[2] / "templates"


async def seed_templates() -> None:
    pool = await get_db_pool()
    for json_file in TEMPLATES_DIR.glob("*.json"):
        clauses = json.loads(json_file.read_text())
        for clause in clauses:
            existing = await pool.fetchval(
                "SELECT id FROM clause_templates WHERE contract_type=$1 AND clause_type=$2 AND standard_text=$3",
                clause["contract_type"], clause["clause_type"], clause["standard_text"],
            )
            if existing:
                continue
            embedding = await embed_text(clause["standard_text"])
            await pool.execute(
                """
                INSERT INTO clause_templates (contract_type, clause_type, standard_text, risk_baseline, embedding)
                VALUES ($1, $2, $3, $4, $5::vector)
                """,
                clause["contract_type"],
                clause["clause_type"],
                clause["standard_text"],
                json.dumps(clause["risk_baseline"]),
                str(embedding),
            )
            print(f"Seeded {clause['contract_type']} / {clause['clause_type']}")
    print("Template seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed_templates())
