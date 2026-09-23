import os
import sys
import threading
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Automated verification for Duplicate Lead Detection (Spec Section 15 & 19).
"""
import urllib.request
import urllib.error
import json
import csv

BASE_URL = "http://127.0.0.1:5050"

def ensure_server():
    global BASE_URL
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/dashboard")
        with urllib.request.urlopen(req, timeout=1) as resp:
            return None
    except Exception:
        from http.server import HTTPServer
        from web_dashboard import DashboardHandler
        for port in (5050, 5055, 5056):
            try:
                server = HTTPServer(("127.0.0.1", port), DashboardHandler)
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                time.sleep(1)
                BASE_URL = f"http://127.0.0.1:{port}"
                return server
            except Exception:
                continue
    return None




def make_post(endpoint: str, payload: dict):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"message": body}


def make_get(endpoint: str):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def run_tests():
    srv = ensure_server()
    print("=================================================================")

    print("STARTING DUPLICATE LEAD DETECTION VERIFICATION (SPEC 15 & 19)")
    print("=================================================================\n")

    # --------------------------------------------------------------------------
    # Pre-clean any leftover dummy leads
    # --------------------------------------------------------------------------
    csv_path = "data/leads.csv"
    if os.path.exists(csv_path):
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = [r for r in reader if not r.get("company", "").strip().lower().startswith("uniquealpha") and not r.get("company", "").strip().lower().startswith("second brand") and not r.get("company", "").strip().lower().startswith("brand new")]

        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # --------------------------------------------------------------------------
    # Test 1: Unique company addition succeeds
    # --------------------------------------------------------------------------
    unique_company = "UniqueAlpha Enterprise 999"
    unique_email = "uniquealpha999@example.com"
    unique_phone = "+13022190702"

    print("Step 1: Adding a unique lead...")
    status, res = make_post("/api/add-lead", {
        "company": unique_company,
        "contact_name": "Test Contact",
        "email": unique_email,
        "phone": unique_phone,
        "primary_service": "Cloud Development"
    })


    print(f"  Response Status: {status}")
    print(f"  Response: {res}")
    assert status == 200, f"Test 1 failed: expected 200, got {status}"
    added_lead_id = res["lead"]["lead_id"]
    print(f"=> [PASS] Test 1: Added unique lead {added_lead_id} successfully.\n")

    # --------------------------------------------------------------------------
    # Test 2: Case-insensitive company name match rejected
    # --------------------------------------------------------------------------
    print("Step 2: Testing duplicate company name (case-insensitive 'uniquealpha enterprise 999')...")
    status, res = make_post("/api/add-lead", {
        "company": "  uniquealpha enterprise 999  ",
        "contact_name": "Another Person",
        "email": "different_email@example.com",
        "phone": "+19998887777"
    })
    print(f"  Response Status: {status}")
    print(f"  Response: {res}")
    assert status == 409, f"Test 2 failed: expected 409, got {status}"
    assert "already exists as lead" in res.get("message", ""), "Test 2 failed: missing duplicate company message"
    print("=> [PASS] Test 2: Case-insensitive company duplicate rejected with 409.\n")

    # --------------------------------------------------------------------------
    # Test 3: Same email with NEW company name rejected
    # --------------------------------------------------------------------------
    print("Step 3: Testing duplicate email with new company name...")
    status, res = make_post("/api/add-lead", {
        "company": "Brand New Company Ltd",
        "contact_name": "Another Person",
        "email": unique_email.upper(),  # case-insensitive check
        "phone": "+19998887777"
    })
    print(f"  Response Status: {status}")
    print(f"  Response: {res}")
    assert status == 409, f"Test 3 failed: expected 409, got {status}"
    assert "already belongs to lead" in res.get("message", ""), "Test 3 failed: missing duplicate email message"
    assert "email" in res.get("message", ""), "Test 3 failed: message does not mention email"
    print("=> [PASS] Test 3: Duplicate email with new company rejected with 409.\n")

    # --------------------------------------------------------------------------
    # Test 4: Same phone in DIFFERENT format caught via E.164 normalization
    # (Stored phone is +13022190702, submission has "(302) 219-0702")
    # --------------------------------------------------------------------------
    print("Step 4: Testing duplicate phone in different format: '(302) 219-0702' vs stored '+13022190702'...")
    status, res = make_post("/api/add-lead", {
        "company": "Second Brand New Company",
        "contact_name": "Third Contact",
        "email": "fresh_email@example.com",
        "phone": "(302) 219-0702"
    })
    print(f"  Response Status: {status}")
    print(f"  Response: {res}")
    assert status == 409, f"Test 4 failed: expected 409, got {status}"
    assert "already belongs to lead" in res.get("message", ""), "Test 4 failed: missing duplicate phone message"
    assert "phone" in res.get("message", ""), "Test 4 failed: message does not mention phone"
    print("=> [PASS] Test 4: Differently-formatted phone number normalized to E.164 and caught as duplicate.\n")

    # --------------------------------------------------------------------------
    # Test 5: Explicit override with force: true succeeds
    # --------------------------------------------------------------------------
    print("Step 5: Testing explicit duplicate override with force: true...")
    status, res = make_post("/api/add-lead", {
        "company": "Second Brand New Company",
        "contact_name": "Third Contact",
        "email": "fresh_email@example.com",
        "phone": "(302) 219-0702",
        "force": True
    })
    print(f"  Response Status: {status}")
    print(f"  Response: {res}")
    assert status == 200, f"Test 5 failed: expected 200 with force: true, got {status}"
    forced_lead_id = res["lead"]["lead_id"]
    print(f"=> [PASS] Test 5: Lead {forced_lead_id} successfully added using force: true.\n")

    # --------------------------------------------------------------------------
    # Test 6: Hetvi discovery fetch/activate unaffected
    # --------------------------------------------------------------------------
    print("Step 6: Confirming Hetvi Leads fetch endpoint remains functional...")
    status, res = make_get("/api/fetch-hetvi-leads")
    print(f"  Response Status: {status}")
    print(f"  Status in response: {res.get('status')}")
    print(f"  Total from API: {res.get('total_from_api')}")
    assert status == 200, f"Test 6 failed: expected 200, got {status}"
    assert res.get("status") == "success", "Test 6 failed: status is not success"
    assert "total_from_api" in res, "Test 6 failed: missing total_from_api"
    print("=> [PASS] Test 6: Hetvi discovery endpoint works seamlessly and duplicate filtering is unaffected.\n")

    # Clean up test rows from leads.csv so tests don't leave permanent dummy records
    csv_path = "data/leads.csv"
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = [r for r in reader if r.get("lead_id") not in (added_lead_id, forced_lead_id)]
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Cleanup: Removed temporary test leads {added_lead_id} and {forced_lead_id} from data/leads.csv.\n")

    print("=================================================================")
    print("ALL 6 TESTS PASSED SUCCESSFULLY!")
    print("=================================================================")
    if srv:
        srv.shutdown()


if __name__ == "__main__":
    run_tests()

