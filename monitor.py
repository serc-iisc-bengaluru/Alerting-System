#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path
from datetime import datetime, date

# ---------------- PATH SETUP ----------------

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

# ---------------- IMPORTS ----------------

from core.checker import ping_check, ssh_check, update_status_files
from core.emailer import send_email
from core.html_report import build_report_html
from core.utils import load_config

# ---------------- FILES ----------------

LOG_FILE   = SCRIPT_DIR / "logs" / "resource_monitor.log"
STATE_FILE = SCRIPT_DIR / "logs" / "state.json"

# ---------------- CONSTANTS ----------------

PING_RETRIES = 4
SSH_RETRIES  = 4

DAILY_SUMMARY_HOUR  = 0    # 12:00 AM
DAILY_REMINDER_HOUR = 10   # 10:00 AM

GROUPS = [
    ("RNC Cluster", "config/cluster_nodes.json"),
    ("DGX Servers", "config/dgx_nodes.json"),
    ("License Servers", "config/license_servers.json"),
    ("NIS Servers", "config/nis_servers.json"),
]

GROUP_EMAIL_MAP = {
    "RNC Cluster": [
        "dhyann@iisc.ac.in",
        "naveennayaka@iisc.ac.in",
        "shrinivasam@iisc.ac.in",
    ],
    "DGX Servers": [
        "dhyann@iisc.ac.in",
        "naveennayaka@iisc.ac.in",
        "shrinivasam@iisc.ac.in",
    ],
    "License Servers": [
        "dhyann@iisc.ac.in",
        "akhileshku@iisc.ac.in",
        "shivaprasadl@iisc.ac.in",
    ],
    "NIS Servers": [
        "dhyann@iisc.ac.in",
        "shivaprasadl@iisc.ac.in",
        "manjulap@iisc.ac.in",
    ],
}

# ---------------- LOGGING ----------------

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ---------------- STATE ----------------

def load_state():
    default = {
        "nodes": {},                 # per-node last status
        "last_daily_summary": "",
        "last_daily_reminder": "",
    }

    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            for k in default:
                data.setdefault(k, default[k])
            return data
        except Exception:
            pass

    return default

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ---------------- ALERT SENDER ----------------

def send_group_alerts(subject_prefix, results):
    for group, data in results.items():
        if not data["rows"]:
            continue

        recipients = GROUP_EMAIL_MAP.get(group)
        if not recipients:
            continue

        subject = f"{subject_prefix} [{group}]"
        html = build_report_html({group: data}, data["issues"])
        send_email(subject, html, recipients)

# ---------------- CORE CHECK ----------------

def run_checks_once():
    results = {}
    total_issues = 0

    for group_name, cfg_path in GROUPS:
        try:
            nodes = load_config(cfg_path)
            log(f"DEBUG: Loaded {len(nodes)} nodes for group '{group_name}'")
        except Exception as e:
            log(f"ERROR: Failed to load {cfg_path}: {e}")
            continue

        rows = []
        issues = 0

        for entry in nodes:
            name = entry.get("name")
            ip   = entry.get("ip")
            skip_ssh = entry.get("skip_ssh", False)

            ping_ok, _ = ping_check(ip, retries=PING_RETRIES)
            ssh_ok, _  = (True, "") if skip_ssh else ssh_check(ip, retries=SSH_RETRIES)

            is_issue = not ping_ok or (not skip_ssh and not ssh_ok)

            last_seen, uptime = update_status_files(name, ip, not is_issue)

            if is_issue:
                issues += 1

            rows.append({
                "name": name,
                "ip": ip or "-",
                "ping": "🟢 OK" if ping_ok else "🔴 FAIL",
                "ssh": "🟢 OK" if ssh_ok else "🔴 FAIL",
                "last_seen": last_seen,
                "uptime": uptime,
                "is_issue": is_issue,
                "role": entry.get("role", "default"),
            })

        results[group_name] = {"rows": rows, "issues": issues}
        total_issues += issues

    return results, total_issues

# ---------------- MAIN ----------------

def main():
    state = load_state()
    now = datetime.now()
    today = date.today().isoformat()

    log("monitor.py started")

    results, overall_issues = run_checks_once()

    current_nodes = {}

    # ---------- NODE-LEVEL CHANGE DETECTION ----------
    for group, data in results.items():
        for r in data["rows"]:
            key = f"{group}:{r['name']}"
            current_nodes[key] = r["is_issue"]

            prev = state["nodes"].get(key)

            # 🚨 FAILURE
            if prev is False and r["is_issue"] is True:
                send_group_alerts("🚨 NODE DOWN", {group: {"rows": [r], "issues": 1}})
                log(f"ALERT: Node DOWN -> {key}")

            # ✅ RECOVERY
            if prev is True and r["is_issue"] is False:
                send_group_alerts("✅ NODE RECOVERED", {group: {"rows": [r], "issues": 0}})
                log(f"RECOVERY: Node UP -> {key}")

    state["nodes"] = current_nodes

    # ---------- DAILY SUMMARY (12 AM) ----------
    if now.hour == DAILY_SUMMARY_HOUR and state["last_daily_summary"] != today:
        subject = "📊 DAILY INFRASTRUCTURE SUMMARY (ALL SYSTEMS)"
        html = build_report_html(results, overall_issues)
        send_email(subject, html)
        log("Daily summary sent")
        state["last_daily_summary"] = today

    # ---------- DAILY REMINDER (10 AM) ----------
    if overall_issues > 0 and now.hour == DAILY_REMINDER_HOUR and state["last_daily_reminder"] != today:
        issue_only = {
            g: {"rows": [r for r in d["rows"] if r["is_issue"]], "issues": d["issues"]}
            for g, d in results.items() if d["issues"] > 0
        }
        send_group_alerts("⚠️ DAILY REMINDER – ISSUES STILL PRESENT", issue_only)
        log("Daily reminder sent")
        state["last_daily_reminder"] = today

    save_state(state)

# ---------------- ENTRY ----------------

if __name__ == "__main__":
    (SCRIPT_DIR / "logs").mkdir(exist_ok=True)
    main()

