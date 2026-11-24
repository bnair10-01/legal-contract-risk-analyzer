"""Measure how responsive the API stays while an analysis job is running.

A blocked event loop (e.g. a synchronous LLM client inside `async def`) shows up as
multi-second status-poll latency. Prints the poll count and the slowest GET.
Requires benchmarks/out/sample_contract.pdf (created by run_benchmark.py).
"""
import os, time, requests

OUT = os.environ.get("BENCH_OUT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

with open(os.path.join(OUT, "sample_contract.pdf"), "rb") as f:
    job = requests.post(f"{BASE_URL}/api/jobs", files={"file": ("c.pdf", f, "application/pdf")}).json()["job_id"]
t0 = time.time(); lat = []
while time.time() - t0 < 90:
    s = time.time()
    j = requests.get(f"{BASE_URL}/api/jobs/{job}", timeout=60).json()
    lat.append((round(s - t0, 1), round((time.time() - s) * 1000), j["status"]))
    if j["status"] in ("done", "error"):
        break
    time.sleep(0.5)
print("polls:", len(lat))
print("slowest GET ms:", max(l[1] for l in lat))
print("polls slower than 1s:", [l for l in lat if l[1] > 1000])
