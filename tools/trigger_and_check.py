"""Trigger the check-token workflow via API, wait for it to finish, fetch logs."""
import io, os, sys, time, zipfile, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
GH = (os.getenv("GITHUB_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {GH}", "Accept": "application/vnd.github+json"}
REPO = "Travd40/travis-content-agent"

print("Triggering check-token workflow...")
disp = requests.post(
    f"https://api.github.com/repos/{REPO}/actions/workflows/check-token.yml/dispatches",
    headers=H, json={"ref": "main"},
)
if disp.status_code != 204:
    print(f"FAIL: dispatch returned {disp.status_code} {disp.text}"); sys.exit(1)
print("Triggered. Waiting for it to finish...")

# Poll for the new run
start = time.time()
run_id = None
for i in range(40):
    time.sleep(3)
    runs = requests.get(
        f"https://api.github.com/repos/{REPO}/actions/workflows/check-token.yml/runs",
        headers=H, params={"per_page": 1, "event": "workflow_dispatch"},
    ).json()
    if not runs.get("workflow_runs"): continue
    r = runs["workflow_runs"][0]
    # Only the one we just kicked off (created in last 2 min)
    if r["status"] == "completed":
        run_id = r["id"]; print(f"Done. {r['conclusion']}  ({int(time.time()-start)}s)")
        break
    print(f"  {r['status']}...")

if not run_id:
    print("Timed out waiting."); sys.exit(1)

resp = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/logs",
                    headers=H, allow_redirects=True)
zf = zipfile.ZipFile(io.BytesIO(resp.content))
for n in zf.namelist():
    if n.endswith("_check.txt"):
        raw = zf.read(n).decode("utf-8", errors="replace")
        start_i = raw.find("Token length")
        end_i = raw.find("Done. No posts created.")
        if start_i != -1:
            chunk = raw[start_i:end_i+len("Done. No posts created.")] if end_i != -1 else raw[start_i:start_i+3000]
            cleaned = []
            for line in chunk.splitlines():
                if len(line) > 30 and line[4] == "-" and line[10] == "T":
                    line = line[29:]
                cleaned.append(line)
            print("\n--- GitHub secret diagnostic ---")
            print("\n".join(cleaned))
        break
