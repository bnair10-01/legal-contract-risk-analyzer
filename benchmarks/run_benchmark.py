"""Run a labeled synthetic contract through legal-agent's API and score the result."""
import os
OUT = os.environ.get("BENCH_OUT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
os.makedirs(OUT, exist_ok=True)
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
import json, time, requests
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

B = BASE_URL

# (title, text, expected clause_type set, risky?)
CL = [
 ("Definitions", "\"Services\" means the software consulting services described in Exhibit A. \"Deliverables\" means all work product created under this Agreement.", {"definitions"}, False),
 ("Payment", "Client shall pay Provider a fixed fee of $50,000 payable in monthly installments. Invoices are due within 30 days; late amounts accrue interest at 1% per month.", {"payment"}, False),
 ("Confidentiality", "Each party shall keep the other party's Confidential Information strictly confidential and use it only to perform this Agreement for a period of three years.", {"confidentiality"}, False),
 ("Intellectual Property", "All Deliverables and any related patents, copyrights and know-how are the sole property of Client. Provider hereby irrevocably assigns all rights, including pre-existing Provider tools incorporated into the Deliverables, to Client without additional compensation.", {"IP"}, True),
 ("Limitation of Liability", "Provider's liability under this Agreement is unlimited and extends to all direct, indirect, incidental, special and consequential damages, including lost profits. Client's aggregate liability shall not exceed $1,000.", {"liability"}, True),
 ("Indemnification", "Provider shall indemnify, defend and hold harmless Client from any and all claims, losses and expenses, including those arising from Client's own negligence or willful misconduct, without any cap or time limit. Client has no indemnification obligations.", {"indemnification"}, True),
 ("Termination", "Client may terminate this Agreement at any time for any reason on one day's notice without penalty. Provider may terminate only for Client's uncured material breach after a 5-day cure period, and must continue performing during any dispute.", {"termination"}, True),
 ("Governing Law", "This Agreement is governed by the laws of the State of Delaware, and venue lies exclusively in the state courts of Wilmington, Delaware.", {"governing_law"}, False),
 ("Dispute Resolution", "Any dispute shall be resolved by binding arbitration administered by the AAA in Wilmington, Delaware, with each party bearing its own costs.", {"dispute_resolution"}, False),
 ("Non-Competition", "For five (5) years after termination, Provider shall not provide services to any business anywhere in the world that competes with Client or any of Client's affiliates.", {"non_compete"}, True),
 ("Assignment", "Provider may not assign this Agreement or any rights hereunder without Client's prior written consent. Client may assign freely, including upon a change of control.", {"assignment"}, False),
 ("Entire Agreement", "This Agreement constitutes the entire agreement between the parties and supersedes all prior discussions, representations and understandings.", {"entire_agreement"}, False),
]

doc = SimpleDocTemplate(f"{OUT}/sample_contract.pdf", pagesize=letter)
st = getSampleStyleSheet(); flow = [Paragraph("SERVICES AGREEMENT (synthetic specimen for software testing)", st["Title"]),
    Paragraph("This Services Agreement is entered into between Acme Corp (\"Client\") and Beacon Labs LLC (\"Provider\").", st["Normal"]), Spacer(1, 12)]
for i, (t, x, _, _) in enumerate(CL, 1):
    flow += [Paragraph(f"<b>{i}. {t}.</b> {x}", st["Normal"]), Spacer(1, 10)]
doc.build(flow)

t0 = time.time()
with open(f"{OUT}/sample_contract.pdf", "rb") as f:
    job = requests.post(f"{B}/api/jobs", files={"file": ("sample_contract.pdf", f, "application/pdf")}).json()["job_id"]
timeline, last = [], None
while True:
    j = requests.get(f"{B}/api/jobs/{job}").json()
    if j["status"] != last:
        timeline.append((j["status"], round(time.time() - t0, 1))); last = j["status"]; print(timeline[-1], flush=True)
    if j["status"] in ("done", "error") or time.time() - t0 > 900:
        break
    time.sleep(1)
total = time.time() - t0
cl = j["clauses"]
print("status:", j["status"], "error:", j.get("error"), "clauses:", len(cl), "total s:", round(total, 1))

rep = requests.get(f"{B}/api/jobs/{job}/report")
open(f"{OUT}/legal_report.pdf", "wb").write(rep.content)

by_num = {c["clause_number"]: c for c in cl}
type_ok = sev_ok = 0; rows = []
for i, (t, _, exp, risky) in enumerate(CL, 1):
    c = by_num.get(i)
    if not c: rows.append((i, t, None, None, risky)); continue
    ok = c["clause_type"] in exp; type_ok += ok
    flagged = c["risk_severity"] in ("high", "critical")
    sev_ok += (flagged == risky)
    rows.append((i, t, c["clause_type"], c["risk_severity"], risky, ok, round(c["risk_score"] or 0, 2), round(c["similarity_score"] or 0, 2)))
    print(f"{i:>2} {t:<24} type={c['clause_type']:<18} ok={ok!s:<5} sev={c['risk_severity']:<9} score={c['risk_score']:.2f} sim={c['similarity_score']:.2f}")
risky_idx = [i for i, (_, _, _, r) in enumerate(CL, 1) if r]
recall = sum(1 for i in risky_idx if by_num.get(i, {}).get("risk_severity") in ("high", "critical")) / len(risky_idx)
benign_idx = [i for i in range(1, 13) if i not in risky_idx]
fp = sum(1 for i in benign_idx if by_num.get(i, {}).get("risk_severity") in ("high", "critical"))
summary = {"job": job, "status": j["status"], "clauses_extracted": len(cl), "clauses_expected": len(CL), "type_accuracy": type_ok / len(CL),
           "risk_flag_agreement": sev_ok / len(CL), "high_risk_recall": recall, "benign_flagged_high": fp, "benign_total": len(benign_idx),
           "matched_to_template": sum(1 for c in cl if (c["similarity_score"] or 0) > 0.5), "timeline_s": timeline, "total_s": round(total, 1),
           "report_bytes": len(rep.content), "severity_counts": {s: sum(1 for c in cl if c["risk_severity"] == s) for s in ("critical", "high", "medium", "low")}}
json.dump({"summary": summary, "rows": rows, "clauses": cl}, open(f"{OUT}/legal_results.json", "w"), indent=1, default=str)
print(json.dumps(summary, indent=1))
