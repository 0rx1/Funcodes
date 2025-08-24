import os
import json
import time
from datetime import datetime, timedelta, timezone
from gcore import Gcore
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

WATCHLIST_FILE = "watchlist.json"
DURATION_FILE = "attack_duration.json"  # store start times
CHECK_INTERVAL_MINUTES = 10

load_dotenv()
api_key = os.getenv("GCORE_API_KEY")
if not api_key:
    raise RuntimeError("Missing GCORE_API_KEY in environment or .env file")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM")   
SMTP_TO   = os.getenv("SMTP_TO")

client = Gcore(api_key=api_key)

watchlist = []

if os.path.exists(WATCHLIST_FILE):
    with open(WATCHLIST_FILE, "r") as f:
        saved_ids = json.load(f)
    try:
        domains = client.waap.domains.list().results
        watchlist = [d for d in domains if d.id in saved_ids]
    except Exception as e:
        print(f"Error fetching WAAP domains: {e}")
        exit(1)

if not watchlist:
    try:
        domains = client.waap.domains.list().results
    except Exception as e:
        print(f"Error fetching WAAP domains: {e}")
        exit(1)

    print("WAAP domains available:")
    for i, d in enumerate(domains):
        print(f"{i+1}) id={d.id} | name={getattr(d,'name','<no-name>')}")

    selection = input("Enter the numbers of domains to monitor, comma-separated (e.g. 1,3): ")
    indices = [int(x.strip())-1 for x in selection.split(",") if x.strip().isdigit()]
    watchlist = [domains[i] for i in indices if 0 <= i < len(domains)]

    if not watchlist:
        print("No valid domains selected. Exiting.")
        exit(1)

    with open(WATCHLIST_FILE, "w") as f:
        json.dump([d.id for d in watchlist], f)
    print(f"Watchlist saved to {WATCHLIST_FILE}")

print("\nMonitoring the following domains:")
for d in watchlist:
    print(f"- {getattr(d,'name','<no-name>')} (id={d.id})")


if os.path.exists(DURATION_FILE):
    with open(DURATION_FILE, "r") as f:
        attack_start_times = json.load(f)
        # convert ISO strings to datetime
        attack_start_times = {k: datetime.fromisoformat(v) for k,v in attack_start_times.items()}
else:
    attack_start_times = {}


def save_attack_start_times():
    with open(DURATION_FILE, "w") as f:
        # convert datetime to ISO string
        json.dump({k:v.isoformat() for k,v in attack_start_times.items()}, f)


def send_alert_email(domain_name, blocked, passed, duration_minutes):
    subject = f"🚨 DDoS Alert for {domain_name}"
    body = f"""
    <html>
    <body>
        <h2>⚠️ DDoS Alert for {domain_name}</h2>
        <p><b>Blocked Requests:</b> {blocked:,}</p>
        <p><b>Passed Requests:</b> {passed:,}</p>
        <p><b>Duration:</b> {duration_minutes} minutes</p>
        <p>Thresholds: Blocked > 50,000 or Passed > 100,000</p>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM   # 👈 explicit sender email
    msg["To"] = SMTP_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, SMTP_TO, msg.as_string())  # 👈 use SMTP_FROM here
        print(f"[INFO] Alert email sent for {domain_name}")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")

def send_metrics_alert(domain):
    domain_id = domain.id
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=CHECK_INTERVAL_MINUTES)
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()

    try:
        metrics = client.waap.domains.statistics.get_traffic_series(
            domain_id=domain_id,
            start=start_str,
            end=end_str,
            resolution="minutely"
        )

        blocked_total = sum((getattr(m,"policyBlocked",0) or 0) +
                            (getattr(m,"customBlocked",0) or 0) +
                            (getattr(m,"ddosBlocked",0) or 0) for m in metrics)
        passed_total = sum((getattr(m,"passedToOrigin",0) or 0) for m in metrics)

        print(f"[{getattr(domain,'name','<no-name>')}] Blocked={blocked_total}, Passed={passed_total}")

        # Check thresholds
        alert = blocked_total > 50000 or passed_total > 100000

        if alert:
            # track duration
            if domain.id not in attack_start_times:
                attack_start_times[domain.id] = datetime.now(timezone.utc)
            duration_minutes = int((datetime.now(timezone.utc) - attack_start_times[domain.id]).total_seconds() / 60)

            send_alert_email(
                domain_name=getattr(domain,'name','<no-name>'),
                blocked=blocked_total,
                passed=passed_total,
                duration_minutes=duration_minutes
            )
        else:
            # reset duration if under threshold
            if domain.id in attack_start_times:
                del attack_start_times[domain.id]

        save_attack_start_times()

    except Exception as e:
        print(f"Error fetching stats for domain {getattr(domain,'name','<no-name>')}: {e}")

def send_test_email():
    if not watchlist:
        print("Watchlist is empty. Cannot send test email.")
        return

    domain = watchlist[0]
    domain_id = domain.id
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=CHECK_INTERVAL_MINUTES)
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()

    try:
        metrics = client.waap.domains.statistics.get_traffic_series(
            domain_id=domain_id,
            start=start_str,
            end=end_str,
            resolution="minutely"
        )

        blocked_total = sum((getattr(m,"policyBlocked",0) or 0) +
                            (getattr(m,"customBlocked",0) or 0) +
                            (getattr(m,"ddosBlocked",0) or 0) for m in metrics)
        passed_total = sum((getattr(m,"passedToOrigin",0) or 0) for m in metrics)

        duration_minutes = CHECK_INTERVAL_MINUTES  # for test, just use interval

        send_alert_email(
            domain_name=getattr(domain,'name','<no-name>'),
            blocked=blocked_total,
            passed=passed_total,
            duration_minutes=duration_minutes
        )
        print(f"✅ Test email sent successfully for domain {getattr(domain,'name','<no-name>')}")

    except Exception as e:
        print(f"❌ Failed to send test email: {e}")

# Uncomment to send test email
#send_test_email()
while True:
    print(f"\nChecking WAAP stats at {datetime.now(timezone.utc).isoformat()}")
    for domain in watchlist:
        send_metrics_alert(domain)
    print(f"Waiting {CHECK_INTERVAL_MINUTES} minutes before next check...")
    time.sleep(CHECK_INTERVAL_MINUTES * 60)
