from datetime import datetime
import html

# ===================== CONFIG =====================

GROUP_SKINS = {
    "RNC Cluster": {"bg": "#e3f2fd", "border": "#1565c0"},
    "DGX Servers": {"bg": "#ede7f6", "border": "#5e35b1"},
    "License Servers": {"bg": "#e8f5e9", "border": "#2e7d32"},
    "NIS Servers": {"bg": "#fff3e0", "border": "#ef6c00"},
    "DEFAULT": {"bg": "#f5f7fa", "border": "#90a4ae"},
}

ROLE_BADGE = {
    "login": ("LOGIN", "#0288d1"),
    "compute": ("COMPUTE", "#6a1b9a"),
    "gpu": ("GPU", "#f9a825"),
    "storage": ("STORAGE", "#2e7d32"),
    "default": ("NODE", "#546e7a"),
}

SEVERITY_STYLE = {
    "OK": ("🟢 OK", "#1e8e3e"),
    "CRITICAL": ("🔴 CRITICAL", "#d93025"),
}

# ===================== HELPERS =====================

def severity(row):
    return "CRITICAL" if row["is_issue"] else "OK"

def node_status(row):
    return "🔴 DOWN" if row["is_issue"] else "🟢 UP"

# ===================== MAIN =====================

def build_report_html(results: dict, overall_issues: int):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    healthy = overall_issues == 0
    total_nodes = sum(len(d["rows"]) for d in results.values())

    html_report = f"""
    <style>
    @media only screen and (max-width: 600px) {{
        table, thead, tbody, th, td, tr {{
            display: block !important;
            width: 100% !important;
        }}
        thead {{ display: none !important; }}
        tr {{
            margin-bottom: 15px;
            border-bottom: 2px solid #ddd;
        }}
        td {{
            padding-left: 45% !important;
            position: relative;
        }}
        td::before {{
            position: absolute;
            left: 10px;
            width: 40%;
            font-weight: 600;
            color: #555;
        }}
        td:nth-of-type(1)::before {{ content: "Node"; }}
        td:nth-of-type(2)::before {{ content: "Role"; }}
        td:nth-of-type(3)::before {{ content: "IP"; }}
        td:nth-of-type(4)::before {{ content: "Status"; }}
        td:nth-of-type(5)::before {{ content: "Ping"; }}
        td:nth-of-type(6)::before {{ content: "SSH"; }}
        td:nth-of-type(7)::before {{ content: "Last Seen"; }}
        td:nth-of-type(8)::before {{ content: "Node State"; }}
    }}
    </style>

    <div style="font-family:Segoe UI,Arial,sans-serif;
                max-width:1150px;margin:auto;color:#222;">

    <div style="padding:22px;border-radius:14px;
                background:{'#e6f4ea' if healthy else '#fdecea'};
                border:2px solid {'#1e8e3e' if healthy else '#d93025'};">
        <h1>Infrastructure Monitoring Report</h1>
        <p>Generated: <b>{ts}</b></p>
        <span style="padding:6px 18px;border-radius:20px;
                     background:{'#34a853' if healthy else '#d93025'};
                     color:white;font-weight:600;">
            {"ALL SYSTEMS HEALTHY" if healthy else f"{overall_issues} ACTIVE ISSUE(S)"}
        </span>
    </div>

    <div style="margin-top:18px;padding:16px;background:#f7f9fc;
                border-radius:12px;border:1px solid #d0d7de;">
        <b>Total Nodes:</b> {total_nodes} &nbsp;
        <b>Issues:</b> {overall_issues}
    </div>
    """

    for group, data in results.items():
        skin = GROUP_SKINS.get(group, GROUP_SKINS["DEFAULT"])

        html_report += f"""
        <div style="margin-top:22px;">
        <div style="padding:14px;border-radius:12px;
                    background:{skin['bg']};
                    border-left:6px solid {skin['border']};
                    font-size:18px;font-weight:700;">
            {group} — {data["issues"]} issue(s)
        </div>

        <table style="width:100%;border-collapse:separate;
                      border-spacing:0 10px;font-size:14px;">
        <thead>
        <tr style="background:#eceff1;">
            <th>Node</th>
            <th>Role</th>
            <th>IP</th>
            <th>Status</th>
            <th>Ping</th>
            <th>SSH</th>
            <th>Last Seen</th>
            <th>Node State</th>
        </tr>
        </thead>
        <tbody>
        """

        for r in data["rows"]:
            sev = severity(r)
            sev_text, sev_color = SEVERITY_STYLE[sev]
            role = r.get("role", "default")
            role_text, role_color = ROLE_BADGE.get(role, ROLE_BADGE["default"])

            html_report += f"""
            <tr style="background:#fff;border-left:6px solid {sev_color};">
                <td><b>{html.escape(r["name"])}</b></td>
                <td>
                    <span style="padding:4px 10px;border-radius:12px;
                                 background:{role_color};
                                 color:white;font-size:12px;font-weight:600;">
                        {role_text}
                    </span>
                </td>
                <td>{r["ip"]}</td>
                <td style="color:{sev_color};font-weight:700;">{sev_text}</td>
                <td>{r["ping"]}</td>
                <td>{r["ssh"]}</td>
                <td>{r["last_seen"]}</td>
                <td><b>{node_status(r)}</b></td>
            </tr>
            """

        html_report += "</tbody></table></div>"

    html_report += """
    <div style="margin-top:30px;padding:14px;font-size:12px;color:#555;">
        Automated report generated by <b>SERC Resource Monitor</b>.
    </div>
    </div>
    """

    return html_report

