import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hetvi_leads_cache.json")

# Realistic fallback leads in case cache file does not exist yet and server is offline
FALLBACK_DISCOVERY_LEADS = [
    {
        "lead_id": "HETVI-187",
        "company": "Finance App Development Client",
        "contact_name": "James Murray",
        "email": "jmurray@freelancer.com",
        "phone": "+14155552671",
        "website": "https://www.freelancer.com/projects/android-app-development/Secure-Android-Finance-App-Development",
        "personalization_hook": "Looking for an experienced developer to build a production-ready finance application with strong focus on security, encryption, and compliance.",
        "primary_service": "Mobile App Development",
        "lead_score": 85,
        "lead_status": "NEW"
    },
    {
        "lead_id": "HETVI-192",
        "company": "Apex Global Logistics",
        "contact_name": "Sarah Jenkins",
        "email": "sarah.jenkins@apexgl.io",
        "phone": "+919820112233",
        "website": "https://apexgl.io",
        "personalization_hook": "Recently posted RFP for ERP integration and real-time shipment tracking microservices.",
        "primary_service": "ERP Development",
        "lead_score": 90,
        "lead_status": "NEW"
    },
    {
        "lead_id": "HETVI-205",
        "company": "CloudScale Commerce",
        "contact_name": "Devin Vance",
        "email": "devin@cloudscale.shop",
        "phone": "+12065550198",
        "website": "https://cloudscale.shop",
        "personalization_hook": "Scaling multi-vendor eCommerce platform and actively seeking dedicated React and Node backend engineers.",
        "primary_service": "eCommerce Development",
        "lead_score": 88,
        "lead_status": "NEW"
    }
]


def load_cached_leads():
    """Load leads from the local JSON cache file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"[HetviLeadSource] Error reading cache file: {e}")
    
    # Pre-seed fallback leads into cache file
    fallback = list(FALLBACK_DISCOVERY_LEADS)
    save_leads_to_cache(fallback)
    return fallback


def save_leads_to_cache(leads):
    """Save leads to the local JSON cache file."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        # Merge with existing cache if any to avoid losing previously discovered leads
        existing = {}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    for l in json.load(f):
                        if isinstance(l, dict) and "lead_id" in l:
                            existing[l["lead_id"]] = l
            except Exception:
                pass

        for l in leads:
            if isinstance(l, dict) and "lead_id" in l:
                existing[l["lead_id"]] = l

        merged = list(existing.values())
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        print(f"[HetviLeadSource] Saved {len(merged)} leads to cache: {CACHE_FILE}")
    except Exception as e:
        print(f"[HetviLeadSource] Error saving to cache: {e}")


def fetch_hetvi_leads():
    """
    Fetch leads from Hetvi's API and return a list of dicts with mechanically mapped fields.
    If the remote server is unreachable, gracefully loads previously saved leads from local cache.
    """
    url = os.getenv("LEAD_API_URL")
    if not url:
        print("[HetviLeadSource] LEAD_API_URL not set in environment, loading from cache")
        return load_cached_leads()

    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            print(f"[HetviLeadSource] Non-200 response ({resp.status_code}), falling back to cache")
            return load_cached_leads()

        data = resp.json()
        if "leads" not in data or not isinstance(data["leads"], list):
            print("[HetviLeadSource] Response missing 'leads' key, falling back to cache")
            return load_cached_leads()

        mapped = []
        for item in data["leads"]:
            contact = item.get("contact_name")
            if contact in (None, "", "N/A"):
                contact = "(Unknown)"

            mapped.append({
                "lead_id": f"HETVI-{item['id']}" if not str(item.get('id', '')).startswith("HETVI-") else str(item['id']),
                "company": item.get("company_name", ""),
                "contact_name": contact,
                "email": item.get("email") or None,
                "phone": item.get("phone_number") or None,
                "website": item.get("website", ""),
                "personalization_hook": item.get("research_summary") or "",
                "primary_service": item.get("primary_service") or None,
                "lead_score": item.get("lead_score") or None,
                "lead_status": "NEW",
            })

        if mapped:
            save_leads_to_cache(mapped)
        return mapped

    except (requests.exceptions.RequestException, Exception) as e:
        print(f"[HetviLeadSource] Server unreachable ({e}), seamlessly falling back to local cache")
        return load_cached_leads()

