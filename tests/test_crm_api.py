import os
import sys
import threading
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import urllib.request
import urllib.error
import json

def ensure_server():
    base_url = "http://127.0.0.1:5050"
    try:
        req = urllib.request.Request(f"{base_url}/api/dashboard")
        with urllib.request.urlopen(req, timeout=1) as resp:
            return None, base_url
    except Exception:
        from http.server import HTTPServer
        from web_dashboard import DashboardHandler
        for port in (5050, 5055, 5056):
            try:
                server = HTTPServer(("127.0.0.1", port), DashboardHandler)
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                time.sleep(1)
                return server, f"http://127.0.0.1:{port}"
            except Exception:
                continue
    return None, base_url

def test_api():
    srv, base_url = ensure_server()


    
    # 1. Test validation error
    print("Testing invalid opportunity_value:")
    req = urllib.request.Request(
        f"{base_url}/api/update-lead",
        data=json.dumps({"lead_id": "L001", "opportunity_value": "not_a_number"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        urllib.request.urlopen(req)
        assert False, "Should have failed with 400!"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        print("-> Correctly returned 400 for non-numeric opportunity_value.")

    # 2. Test valid update
    print("Testing valid CRM update:")
    update_payload = {
        "lead_id": "L001",
        "city": "Bengaluru",
        "industry": "Retail eCommerce",
        "opportunity_value": 45000.0,
        "salesperson": "Priya Sharma",
        "notes": "Discussed expansion into tier-2 cities. Proposal expected."
    }
    req2 = urllib.request.Request(
        f"{base_url}/api/update-lead",
        data=json.dumps(update_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req2) as resp:
        assert resp.status == 200
        res_data = json.loads(resp.read().decode("utf-8"))
        print(f"-> Update response: {res_data['message']}")

    # 3. Test lead-details retrieval
    print("Testing /api/lead-details retrieval:")
    with urllib.request.urlopen(f"{base_url}/api/lead-details?lead_id=L001") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        lead = data["lead"]
        print(f"-> Lead details retrieved:")
        print(f"   City: {lead.get('city')}")
        print(f"   Industry: {lead.get('industry')}")
        print(f"   Opportunity Value: {lead.get('opportunity_value')}")
        print(f"   Salesperson: {lead.get('salesperson')}")
        print(f"   Notes: {lead.get('notes')}")
        assert lead.get("city") == "Bengaluru"
        assert lead.get("opportunity_value") == 45000.0
        assert lead.get("salesperson") == "Priya Sharma"

    # 4. Test dashboard retrieval
    print("Testing /api/dashboard retrieval:")
    with urllib.request.urlopen(f"{base_url}/api/dashboard") as resp:
        dash_data = json.loads(resp.read().decode("utf-8"))
        l001 = next(l for l in dash_data["leads"] if l["lead_id"] == "L001")
        assert l001["salesperson"] == "Priya Sharma"
        print(f"-> Dashboard lead L001 salesperson: {l001['salesperson']}")

    print("\nALL HTTP API TESTS PASSED SUCCESSFULLY!")
    if srv:
        srv.shutdown()

if __name__ == "__main__":
    test_api()

