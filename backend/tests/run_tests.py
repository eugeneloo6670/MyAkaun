"""
AccountMaxxer backend verification — 7-test suite.
Run from the backend/ directory with: py -3.12 tests/run_tests.py
The script manages its own server lifecycle and uses a fresh database.

This suite locks in the fix for the void-guard over-block bug (commit cbffcd2):
TEST 2 must PASS (void allowed when other purchases remain) and TEST 3 must
PASS (void blocked when it would orphan a payment).
"""
import subprocess, time, os, sys, sqlite3, requests, signal
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date

# This file lives in backend/tests/ — the server and DB live one level up.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE = "http://127.0.0.1:8000"
DB_PATH = os.path.join(BACKEND_DIR, "hermes_accounting.db")
TODAY = date.today().isoformat()

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
UNEXPECTED = "\033[93mUNEXPECTED\033[0m"

results = []

def log(test, status, evidence):
    results.append((test, status, evidence))
    tag = PASS if status == "PASS" else (FAIL if status == "FAIL" else UNEXPECTED)
    print(f"\n{'-'*60}")
    print(f"TEST {test} -- {tag}")
    print(evidence)

def post(path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(f"{BASE}{path}", json=body, headers=headers)

def get(path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(f"{BASE}{path}", headers=headers)

# ── Stop any running uvicorn ──────────────────────────────────────────────────
# Kill whatever process is listening on port 8000 (a stale uvicorn from a
# previous run holds the DB file open). Target by port, NOT by image name —
# a blanket `taskkill /IM python.exe` would kill this test script too.
def kill_port(port=8000):
    """Kill any process listening on the given port (Windows + Unix)."""
    try:
        netstat = subprocess.run(
            'netstat -ano -p tcp', shell=True, capture_output=True, text=True
        ).stdout
        my_pid = str(os.getpid())
        for line in netstat.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.split()[-1]
                if pid != my_pid and pid != "0":
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True,
                                   capture_output=True)
        time.sleep(1)
    except Exception as e:
        print(f"  port-kill warning: {e}")


print("Stopping any process on port 8000...")
kill_port()
time.sleep(1)

# ── Fresh DB ──────────────────────────────────────────────────────────────────
# Retry the delete — the OS may not release the file handle immediately.
if os.path.exists(DB_PATH):
    for attempt in range(10):
        try:
            os.remove(DB_PATH)
            print(f"Deleted {DB_PATH}")
            break
        except PermissionError:
            if attempt == 9:
                print("ERROR: could not delete DB — a process still holds it.")
                print("Close any running uvicorn/python and re-run.")
                sys.exit(1)
            time.sleep(1)

# ── Start server ──────────────────────────────────────────────────────────────
print("Starting uvicorn...")
srv = subprocess.Popen(
    ["py", "-3.12", "-m", "uvicorn", "main:app", "--port", "8000"],
    cwd=BACKEND_DIR,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, bufsize=1
)

# Wait for startup
startup_lines = []
for _ in range(60):
    line = srv.stdout.readline()
    if line:
        startup_lines.append(line.rstrip())
        print(" >", line.rstrip())
    if "Application startup complete" in line:
        break
    time.sleep(0.5)
else:
    print("ERROR: Server did not start in time")
    srv.terminate()
    sys.exit(1)

time.sleep(1)

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1 — App boots clean
# ═══════════════════════════════════════════════════════════════════════════════
r = get("/health")
if r.status_code == 200 and r.json().get("status") == "ok":
    log(1, "PASS", f"/health -> {r.json()}")
else:
    log(1, "FAIL", f"status={r.status_code} body={r.text}")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Over-block bug (key test)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n\n── TEST 2 ──")
rA = post("/api/entries/", {"date": TODAY, "type": "purchase", "supplier": "VoidTest",
    "gl_code": "5100", "gl_name": "Purchases", "amount": 5000, "sst_rate": 0,
    "sst_amount": 0, "total": 5000})
rB = post("/api/entries/", {"date": TODAY, "type": "purchase", "supplier": "VoidTest",
    "gl_code": "5100", "gl_name": "Purchases", "amount": 3000, "sst_rate": 0,
    "sst_amount": 0, "total": 3000})
rP = post("/api/entries/", {"date": TODAY, "type": "payment", "supplier": "VoidTest",
    "amount": 8000, "sst_rate": 0, "sst_amount": 0, "total": 8000,
    "paid": 8000, "balance_owed": 8000})

print(f"Purchase A: {rA.status_code} id={rA.json().get('id')}")
print(f"Purchase B: {rB.status_code} id={rB.json().get('id')}")
print(f"Payment:    {rP.status_code} id={rP.json().get('id')}")

B_id = rB.json().get("id")
rV = post(f"/api/entries/{B_id}/void", {"voided_by": "tester", "reason": "entered in error"})
print(f"Void B:     {rV.status_code} → {rV.text[:300]}")

if rV.status_code == 200:
    log(2, "PASS", f"Void of Purchase B allowed (status 200). Over-block bug is FIXED.")
elif rV.status_code in (400, 422):
    log(2, "FAIL", f"Over-block — void rejected: {rV.json().get('detail','')[:200]}")
else:
    log(2, "UNEXPECTED", f"status={rV.status_code} body={rV.text[:200]}")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Guard should block when sole purchase + payment
# ═══════════════════════════════════════════════════════════════════════════════
print("\n\n── TEST 3 ──")
r2A = post("/api/entries/", {"date": TODAY, "type": "purchase", "supplier": "VoidTest2",
    "gl_code": "5100", "gl_name": "Purchases", "amount": 4000, "sst_rate": 0,
    "sst_amount": 0, "total": 4000})
r2P = post("/api/entries/", {"date": TODAY, "type": "payment", "supplier": "VoidTest2",
    "amount": 4000, "sst_rate": 0, "sst_amount": 0, "total": 4000,
    "paid": 4000, "balance_owed": 4000})
A2_id = r2A.json().get("id")
r2V = post(f"/api/entries/{A2_id}/void", {"voided_by": "tester", "reason": "test"})
print(f"Void sole purchase with payment: {r2V.status_code} → {r2V.text[:300]}")

if r2V.status_code in (400, 422):
    log(3, "PASS", f"Correctly blocked: {r2V.json().get('detail','')[:200]}")
elif r2V.status_code == 200:
    log(3, "FAIL", "Guard did NOT block — sole purchase with payment was voided (orphaned payment)")
else:
    log(3, "UNEXPECTED", f"status={r2V.status_code} body={r2V.text[:200]}")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Audit log append-only triggers
# ═══════════════════════════════════════════════════════════════════════════════
print("\n\n── TEST 4 ──")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
row = cur.execute("SELECT id FROM audit_log LIMIT 1").fetchone()
update_blocked = delete_blocked = False
update_msg = delete_msg = ""

if row:
    row_id = row[0]
    try:
        cur.execute("UPDATE audit_log SET description='x' WHERE id=?", (row_id,))
        conn.commit()
        update_msg = "UPDATE succeeded (trigger missing!)"
    except sqlite3.IntegrityError as e:
        update_blocked = True
        update_msg = f"UPDATE blocked: {e}"
    except Exception as e:
        update_msg = f"UPDATE error (not IntegrityError): {e}"

    try:
        cur.execute("DELETE FROM audit_log WHERE id=?", (row_id,))
        conn.commit()
        delete_msg = "DELETE succeeded (trigger missing!)"
    except sqlite3.IntegrityError as e:
        delete_blocked = True
        delete_msg = f"DELETE blocked: {e}"
    except Exception as e:
        delete_msg = f"DELETE error (not IntegrityError): {e}"
else:
    update_msg = delete_msg = "No audit_log rows yet — run after entries exist"
    # Try anyway with dummy id
    try:
        cur.execute("UPDATE audit_log SET description='x' WHERE id=0")
        conn.commit()
    except sqlite3.IntegrityError as e:
        update_blocked = True
        update_msg = f"UPDATE blocked (even on no-op): {e}"

conn.close()

if update_blocked and delete_blocked:
    log(4, "PASS", f"{update_msg} | {delete_msg}")
else:
    log(4, "FAIL", f"{update_msg} | {delete_msg}")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5 — Bearer token auth
# ═══════════════════════════════════════════════════════════════════════════════
print("\n\n── TEST 5 ──")

# 5a — no token env: open
r5a = get("/api/entries/")
print(f"5a no-token-env, no-header: {r5a.status_code}")

# Restart with token
srv.terminate()
srv.wait()
kill_port()

env = os.environ.copy()
env["ACCOUNTMAXXER_API_TOKEN"] = "testsecret123"
srv2 = subprocess.Popen(
    ["py", "-3.12", "-m", "uvicorn", "main:app", "--port", "8000"],
    cwd=BACKEND_DIR,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, bufsize=1, env=env
)
for _ in range(40):
    line = srv2.stdout.readline()
    if "Application startup complete" in line:
        break
    time.sleep(0.5)
time.sleep(1)

r5c = get("/api/entries/")                          # no header → 401
r5d = get("/api/entries/", token="testsecret123")   # correct token → 200
r5e = get("/health")                                # health public → 200
print(f"5c no-header (want 401): {r5c.status_code}")
print(f"5d correct token (want 200): {r5d.status_code}")
print(f"5e /health no-token (want 200): {r5e.status_code}")

pass5 = (r5a.status_code == 200 and r5c.status_code in (401,403)
         and r5d.status_code == 200 and r5e.status_code == 200)
log(5, "PASS" if pass5 else "FAIL",
    f"5a={r5a.status_code} 5c={r5c.status_code} 5d={r5d.status_code} 5e={r5e.status_code}")

# Restart without token
srv2.terminate()
srv2.wait()
kill_port()
srv3 = subprocess.Popen(
    ["py", "-3.12", "-m", "uvicorn", "main:app", "--port", "8000"],
    cwd=BACKEND_DIR,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, bufsize=1
)
for _ in range(40):
    line = srv3.stdout.readline()
    if "Application startup complete" in line:
        break
    time.sleep(0.5)
time.sleep(1)

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6 — Aged buckets FIFO
# ═══════════════════════════════════════════════════════════════════════════════
print("\n\n── TEST 6 ──")
post("/api/entries/", {"date": TODAY, "type": "purchase", "supplier": "AgeTest",
    "gl_code": "5100", "gl_name": "Purchases", "amount": 1000, "sst_rate": 0,
    "sst_amount": 0, "total": 1000})
post("/api/entries/", {"date": TODAY, "type": "payment", "supplier": "AgeTest",
    "amount": 600, "sst_rate": 0, "sst_amount": 0, "total": 600,
    "paid": 600, "balance_owed": 1000})
r6 = get("/api/reports/creditors")
creditors = r6.json() if r6.status_code == 200 else []
age_row = next((c for c in creditors if c.get("supplier") == "AgeTest"), None)
print(f"AgeTest creditor row: {age_row}")

if age_row:
    bal = age_row.get("balance")
    aged = age_row.get("aged", {})
    current = aged.get("current", aged.get("d0"))
    ok = (abs(float(bal) - 400) < 0.01 and abs(float(current or 0) - 400) < 0.01)
    log(6, "PASS" if ok else "FAIL",
        f"balance={bal}, aged.current={current}. Full aged: {aged}")
else:
    log(6, "FAIL", f"AgeTest not found in creditors. Response: {r6.status_code} {r6.text[:200]}")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7 — Decimal precision
# ═══════════════════════════════════════════════════════════════════════════════
print("\n\n── TEST 7 ──")
r7c = post("/api/entries/", {"date": TODAY, "type": "purchase", "supplier": "DecimalTest",
    "gl_code": "5100", "gl_name": "Purchases", "amount": 100.00, "sst_rate": 6,
    "sst_amount": 6.00, "total": 106.00})
eid = r7c.json().get("id")
r7g = get(f"/api/entries/{eid}")
entry = r7g.json()
amount = float(entry.get("amount", 0))
sst = float(entry.get("sst_amount", 0))
total = float(entry.get("total", 0))
print(f"amount={amount}, sst_amount={sst}, total={total}")

r7cr = get("/api/reports/creditors")
dec_row = next((c for c in r7cr.json() if c.get("supplier") == "DecimalTest"), None)
dec_bal = float(dec_row.get("balance", 0)) if dec_row else None
print(f"DecimalTest creditor balance: {dec_bal}")

ok7 = (amount == 100.0 and sst == 6.0 and total == 106.0 and dec_bal == 106.0)
log(7, "PASS" if ok7 else "FAIL",
    f"amount={amount} / sst={sst} / total={total} — creditor balance={dec_bal}")

# ── Cleanup ───────────────────────────────────────────────────────────────────
srv3.terminate()

# ── Summary table ─────────────────────────────────────────────────────────────
print(f"\n\n{'═'*70}")
print("Summary Table")
print(f"{'═'*70}")
print(f"{'#':<4} {'Result':<10} Evidence")
print(f"{'─'*70}")
exit_code = 0
for num, status, evidence in results:
    tag = "PASS" if "PASS" in status else ("FAIL" if "FAIL" in status else "UNEXPECTED")
    if tag != "PASS":
        exit_code = 1
    print(f"{num:<4} {tag:<10} {evidence[:90]}")
print(f"{'═'*70}")
sys.exit(exit_code)
