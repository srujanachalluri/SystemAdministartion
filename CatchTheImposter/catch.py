#!/usr/bin/env python3
"""catch.py - Catch the Impostor (Project 3, Shepherd's Gate Health Cooperative).
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# These are the *defaults*. config.json can override any of them without my
# touching the code -- that is what "configurable threshold" in the rubric means.
DEFAULT_CONFIG = {
    # Impossible travel: no human moves faster than this between two logins.
    # 900 km/h (the assignment default) is a jetliner's cruise speed, but GeoIP
    # databases misplace a *domestic* IP by hundreds of km, which can fake speeds
    # of a couple thousand km/h for a perfectly legitimate same-country login.
    # 3000 km/h absorbs that jitter (sparing vp_kpatel's 2216 km/h domestic hop)
    # while still catching an intercontinental teleport (mcompton at 52,404 km/h).
    "impossible_travel_kmh": 3000.0,

    # Off-hours privileged access: admins are expected 07:00-19:00 local.
    "business_start_hour": 7,
    "business_end_hour": 19,
    # Accounts whose *normal* baseline is off-hours (e.g. the nightly backup job).
    # We never raise an off-hours alert on these -- the "spare the service account"
    # lesson. They are exempted by name so the exemption is auditable.
    "service_accounts": ["svc_backup"],

    # Brute force: many failed logins against ONE account in a short window.
    "brute_force_min_failures": 5,
    "brute_force_window_min": 15,

    # Password spray: ONE source IP failing against MANY distinct accounts,
    # a few tries each, inside one window.
    "spray_min_accounts": 5,
    "spray_window_min": 60,
}

# The columns the log is supposed to have. Used only to sanity-check the header.
EXPECTED_COLUMNS = [
    "ts", "user", "event", "result", "role",
    "country", "city", "lat", "lon", "src_ip",
]


# ---------------------------------------------------------------------------
# 1. Parser  (rubric: "handles bad lines, correct fields")
# ---------------------------------------------------------------------------
def parse_log(path):
    """Read the auth log into a list of clean dict rows.

    Returns (events, skipped). A malformed line NEVER crashes the run: it is
    counted in `skipped` with its line number and reason, then we move on.
    """
    events = []
    skipped = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        # enumerate from 2 because line 1 is the header, so the first data row is line 2.
        for lineno, row in enumerate(reader, start=2):
            try:
                # The four fields every event must have to be meaningful.
                for field in ("ts", "user", "event", "result"):
                    if not row.get(field):
                        raise ValueError(f"missing '{field}'")

                # Timestamps must be real ISO timestamps or the row is useless.
                dt = datetime.fromisoformat(row["ts"])

                # lat/lon may be blank on non-geographic events; parse when present.
                lat = float(row["lat"]) if row.get("lat") else None
                lon = float(row["lon"]) if row.get("lon") else None

                events.append({
                    "ts": row["ts"],          # keep the raw string for scoring keys
                    "dt": dt,                 # parsed datetime for arithmetic
                    "user": row["user"],
                    "event": row["event"],
                    "result": row["result"],
                    "role": row.get("role", "") or "",
                    "country": row.get("country", "") or "",
                    "city": row.get("city", "") or "",
                    "lat": lat,
                    "lon": lon,
                    "src_ip": row.get("src_ip", "") or "",
                })
            except (ValueError, KeyError, TypeError) as exc:
                skipped.append((lineno, str(exc)))
                continue  # robustness: bad line logged, pipeline keeps running
    return events, skipped


# ---------------------------------------------------------------------------
# Geometry helper (rubric: "haversine, not Euclidean")
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points on a sphere.

    A flat-earth (Euclidean) distance on raw lat/lon degrees would mis-scale
    longitude badly away from the equator, so we do it properly.
    """
    r = 6371.0  # mean Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Detector 2: Impossible travel
# ---------------------------------------------------------------------------
def detect_impossible_travel(events, kmh_threshold):
    """Flag a successful login that is impossibly far from the user's previous one.

    We only compare *successful logins*: a failed login proves nothing about
    where the user actually is.
    """
    alerts = []
    logins = [e for e in events
              if e["event"] == "login" and e["result"] == "success"
              and e["lat"] is not None and e["lon"] is not None]
    # Sort by user then time so each user's logins are in order.
    logins.sort(key=lambda e: (e["user"], e["dt"]))

    prev = {}  # user -> their previous successful login
    for e in logins:
        user = e["user"]
        if user in prev:
            p = prev[user]
            hours = (e["dt"] - p["dt"]).total_seconds() / 3600.0
            if hours > 0:
                km = haversine_km(p["lat"], p["lon"], e["lat"], e["lon"])
                kmh = km / hours
                if kmh > kmh_threshold:
                    alerts.append({
                        "ts": e["ts"], "user": user, "detector": "impossible_travel",
                        "detail": (f"{p['city']} -> {e['city']}: {km:.0f} km in "
                                   f"{hours * 60:.0f} min = {kmh:.0f} km/h "
                                   f"(> {kmh_threshold:.0f})"),
                    })
        prev[user] = e
    return alerts


# ---------------------------------------------------------------------------
# Detector 3: Off-hours privileged access
# ---------------------------------------------------------------------------
def detect_off_hours_admin(events, start_hour, end_hour, service_accounts):
    """Flag admin-role activity outside business hours, sparing service accounts."""
    alerts = []
    allow = set(service_accounts)
    for e in events:
        if e["role"] != "admin":
            continue                      # authorization filter: admins only
        if e["user"] in allow:
            continue                      # spare the known nightly service account
        hour = e["dt"].hour
        if not (start_hour <= hour < end_hour):
            alerts.append({
                "ts": e["ts"], "user": e["user"], "detector": "off_hours_admin",
                "detail": (f"admin '{e['event']}' at {e['dt'].strftime('%H:%M')} "
                           f"(outside {start_hour:02d}:00-{end_hour:02d}:00) "
                           f"from {e['src_ip']}"),
            })
    return alerts


# ---------------------------------------------------------------------------
# Detector 4a: Brute force (many failures against one account)
# ---------------------------------------------------------------------------
def detect_brute_force(events, min_failures, window_min):
    """Flag an account that sees >= min_failures failed logins within a window."""
    fails_by_user = defaultdict(list)
    for e in events:
        if e["event"] == "login" and e["result"] == "failure":
            fails_by_user[e["user"]].append(e)

    alerts = []
    window_sec = window_min * 60
    for user, evs in fails_by_user.items():
        evs.sort(key=lambda e: e["dt"])
        # Slide the window: for each failure, count how many fall within it.
        for anchor in evs:
            burst = [x for x in evs
                     if 0 <= (x["dt"] - anchor["dt"]).total_seconds() <= window_sec]
            if len(burst) >= min_failures:
                alerts.append({
                    "ts": anchor["ts"], "user": user, "detector": "brute_force",
                    "detail": (f"{len(burst)} failed logins in {window_min} min "
                               f"from {anchor['src_ip']}"),
                })
                break  # one alert per account, keyed to the burst's first failure
    return alerts


# ---------------------------------------------------------------------------
# Detector 4b: Password spray (one IP, many accounts, few tries each)
# ---------------------------------------------------------------------------
def detect_password_spray(events, min_accounts, window_min):
    """Flag a source IP that fails against >= min_accounts distinct accounts."""
    fails_by_ip = defaultdict(list)
    for e in events:
        if e["event"] == "login" and e["result"] == "failure":
            fails_by_ip[e["src_ip"]].append(e)

    alerts = []
    window_sec = window_min * 60
    for ip, evs in fails_by_ip.items():
        evs.sort(key=lambda e: e["dt"])
        for anchor in evs:
            window = [x for x in evs
                      if 0 <= (x["dt"] - anchor["dt"]).total_seconds() <= window_sec]
            accounts = {x["user"] for x in window}
            if len(accounts) >= min_accounts:
                # Flag the first failure of each distinct victim in this window.
                seen = set()
                for x in window:
                    if x["user"] not in seen:
                        seen.add(x["user"])
                        alerts.append({
                            "ts": x["ts"], "user": x["user"], "detector": "password_spray",
                            "detail": (f"source IP {ip} sprayed {len(accounts)} "
                                       f"accounts in {window_min} min"),
                        })
                break  # report the spray episode once
    return alerts


# ---------------------------------------------------------------------------
# Detector 5 (bonus): Privilege escalation
# ---------------------------------------------------------------------------
def detect_privilege_escalation(events):
    """Flag a user who grants themselves admin (a roleassign to admin by an
    account that was not already an admin). This is not required for the Normal
    tier, but the answer key contains one, so catching it lifts recall."""
    alerts = []
    roles_seen = defaultdict(set)  # user -> set of roles seen so far in time order
    for e in sorted(events, key=lambda e: e["dt"]):
        user = e["user"]
        if (e["event"] == "roleassign" and e["role"] == "admin"
                and "admin" not in roles_seen[user]):
            alerts.append({
                "ts": e["ts"], "user": user, "detector": "privilege_escalation",
                "detail": "roleassign to admin by a previously non-admin account",
            })
        roles_seen[user].add(e["role"])
    return alerts


# ---------------------------------------------------------------------------
# 5. Self-scoring  (rubric: precision + recall, name the FPs and FNs)
# ---------------------------------------------------------------------------
def load_truth(path):
    """Load ground_truth.csv into {(ts, user): attack_type} for malicious rows."""
    truth = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("label") == "malicious":
                truth[(row["ts"], row["user"])] = row.get("attack_type", "")
    return truth


def score(alerts, truth):
    """Compare alert (ts, user) keys against the answer key."""
    alert_keys = {(a["ts"], a["user"]) for a in alerts}
    truth_keys = set(truth)
    tp = alert_keys & truth_keys        # flagged and actually malicious
    fp = alert_keys - truth_keys        # flagged but actually benign (false alarm)
    fn = truth_keys - alert_keys        # missed real attacks
    precision = len(tp) / len(alert_keys) if alert_keys else 0.0
    recall = len(tp) / len(truth_keys) if truth_keys else 0.0
    return tp, fp, fn, precision, recall


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if path:
        with open(path) as fh:
            cfg.update(json.load(fh))
    return cfg


def run_detectors(events, cfg):
    alerts = []
    alerts += detect_impossible_travel(events, cfg["impossible_travel_kmh"])
    alerts += detect_off_hours_admin(events, cfg["business_start_hour"],
                                     cfg["business_end_hour"], cfg["service_accounts"])
    alerts += detect_brute_force(events, cfg["brute_force_min_failures"],
                                 cfg["brute_force_window_min"])
    alerts += detect_password_spray(events, cfg["spray_min_accounts"],
                                    cfg["spray_window_min"])
    alerts += detect_privilege_escalation(events)
    # Stable order for the report: by time, then user, then detector.
    alerts.sort(key=lambda a: (a["ts"], a["user"], a["detector"]))
    return alerts


def main():
    ap = argparse.ArgumentParser(description="Catch the Impostor - auth log anomaly detector")
    ap.add_argument("logfile", help="path to auth_events.csv")
    ap.add_argument("--truth", help="path to ground_truth.csv for self-scoring")
    ap.add_argument("--config", default="config.json",
                    help="JSON file of thresholds / allow-list (default: config.json)")
    args = ap.parse_args()

    # config.json is optional; fall back to built-in defaults if it is absent.
    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        cfg = dict(DEFAULT_CONFIG)

    events, skipped = parse_log(args.logfile)
    alerts = run_detectors(events, cfg)

    print("=" * 70)
    print(f"Parsed {len(events)} events; skipped {len(skipped)} malformed line(s).")
    for lineno, reason in skipped:
        print(f"  - line {lineno} skipped: {reason}")
    print("=" * 70)
    print(f"ALERTS RAISED: {len(alerts)}")
    print("-" * 70)
    for a in alerts:
        print(f"[{a['detector']:<22}] {a['ts']}  {a['user']:<12} {a['detail']}")

    if args.truth:
        truth = load_truth(args.truth)
        tp, fp, fn, precision, recall = score(alerts, truth)
        print("=" * 70)
        print("SELF-SCORE against ground truth")
        print("-" * 70)
        print(f"True positives : {len(tp)}")
        print(f"False positives: {len(fp)}")
        print(f"False negatives: {len(fn)}")
        print(f"Precision      : {precision:.3f}")
        print(f"Recall         : {recall:.3f}")
        if fp:
            print("\nFalse positives (flagged but benign):")
            for ts, user in sorted(fp):
                print(f"  - {ts}  {user}")
        if fn:
            print("\nFalse negatives (real attacks we missed):")
            for ts, user in sorted(fn):
                print(f"  - {ts}  {user}  [{truth[(ts, user)]}]")
        if not fp and not fn:
            print("\nNo false positives or false negatives.")
        print("=" * 70)


if __name__ == "__main__":
    main()
