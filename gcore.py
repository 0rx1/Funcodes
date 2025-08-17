import os
import time
import json
import random
from datetime import datetime
from gcore import Gcore

# === CONFIG ===
API_KEY = os.getenv("GCORE_API_KEY")  # Recommended: export GCORE_API_KEY=yourkey
WATCHLIST_FILE = "watchlist.json"
BLOCKED_THRESHOLD = 50_000
PASSED_THRESHOLD = 100_000

client = Gcore(api_key=API_KEY)


def list_services():
    """List all available services from Gcore (WAAP)."""
    try:
        services = client.waap.services.list()
        print("\n=== Available Services ===")
        for svc in services:
            print(f"ID: {svc['id']} | Name: {svc['name']} | Domain: {svc.get('domain', 'N/A')}")
        return services
    except Exception as e:
        print(f"❌ Error fetching services: {e}")
        return []


def choose_services(services):
    """Prompt user to choose which services to monitor."""
    selected = []
    print("\nEnter the service IDs you want to monitor (comma separated):")
    ids = input("> ").strip().split(",")

    for i in ids:
        i = i.strip()
        for svc in services:
            if str(svc["id"]) == i:
                selected.append({"id": svc["id"], "name": svc["name"], "domain": svc.get("domain", "N/A")})

    if not selected:
        print("⚠️ No valid services selected, watchlist will be empty.")
    else:
        print("\n✅ Selected services:")
        for s in selected:
            print(f"- {s['name']} ({s['domain']})")

    # Save to file
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(selected, f, indent=2)
    return selected


def load_watchlist():
    """Load previously chosen watchlist from file."""
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return []


def fetch_stats_for_service(service_id):
    """Fetch request stats for a specific service ID."""
    try:
        resp = client.waap.analytics.get_requests(service_id=service_id)
        # Example: count blocked/passed
        blocked = sum(1 for r in resp.requests if r.result == "blocked")
        passed = sum(1 for r in resp.requests if r.result == "passed")
        return blocked, passed
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error fetching stats for {service_id}: {e}")
        return 0, 0


def check_ddos(service, blocked, passed):
    """Apply thresholds to detect DDoS activity."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if blocked > BLOCKED_THRESHOLD:
        print(f"[{ts}] 🚨 {service['name']} ({service['domain']}): Mitigated DDoS detected (blocked={blocked})")
    elif passed > PASSED_THRESHOLD:
        print(f"[{ts}] ⚠️ {service['name']} ({service['domain']}): Ongoing DDoS (passed={passed})")
    else:
        print(f"[{ts}] ✅ {service['name']} ({service['domain']}): Normal (blocked={blocked}, passed={passed})")


def main():
    # Step 1: Load existing watchlist or let user pick
    watchlist = load_watchlist()
    if not watchlist:
        print("No watchlist found. Fetching services...")
        services = list_services()
        if services:
            watchlist = choose_services(services)

    # Step 2: Start monitoring loop
    if not watchlist:
        print("❌ No services to monitor. Exiting.")
        return

    print("\n=== Starting Monitoring Loop ===")
    while True:
        for svc in watchlist:
            blocked, passed = fetch_stats_for_service(svc["id"])
            check_ddos(svc, blocked, passed)

        # Sleep 10–15 min
        delay = 600 + random.randint(0, 300)
        print(f"\nNext check in {delay//60} minutes...\n")
        time.sleep(delay)


if __name__ == "__main__":
    main()
