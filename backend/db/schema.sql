CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS clause_templates (
  id SERIAL PRIMARY KEY,
  contract_type TEXT NOT NULL,
  clause_type TEXT NOT NULL,
  standard_text TEXT NOT NULL,
  risk_baseline JSONB NOT NULL DEFAULT '{}',
  embedding vector(1536)
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now(),
  report_path TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS extracted_clauses (
  id SERIAL PRIMARY KEY,
  job_id UUID REFERENCES analysis_jobs(id) ON DELETE CASCADE,
  clause_number INT NOT NULL,
  clause_type TEXT,
  clause_text TEXT NOT NULL,
  embedding vector(1536),
  risk_severity TEXT,
  risk_score FLOAT,
  risk_rationale TEXT,
  similar_template_id INT REFERENCES clause_templates(id),
  similarity_score FLOAT,
  deviation_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_clause_templates_embedding
  ON clause_templates USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 10);

CREATE INDEX IF NOT EXISTS idx_extracted_clauses_embedding
  ON extracted_clauses USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 10);
