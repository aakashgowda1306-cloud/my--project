"""Builds the static review mockups (HTML) from shared pieces.

    python design/mockups/build.py        -> writes design/mockups/*.html
    node design/mockups/render.cjs        -> screenshots into design/screenshots/

All numbers shown come from the real synthetic dataset (synthetic-v1).
"""

from pathlib import Path

OUT = Path(__file__).parent

ICONS = {
    "home": '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "academy": '<path d="M2 8l10-5 10 5-10 5z"/><path d="M6 10v5c3 2 9 2 12 0v-5"/>',
    "soc": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "siem": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "forensics": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/>',
    "network": '<circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>'
               '<path d="M12 7v5M12 12l-6 5M12 12l6 5"/>',
    "ir": '<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/>',
    "award": '<circle cx="12" cy="9" r="6"/><path d="M8.5 14L7 22l5-3 5 3-1.5-8"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "more": '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    "shield": '<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/><path d="M9 12l2 2 4-4"/>',
}


def icon(name, size=18):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def page(title, body, extra_css="", width=1440):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width={width}"><title>{title} — Cybersec Academy (mockup)</title>
<link rel="stylesheet" href="../tokens/tokens.css"><style>{extra_css}</style></head><body>{body}</body></html>"""


def sidebar(active):
    learn = [("home", "Dashboard"), ("academy", "Academy")]
    labs = [("soc", "SOC Operations"), ("siem", "SIEM Lab"), ("forensics", "Forensics Lab"),
            ("network", "Network Lab"), ("ir", "Incident Response")]
    you = [("award", "Achievements"), ("user", "Profile"), ("settings", "Settings")]

    def group(title, items):
        links = "".join(f'<a class="nav-item{" active" if k == active else ""}" href="#">{icon(k)}{label}</a>'
                        for k, label in items)
        return f'<nav class="nav-group" aria-label="{title}"><h4>{title}</h4>{links}</nav>'

    return f"""<aside class="side"><div class="brand"><span class="brand-mark">{icon("shield", 16)}</span>Cybersec Academy</div>
{group("Learn", learn)}{group("Labs", labs)}{group("You", you)}
<div style="margin-top:auto" class="sim">Lab data is simulated</div></aside>"""


def topbar(title, sub=""):
    return f"""<header class="topbar"><div><h1>{title}</h1>{f'<p class="muted" style="font-size:var(--fs-sm)">{sub}</p>' if sub else ''}</div>
<div class="search">{icon("search", 16)} Search events, hosts, lessons</div><div class="avatar">AG</div></header>"""


# --------------------------------------------------------------------------- landing
LOG_LINES = [
    ("02:14:00", "Failed password for root from 203.0.113.45 port 40000"),
    ("02:14:18", "Failed password for root from 203.0.113.45 port 40126"),
    ("02:14:36", "Failed password for root from 203.0.113.45 port 40252"),
    ("02:14:54", "Failed password for root from 203.0.113.45 port 40378"),
    ("02:15:12", "Failed password for root from 203.0.113.45 port 40084"),
    ("02:15:30", "Failed password for root from 203.0.113.45 port 40210"),
    ("02:15:48", "Failed password for root from 203.0.113.45 port 40336"),
]

LANDING_CSS = """
.wrap { max-width: 1200px; margin: 0 auto; padding: 0 var(--s6); }
.top { display:flex; align-items:center; justify-content:space-between; height:72px; }
.top nav { display:flex; gap:28px; font-size:var(--fs-sm); color:var(--text-muted); }
.hero { display:grid; grid-template-columns: 1fr 1.08fr; gap: 56px; align-items:center; padding: 56px 0 88px; }
.hero h1 { font-size: 52px; line-height: 1.06; letter-spacing: -0.025em; font-weight: 600; max-width: 12ch; }
.hero p.lede { font-size: var(--fs-md); color: var(--text-muted); margin: 22px 0 30px; max-width: 46ch; }
.hero .ctas { display:flex; gap:12px; align-items:center; }
.hero .fine { margin-top: 18px; font-size: var(--fs-xs); color: var(--text-faint); }
.term { background: #08101F; border:1px solid var(--line); border-radius: var(--r-lg); overflow:hidden; }
.term-head { display:flex; justify-content:space-between; padding:10px 16px; border-bottom:1px solid var(--line-soft);
             font-size: var(--fs-xs); color: var(--text-faint); }
.term-body { padding: 14px 16px 6px; font-family: var(--font-mono); font-size: 12.5px; line-height: 1.85; }
.term-body .t { color: var(--text-faint); margin-right: 12px; }
.term-body .hl { color: var(--sev-medium); }
.term-body .line { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.term-body .line:nth-child(n+5) { box-shadow: inset 2px 0 0 var(--sev-medium); padding-left: 8px; margin-left: -10px; }
.detect { margin: 6px 16px 16px; border:1px solid rgba(233,199,95,.35); background: rgba(233,199,95,.07);
          border-radius: var(--r-md); padding: 14px 16px; }
.detect strong { font-size: var(--fs-sm); }
.detect dl { display:grid; grid-template-columns: 150px 1fr; gap: 6px 14px; margin-top: 10px; font-size: var(--fs-sm); }
.detect dt { color: var(--text-faint); } .detect dd { margin:0; }
section.block { padding: 72px 0; border-top: 1px solid var(--line-soft); }
section.block h2 { font-size: var(--fs-2xl); letter-spacing: -0.015em; font-weight: 600; max-width: 22ch; }
section.block p.intro { color: var(--text-muted); max-width: 60ch; margin-top: 12px; }
.depts { display:grid; grid-template-columns: 1fr 1fr; margin-top: 36px; border-top:1px solid var(--line-soft); }
.dept { display:grid; grid-template-columns: 40px 1fr; gap: 14px; padding: 22px 24px 22px 0; border-bottom:1px solid var(--line-soft); }
.dept:nth-child(odd) { border-right: 1px solid var(--line-soft); }
.dept:nth-child(even) { padding-left: 24px; }
.dept .ic { width:40px; height:40px; border-radius: var(--r-md); background: var(--surface); border:1px solid var(--line);
            display:grid; place-items:center; color: var(--electric); }
.dept h3 { font-size: var(--fs-md); font-weight: 600; }
.dept p { color: var(--text-muted); font-size: var(--fs-sm); margin-top: 4px; max-width: 46ch; }
.steps { display:grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin-top: 36px; counter-reset: s; }
.step { padding: 0 24px 0 0; position:relative; }
.step::before { counter-increment: s; content: counter(s); display:grid; place-items:center; width:30px; height:30px;
                border-radius:50%; border:1px solid var(--electric); color: var(--electric); font-weight:600;
                font-size: var(--fs-sm); margin-bottom: 14px; background: var(--abyss); position:relative; z-index:1; }
.step::after { content:""; position:absolute; top:15px; left:30px; right:0; height:1px; background: var(--line); }
.step:last-child::after { display:none; }
.step h3 { font-size: var(--fs-base); font-weight: 600; } .step p { color: var(--text-muted); font-size: var(--fs-sm); margin-top:4px; }
.split { display:grid; grid-template-columns: 1fr 1fr; gap: 56px; margin-top: 8px; }
.boundary { border:1px dashed var(--line); border-radius: var(--r-lg); padding: 28px; }
.boundary ul { margin-top: 12px; padding-left: 18px; color: var(--text-muted); font-size: var(--fs-sm); line-height: 1.9; }
.who li { padding: 12px 0; border-bottom: 1px solid var(--line-soft); list-style: none; }
.who { padding: 0; margin-top: 12px; } .who span { color: var(--text-muted); font-size: var(--fs-sm); display:block; }
.final { text-align:left; display:flex; justify-content:space-between; align-items:center; }
footer { padding: 28px 0 40px; border-top:1px solid var(--line-soft); color: var(--text-faint); font-size: var(--fs-xs);
         display:flex; justify-content:space-between; }
"""

DEPARTMENTS = [
    ("soc", "SOC Operations Centre", "Watch a live-style security dashboard built from 352 synthetic events and triage 18 alerts."),
    ("siem", "SIEM Investigation Lab", "Search Windows, Linux, VPN and firewall logs, then run ten detection rules mapped to MITRE ATT&CK."),
    ("forensics", "Digital Forensics Lab", "Hash evidence files, follow a chain of custody and rebuild a timeline from exported records."),
    ("network", "Network Security Lab", "Explore a fictional company network, step through a TCP handshake and practise subnetting."),
    ("ir", "Incident Response Centre", "Take four fictional incidents through nine response stages and write the post-incident report."),
    ("academy", "Cybersecurity Academy", "Short lessons in plain English, each ending with a quiz and a practical task in one of the labs."),
]


def landing():
    log = "".join(f'<div class="line"><span class="t">Nov 17 {t}</span>sshd: <span class="hl">{m}</span></div>' for t, m in LOG_LINES)
    depts = "".join(f'<div class="dept"><span class="ic">{icon(k, 20)}</span><div><h3>{t}</h3><p>{d}</p></div></div>'
                    for k, t, d in DEPARTMENTS)
    body = f"""<div class="wrap">
<header class="top"><div class="brand"><span class="brand-mark">{icon("shield", 16)}</span>Cybersec Academy</div>
<nav><a href="#">Labs</a><a href="#">Courses</a><a href="#">How it works</a><a href="#">Safety</a></nav>
<div style="display:flex;gap:10px"><a class="btn btn-ghost" href="#">Sign in</a><a class="btn btn-primary" href="#">Create free account</a></div></header>

<section class="hero"><div>
<h1>Practise defending a network that doesn’t exist.</h1>
<p class="lede">Cybersec Academy is a free learning platform for cybersecurity beginners. Short lessons, then hands-on investigations in the logs, evidence and incidents of ExampleCorp — a company we invented so you can learn without touching real systems.</p>
<div class="ctas"><a class="btn btn-primary" href="#">Start learning free</a><a class="btn btn-ghost" href="#">See a lab</a></div>
<p class="fine">Learn. Investigate. Defend. Master Cybersecurity.</p></div>

<div class="term" role="img" aria-label="Example lab: failed SSH logins that trigger a detection">
<div class="term-head"><span>lnx-bastion-01.corp.example · /var/log/auth.log</span><span class="sim">Simulated data</span></div>
<div class="term-body">{log}</div>
<div class="detect"><strong><span class="sev sev-medium">Medium</span>&nbsp; CSA-DET-001 · Repeated failed login activity</strong>
<dl><dt>What was detected</dt><dd>12 failed logins for root from 203.0.113.45 in 3 minutes</dd>
<dt>MITRE ATT&amp;CK</dt><dd>T1110 Brute Force</dd>
<dt>Your next step</dt><dd>Check whether any attempt from this address succeeded</dd></dl></div></div>
</section>

<section class="block"><h2>Six departments, one fictional company</h2>
<p class="intro">Every lab shares the same synthetic world, so a clue you find in the SIEM shows up again in forensics and incident response.</p>
<div class="depts">{depts}</div></section>

<section class="block"><h2>How every lab works</h2>
<div class="steps">
<div class="step"><h3>Learn the idea</h3><p>A 15-minute lesson explains one concept with a worked example.</p></div>
<div class="step"><h3>Investigate</h3><p>Open the lab and search the simulated data yourself.</p></div>
<div class="step"><h3>Submit a finding</h3><p>Enter what you found. It is checked on the server.</p></div>
<div class="step"><h3>Understand why</h3><p>See the explanation, earn progress and move to the next lab.</p></div>
</div></section>

<section class="block"><div class="split">
<div><h2>Built for people starting out</h2><ul class="who">
<li>Engineering and cybersecurity students<span>Turn theory into investigations you can explain in an interview.</span></li>
<li>Aspiring SOC and blue-team analysts<span>Triage alerts, write verdicts and practise incident workflows.</span></li>
<li>Portfolio builders<span>Finish labs and share your post-incident reports.</span></li></ul></div>
<div class="boundary"><h2 style="font-size:var(--fs-xl)">A clear safety boundary</h2>
<ul><li>Every log, host, person and incident is fictional.</li>
<li>External addresses come only from ranges reserved for documentation.</li>
<li>Nothing in the platform scans, connects to or attacks a real system.</li>
<li>Every exercise states its objective, environment and restrictions.</li></ul></div></div></section>

<section class="block final"><div><h2>Your first investigation takes 20 minutes.</h2>
<p class="intro">Create an account with your email address. No payment details, no software to install.</p></div>
<a class="btn btn-primary" href="#" style="height:48px;padding:0 26px">Create free account</a></section>
<footer><span>Cybersec Academy — educational platform. All lab data is synthetic.</span><span>Lab safety · Privacy · GitHub</span></footer>
</div>"""
    return page("Landing", body, LANDING_CSS)


# --------------------------------------------------------------------------- dashboard
DASH_CSS = """
.grid { display:grid; grid-template-columns: 1.5fr 1fr; gap: var(--s5); }
.continue { display:grid; grid-template-columns: 1fr auto; gap: var(--s5); align-items:center; }
.continue h2 { font-size: var(--fs-xl); font-weight:600; margin: 6px 0; }
.bar { height:6px; background: var(--raised); border-radius:99px; overflow:hidden; }
.bar > i { display:block; height:100%; background: var(--cyan); border-radius:99px; }
.stats { display:grid; grid-template-columns: repeat(4,1fr); gap: var(--s4); margin: var(--s5) 0; }
.stat { padding: var(--s4) var(--s5); border-left: 1px solid var(--line); }
.stat:first-child { border-left: 0; padding-left: 0; }
.stat b { font-size: var(--fs-2xl); font-weight: 600; display:block; line-height:1.1; }
.stat span { font-size: var(--fs-sm); color: var(--text-muted); }
.course { display:grid; grid-template-columns: 1fr 120px 52px; gap: var(--s4); align-items:center; padding: 14px 0;
          border-top: 1px solid var(--line-soft); font-size: var(--fs-sm); }
.course:first-of-type { border-top:0; }
.queue li { list-style:none; display:grid; grid-template-columns: 84px 1fr; gap: 12px; padding: 12px 0;
            border-top:1px solid var(--line-soft); font-size: var(--fs-sm); }
.queue { padding:0; } .queue li:first-child { border-top:0; }
.streak { display:flex; gap:6px; margin-top: 12px; }
.streak i { flex:1; height: 28px; border-radius: var(--r-sm); background: var(--raised); }
.streak i.on { background: var(--cyan); opacity:.85; }
.badges { display:flex; gap: 10px; margin-top: 12px; }
.badge { width: 52px; height: 52px; border-radius: 50%; display:grid; place-items:center; border:1px solid var(--line);
         color: var(--text-faint); }
.badge.earned { color: var(--cyan); border-color: var(--cyan); background: var(--cyan-soft); }
"""


def dashboard():
    courses = [("Cybersecurity Fundamentals", 67, "2 of 3"), ("Computer Networking Basics", 33, "1 of 3"),
               ("SOC Operations and Log Analysis", 0, "0 of 2")]
    course_rows = "".join(
        f'<div class="course"><div><b style="font-weight:500">{t}</b><div class="faint">{n} lessons</div></div>'
        f'<div class="bar"><i style="width:{p}%"></i></div><span class="muted">{p}%</span></div>' for t, p, n in courses)
    body = f"""<div class="shell">{sidebar("home")}<main class="main">
{topbar("Good evening, Aakash", "You have 18 alerts waiting in the SOC queue and one lesson in progress.")}
<div class="grid"><div>
<section class="panel continue"><div><span class="muted" style="font-size:var(--fs-sm)">Continue learning · Computer Networking Basics</span>
<h2>TCP, UDP and ports</h2><p class="muted" style="font-size:var(--fs-sm);max-width:56ch">Read a connection record and explain what the ports and TCP flags tell you. Ends with a lab: find the beaconing host.</p>
<div class="bar" style="margin-top:16px;max-width:360px"><i style="width:40%"></i></div></div>
<a class="btn btn-primary" href="#">Resume lesson</a></section>

<div class="stats">
<div class="stat"><b>3/8</b><span>lessons completed</span></div>
<div class="stat"><b>2</b><span>quizzes passed</span></div>
<div class="stat"><b>4/10</b><span>labs solved</span></div>
<div class="stat"><b>1</b><span>incident resolved</span></div></div>

<section class="panel"><div class="panel-head"><h2>Your learning paths</h2><a href="#">Browse all courses</a></div>{course_rows}</section>
</div>

<div style="display:flex;flex-direction:column;gap:var(--s5)">
<section class="panel"><div class="panel-head"><h2>SOC queue</h2><a href="#">Open SOC</a></div>
<ul class="queue">
<li><span class="sev sev-critical">Critical</span><div>Security audit log cleared on srv-dc-01<div class="faint">CSA-DET-008 · Sat 21 Nov 03:25</div></div></li>
<li><span class="sev sev-critical">Critical</span><div>Service WinUpdSvc32 installed from a user-writable path<div class="faint">CSA-DET-006 · Sat 21 Nov 03:12</div></div></li>
<li><span class="sev sev-high">High</span><div>Outbound connections from ws-fin-02 to 203.0.113.200:4444<div class="faint">CSA-DET-005 · Fri 20 Nov 22:48</div></div></li></ul></section>

<section class="panel"><div class="panel-head"><h2>3-day streak</h2><span class="muted" style="font-size:var(--fs-sm)">Last 7 days</span></div>
<div class="streak"><i></i><i></i><i></i><i></i><i class="on"></i><i class="on"></i><i class="on"></i></div></section>

<section class="panel"><div class="panel-head"><h2>Achievements</h2><a href="#">4 of 10</a></div>
<div class="badges"><span class="badge earned">{icon("academy",20)}</span><span class="badge earned">{icon("shield",20)}</span>
<span class="badge earned">{icon("award",20)}</span><span class="badge earned">{icon("siem",20)}</span><span class="badge">{icon("ir",20)}</span></div></section>
</div></div></main></div>"""
    return page("Student dashboard", body, DASH_CSS)


# --------------------------------------------------------------------------- SOC
DAYS = [("Mon 16", {"info": 48, "low": 2}), ("Tue 17", {"info": 49, "medium": 13, "low": 5}),
        ("Wed 18", {"info": 49, "medium": 7, "low": 2}), ("Thu 19", {"info": 49, "low": 10, "high": 1}),
        ("Fri 20", {"info": 48, "low": 2, "medium": 6, "high": 9}),
        ("Sat 21", {"info": 21, "medium": 1, "critical": 2, "high": 2, "low": 2}), ("Sun 22", {"info": 21, "low": 3})]
SEV_ORDER = ["info", "low", "medium", "high", "critical"]

SOC_CSS = """
.kpis { display:grid; grid-template-columns: 1.2fr repeat(4, 1fr); border:1px solid var(--line-soft); border-radius: var(--r-lg);
        background: var(--surface); margin-bottom: var(--s5); }
.kpi { padding: 18px 22px; border-left:1px solid var(--line-soft); }
.kpi:first-child { border-left:0; }
.kpi b { display:block; font-size: 30px; font-weight:600; line-height:1.15; }
.kpi span { font-size: var(--fs-sm); color: var(--text-muted); }
.sevbar { display:flex; height:8px; border-radius:99px; overflow:hidden; margin-top: 12px; gap:2px; }
.chain { position:relative; height: 64px; margin-top: 12px; }
.axis { position:absolute; left:0; right:0; top: 30px; height:1px; background: var(--line); }
.day { position:absolute; top: 40px; font-size: var(--fs-xs); color: var(--text-faint); transform: translateX(-50%); }
.tick { position:absolute; top: 8px; width: 3px; height: 22px; border-radius:2px; }
.steps-list { display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px 20px; padding:0; margin-top: 14px; counter-reset: st; }
.steps-list li { list-style:none; border-left: 2px solid; padding: 4px 0 4px 12px; font-size: var(--fs-sm);
                 display:grid; grid-template-columns: 1fr auto; column-gap: 8px; }
.steps-list li b { font-weight: 500; grid-column: 1 / -1; order: 2; }
.steps-list li .faint { font-size: var(--fs-xs); }
.cols { display:grid; grid-template-columns: 1.35fr 1fr; gap: var(--s5); margin-top: var(--s5); }
.chart { display:flex; align-items:flex-end; gap: 18px; height: 170px; padding-top: 8px; }
.chart .c { flex:1; display:flex; flex-direction:column-reverse; gap:2px; }
.chart .c i { display:block; border-radius: 2px; }
.chart-x { display:flex; gap:18px; margin-top: 8px; } .chart-x span { flex:1; text-align:center; font-size: var(--fs-xs); color: var(--text-faint); }
.legend { display:flex; gap: 16px; margin-top: 14px; }
.rules td:last-child { text-align:right; } .rules .mono { color: var(--text-muted); }
"""


def soc():
    max_total = max(sum(v.values()) for _, v in DAYS)
    colors = {"info": "var(--sev-info)", "low": "var(--sev-low)", "medium": "var(--sev-medium)",
              "high": "var(--sev-high)", "critical": "var(--sev-critical)"}
    cols = ""
    for _, v in DAYS:
        segs = "".join(f'<i style="height:{v[s] / max_total * 160:.1f}px;background:{colors[s]};opacity:{0.45 if s == "info" else 1}"></i>'
                       for s in SEV_ORDER if v.get(s))
        cols += f'<div class="c">{segs}</div>'
    xs = "".join(f"<span>{d}</span>" for d, _ in DAYS)
    legend = "".join(f'<span class="sev sev-{s}">{s.capitalize()}</span>' for s in reversed(SEV_ORDER))
    # Attack chain: ticks on a week axis (position = hours since Mon 00:00 UTC), then the ordered steps.
    chain = [(26.2, "medium", "Tue 17 02:14", "Brute force against the SSH bastion", "CSA-DET-001"),
             (49.7, "high", "Wed 18 01:40", "Password spray on the VPN portal", "CSA-DET-002"),
             (118.15, "high", "Fri 20 22:09", "VPN sign-in succeeds after 6 failures", "CSA-DET-003"),
             (118.5, "high", "Fri 20 22:31", "Account adds itself to Domain Admins", "CSA-DET-004"),
             (118.7, "high", "Fri 20 22:44", "Word starts hidden, encoded PowerShell", "CSA-DET-010"),
             (118.8, "high", "Fri 20 22:48", "Beacon to 203.0.113.200 on port 4444", "CSA-DET-005"),
             (119.0, "high", "Fri 20 23:02", "Hidden scheduled task created", "CSA-DET-007"),
             (123.2, "critical", "Sat 21 03:12", "Service installed from C:\\Users\\Public", "CSA-DET-006"),
             (123.4, "critical", "Sat 21 03:25", "Security audit log cleared", "CSA-DET-008")]
    ticks = "".join(f'<i class="tick" style="left:{h / 168 * 100:.2f}%;background:{colors[sev]}"></i>' for h, sev, *_ in chain)
    days = "".join(f'<span class="day" style="left:{(i * 24 + 12) / 168 * 100:.2f}%">{d}</span>' for i, (d, _) in enumerate(DAYS))
    steps = "".join(f'<li style="border-color:{colors[sev]}"><span class="faint">{t}</span><b>{label}</b><span class="mono faint">{rule}</span></li>'
                    for _, sev, t, label, rule in chain)
    rules = [("CSA-DET-001", "Repeated failed logins", "T1110", 3), ("CSA-DET-008", "Defences weakened / logs cleared", "T1562", 3),
             ("CSA-DET-004", "Privileged group change", "T1098", 2), ("CSA-DET-007", "Suspicious scheduled task", "T1053.005", 2),
             ("CSA-DET-009", "Off-hours sign-in", "T1078", 2), ("CSA-DET-010", "Suspicious process", "T1059.001", 2)]
    rule_rows = "".join(f'<tr><td><span class="mono">{i}</span><br>{n}</td><td class="mono">{m}</td><td>{c}</td></tr>' for i, n, m, c in rules)
    body = f"""<div class="shell">{sidebar("soc")}<main class="main">
{topbar("SOC Operations Centre", "ExampleCorp · 16–22 November 2026 · dataset synthetic-v1")}
<div class="kpis">
<div class="kpi"><span>Security events</span><b>352</b>
<div class="sevbar"><i style="flex:285;background:var(--sev-info);opacity:.45"></i><i style="flex:26;background:var(--sev-low)"></i><i style="flex:27;background:var(--sev-medium)"></i><i style="flex:12;background:var(--sev-high)"></i><i style="flex:2;background:var(--sev-critical)"></i></div></div>
<div class="kpi"><span class="sev sev-critical">Critical alerts</span><b>2</b></div>
<div class="kpi"><span class="sev sev-high">High alerts</span><b>11</b></div>
<div class="kpi"><span class="sev sev-medium">Medium alerts</span><b>5</b></div>
<div class="kpi"><span>Your triage</span><b>3<span style="font-size:var(--fs-md);color:var(--text-faint)"> / 18</span></b><span>closed · 4 incidents open</span></div></div>

<section class="panel"><div class="panel-head"><h2>Attack chain: from guessed password to cleared logs</h2><span class="sim">Simulated data</span></div>
<p class="muted" style="font-size:var(--fs-sm);max-width:80ch">Alerts that share the account m.okafor or the address range 203.0.113.0/24, plotted across the week. Clusters show where to start investigating.</p>
<div class="chain"><div class="axis"></div>{days}{ticks}</div><ol class="steps-list">{steps}</ol></section>

<div class="cols">
<section class="panel"><div class="panel-head"><h2>Events per day by severity</h2><a href="#">Open in SIEM</a></div>
<div class="chart">{cols}</div><div class="chart-x">{xs}</div><div class="legend">{legend}</div></section>
<section class="panel"><div class="panel-head"><h2>Detections that fired</h2><a href="#">All 10 rules</a></div>
<table class="rules"><thead><tr><th>Rule</th><th>ATT&amp;CK</th><th>Alerts</th></tr></thead><tbody>{rule_rows}</tbody></table></section>
</div></main></div>"""
    return page("SOC Operations Centre", body, SOC_CSS)


# --------------------------------------------------------------------------- SIEM
SIEM_EVENTS = [
    (52, "Tue 17 02:14:00", "linux", "lnx-bastion-01", "medium", "Failed password for root from 203.0.113.45 port 40000"),
    (53, "Tue 17 02:14:18", "linux", "lnx-bastion-01", "medium", "Failed password for root from 203.0.113.45 port 40126"),
    (54, "Tue 17 02:14:36", "linux", "lnx-bastion-01", "medium", "Failed password for root from 203.0.113.45 port 40252"),
    (55, "Tue 17 02:14:54", "linux", "lnx-bastion-01", "medium", "Failed password for root from 203.0.113.45 port 40378"),
    (289, "Fri 20 22:07:00", "authentication", "vpn-gw-01", "medium", "VPN sign-in failed: invalid credentials for m.okafor from 203.0.113.45"),
    (290, "Fri 20 22:07:30", "authentication", "vpn-gw-01", "medium", "VPN sign-in failed: invalid credentials for m.okafor from 203.0.113.45"),
    (291, "Fri 20 22:09:00", "authentication", "vpn-gw-01", "high", "VPN sign-in succeeded for m.okafor from 203.0.113.45"),
]

SIEM_CSS = """
.layout { display:grid; grid-template-columns: 1fr 400px; gap: var(--s5); }
.query { display:flex; gap: 10px; margin-bottom: var(--s4); }
.query .q { flex:1; height:42px; background: var(--surface); border:1px solid var(--electric); border-radius: var(--r-md);
            display:flex; align-items:center; padding: 0 14px; gap:10px; font-family: var(--font-mono); font-size: 13px; }
.chips { display:flex; gap: 8px; flex-wrap: wrap; margin-bottom: var(--s4); }
.chip { height: 30px; display:inline-flex; align-items:center; gap:6px; padding: 0 12px; border-radius: 99px;
        background: var(--surface); border:1px solid var(--line); font-size: var(--fs-xs); color: var(--text-muted); }
.chip.on { border-color: var(--electric); color: var(--text); background: var(--electric-soft); }
.events td:nth-child(4) { white-space: nowrap; }
.events td.msg { font-family: var(--font-mono); font-size: 12.5px; }
.events td.time { white-space:nowrap; color: var(--text-muted); font-family: var(--font-mono); font-size: 12.5px; }
.detail h3 { font-size: var(--fs-md); font-weight:600; margin: 6px 0 14px; }
.kv { display:grid; grid-template-columns: 110px 1fr; gap: 8px 12px; font-size: var(--fs-sm); }
.kv dt { color: var(--text-faint); } .kv dd { margin:0; }
.q5 { margin-top: var(--s5); border-top: 1px solid var(--line-soft); padding-top: var(--s4); }
.q5 ol { padding-left: 18px; font-size: var(--fs-sm); color: var(--text-muted); line-height: 1.7; }
.q5 ol b { color: var(--text); font-weight: 500; display:block; }
.actions { display:flex; gap: 10px; margin-top: var(--s5); }
.resultbar { display:flex; justify-content:space-between; font-size: var(--fs-sm); color: var(--text-muted); margin-bottom: var(--s2); }
"""


def siem():
    rows_html = "".join(
        f'<tr class="{"selected" if i == 291 else ""}"><td class="time">{t}</td><td><span class="sev sev-{s}">{s.capitalize()}</span></td>'
        f'<td>{src}</td><td>{h}</td><td class="msg">{m}</td></tr>' for i, t, src, h, s, m in SIEM_EVENTS)
    body = f"""<div class="shell">{sidebar("siem")}<main class="main">
{topbar("SIEM Investigation Lab", "Search 352 simulated events from Windows, Linux, VPN, web and firewall sources")}
<div class="query"><div class="q">{icon("search", 16)} 203.0.113.45</div><a class="btn btn-primary" href="#">Search</a></div>
<div class="chips"><span class="chip on">Outcome: any</span><span class="chip">Source: all</span><span class="chip">Severity: all</span>
<span class="chip">Host</span><span class="chip">User</span><span class="chip">16–22 Nov 2026</span><span class="sim" style="margin-left:auto">Simulated data</span></div>
<div class="layout"><section class="panel" style="padding:var(--s4) 0">
<div class="resultbar" style="padding:0 var(--s5)"><span>19 events match · sorted by time</span><span>Page 1 of 1</span></div>
<table class="events"><thead><tr><th style="padding-left:var(--s5)">Time (UTC)</th><th>Severity</th><th>Source</th><th>Host</th><th>Message</th></tr></thead>
<tbody>{rows_html}</tbody></table></section>

<aside class="panel detail"><span class="sev sev-high">High</span>
<h3>VPN sign-in succeeded for m.okafor</h3>
<dl class="kv"><dt>Event</dt><dd class="mono">#291 · VPN_AUTH</dd><dt>Time</dt><dd>Fri 20 Nov 2026, 22:09:00 UTC</dd>
<dt>Host</dt><dd>vpn-gw-01.corp.example</dd><dt>Account</dt><dd>m.okafor</dd><dt>Source IP</dt><dd class="mono">203.0.113.45</dd>
<dt>Related alert</dt><dd><a href="#" style="color:var(--electric)">CSA-DET-003 · Success after 6 failures</a></dd></dl>
<div class="q5"><h4 style="font-size:var(--fs-sm);margin-bottom:8px">Analyst questions</h4><ol>
<li><b>What was detected?</b>A successful login right after six failures from the same address.</li>
<li><b>Why does it matter?</b>The password was probably guessed; the attacker may now hold a valid account.</li>
<li><b>What should you check next?</b>Everything m.okafor did after 22:09.</li></ol></div>
<div class="actions"><a class="btn btn-primary" href="#">Start investigation</a><a class="btn btn-ghost" href="#">Add note</a></div></aside>
</div></main></div>"""
    return page("SIEM Investigation Lab", body, SIEM_CSS)


# --------------------------------------------------------------------------- mobile
MOBILE_CSS = """
body { width: 390px; }
.m { padding: 16px 16px 96px; }
.mtop { display:flex; align-items:center; justify-content:space-between; margin-bottom: 18px; }
.mtop h1 { font-size: var(--fs-lg); font-weight:600; }
.card { background: var(--surface); border:1px solid var(--line-soft); border-radius: var(--r-lg); padding: 16px; margin-bottom: 14px; }
.card h2 { font-size: var(--fs-md); font-weight:600; margin: 4px 0 8px; }
.bar { height:6px; background: var(--raised); border-radius:99px; overflow:hidden; }
.bar > i { display:block; height:100%; background: var(--cyan); }
.row2 { display:grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.row2 .card { margin:0; } .row2 b { font-size: 26px; font-weight:600; display:block; }
.row2 span { font-size: var(--fs-xs); color: var(--text-muted); }
.list li { list-style:none; padding: 12px 0; border-top:1px solid var(--line-soft); font-size: var(--fs-sm); }
.list { padding:0; } .list li:first-child { border-top:0; padding-top: 4px; }
.tabbar { position:fixed; bottom:0; left:0; width:390px; height: 72px; background: var(--surface); border-top:1px solid var(--line);
          display:grid; grid-template-columns: repeat(5, 1fr); padding-bottom: 8px; }
.tabbar a { display:flex; flex-direction:column; align-items:center; justify-content:center; gap: 4px; font-size: 11px; color: var(--text-faint); }
.tabbar a.on { color: var(--electric); }
.mq { height: 44px; background: var(--surface); border:1px solid var(--electric); border-radius: var(--r-md); display:flex;
      align-items:center; gap:8px; padding: 0 12px; font-family: var(--font-mono); font-size: 13px; margin-bottom: 10px; }
.mchips { display:flex; gap: 8px; overflow:hidden; margin-bottom: 14px; }
.mchips span { flex: none; height: 32px; padding: 0 12px; border-radius: 99px; border:1px solid var(--line); display:flex;
               align-items:center; font-size: var(--fs-xs); color: var(--text-muted); background: var(--surface); }
.ev { background: var(--surface); border:1px solid var(--line-soft); border-radius: var(--r-md); padding: 12px 14px; margin-bottom: 10px; }
.ev .meta { display:flex; justify-content:space-between; font-size: var(--fs-xs); color: var(--text-faint); margin-bottom: 6px; }
.ev p { font-family: var(--font-mono); font-size: 12.5px; line-height: 1.5; }
.ev.sel { border-color: var(--electric); }
"""


def tabbar(active):
    items = [("home", "Home"), ("academy", "Learn"), ("soc", "SOC"), ("siem", "Labs"), ("more", "More")]
    return '<nav class="tabbar" aria-label="Main">' + "".join(
        f'<a class="{"on" if k == active else ""}" href="#">{icon(k, 22)}{label}</a>' for k, label in items) + "</nav>"


def mobile_dashboard():
    body = f"""<div class="m"><div class="mtop"><div class="brand" style="padding:0"><span class="brand-mark">{icon("shield", 16)}</span></div>
<h1>Dashboard</h1><div class="avatar">AG</div></div>
<div class="card"><span class="muted" style="font-size:var(--fs-xs)">Continue · Networking Basics</span><h2>TCP, UDP and ports</h2>
<div class="bar"><i style="width:40%"></i></div><a class="btn btn-primary" style="width:100%;justify-content:center;margin-top:14px;height:44px" href="#">Resume lesson</a></div>
<div class="row2"><div class="card"><b>3</b><span>day streak</span></div><div class="card"><b>4/10</b><span>labs solved</span></div></div>
<div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><h2>SOC queue</h2><span class="sim">Simulated</span></div>
<ul class="list"><li><span class="sev sev-critical">Critical</span><div>Security audit log cleared on srv-dc-01</div></li>
<li><span class="sev sev-critical">Critical</span><div>Service installed from a user-writable path</div></li>
<li><span class="sev sev-high">High</span><div>Outbound connections to 203.0.113.200:4444</div></li></ul></div>
<div class="card"><h2>Learning paths</h2>
<div style="font-size:var(--fs-sm);margin:10px 0 6px">Cybersecurity Fundamentals <span class="faint" style="float:right">67%</span></div><div class="bar"><i style="width:67%"></i></div>
<div style="font-size:var(--fs-sm);margin:14px 0 6px">Computer Networking Basics <span class="faint" style="float:right">33%</span></div><div class="bar"><i style="width:33%"></i></div></div>
</div>{tabbar("home")}"""
    return page("Mobile dashboard", body, MOBILE_CSS, width=390)


def mobile_siem():
    evs = [("Fri 20 22:09:00", "high", "vpn-gw-01", "VPN sign-in succeeded for m.okafor from 203.0.113.45", True),
           ("Fri 20 22:07:30", "medium", "vpn-gw-01", "VPN sign-in failed: invalid credentials for m.okafor from 203.0.113.45", False),
           ("Fri 20 22:07:00", "medium", "vpn-gw-01", "VPN sign-in failed: invalid credentials for m.okafor from 203.0.113.45", False),
           ("Tue 17 02:14:18", "medium", "lnx-bastion-01", "Failed password for root from 203.0.113.45 port 40126", False)]
    cards = "".join(f'<div class="ev{" sel" if sel else ""}"><div class="meta"><span class="sev sev-{s}">{s.capitalize()}</span><span>{t}</span></div>'
                    f'<p>{m}</p><div class="faint" style="font-size:var(--fs-xs);margin-top:6px">{h}.corp.example</div></div>'
                    for t, s, h, m, sel in evs)
    body = f"""<div class="m"><div class="mtop"><h1>SIEM Lab</h1><span class="sim">Simulated data</span></div>
<div class="mq">{icon("search", 16)} 203.0.113.45</div>
<div class="mchips"><span>Severity</span><span>Source</span><span>Outcome</span><span>Host</span><span>Dates</span></div>
<p class="muted" style="font-size:var(--fs-xs);margin-bottom:10px">19 events · newest first · tap an event to investigate</p>{cards}
</div>{tabbar("siem")}"""
    return page("Mobile SIEM", body, MOBILE_CSS, width=390)


if __name__ == "__main__":
    for name, fn in [("landing", landing), ("dashboard", dashboard), ("soc", soc), ("siem", siem),
                     ("mobile-dashboard", mobile_dashboard), ("mobile-siem", mobile_siem)]:
        (OUT / f"{name}.html").write_text(fn())
        print("wrote", name)
