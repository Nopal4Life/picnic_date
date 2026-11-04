"""Confirmation emails over SMTP: one to her, and a copy of what she picked to me.

Uses a Gmail "app password" (Google account > Security > 2-Step Verification > App passwords),
which goes in .streamlit/secrets.toml under [email]; see secrets.toml.example.
"""
import html
import json
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from invite import details, make_ics

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOG = Path(__file__).parent / "submissions.jsonl"


def valid_email(text):
    return bool(EMAIL_RE.match((text or "").strip()))


def settings_from(secrets):
    """SMTP login + my address; None if email isn't set up."""
    try:
        email = secrets["email"]
        cfg = {
            "host": email.get("smtp_host") or "smtp.gmail.com",
            "port": int(email.get("smtp_port") or 465),
            "user": email["username"],
            "password": email["app_password"],
            "his_email": secrets["picnic"]["his_email"],
        }
    except Exception:  # no secrets file, or a key is missing
        return None
    return cfg if all(cfg[k] for k in ("user", "password", "his_email")) else None


def _table(rows):
    cells = "".join(
        f'<tr><td style="background:#ff8fc0;color:#6b4a45;font:700 18px Georgia,serif;padding:10px 16px;'
        f'border-bottom:2px dashed #fff">{html.escape(label)}</td>'
        f'<td style="background:#fff6fa;color:#6b4a45;font:16px Arial,sans-serif;padding:10px 16px;'
        f'border-bottom:2px dashed #f4b6d2">{html.escape(value)}</td></tr>'
        for label, value in rows
    )
    return f'<table cellspacing="0" style="border:3px solid #6b4a45;border-radius:14px;border-collapse:separate;width:100%;max-width:440px">{cells}</table>'


def build_messages(cfg, plan, her_email, start, end):
    """[confirmation to her, 'what she picked' to me]. Her .ics rides along so it opens in Calendar."""
    rows = details(plan)
    lines = "\n".join(f"{label}: {value}" for label, value in rows)
    when = start.strftime("%A, %B %-d at %-I:%M %p")

    to_her = EmailMessage()
    to_her["From"], to_her["To"], to_her["Subject"] = cfg["user"], her_email, "Our picnic is on!"
    to_her.set_content(f"Yay, it's a date! {when}.\n\n{lines}\n\nSee you there!")
    to_her.add_alternative(
        f'<div style="font-family:Arial,sans-serif;color:#6b4a45">'
        f'<h2 style="font-family:Georgia,serif;color:#e8559a;margin:0 0 4px">Yay, it\'s a date!</h2>'
        f'<p style="margin:0 0 14px">{html.escape(when)}</p>{_table(rows)}<p>See you there!</p></div>',
        subtype="html",
    )
    to_her.add_attachment(
        make_ics(plan, start, end).encode(), maintype="text", subtype="calendar",
        filename="picnic-date.ics", params={"method": "PUBLISH"},
    )

    customized = any(plan.get(k) for k in ("where", "food", "drinks", "avoid"))
    to_him = EmailMessage()
    to_him["From"], to_him["To"], to_him["Reply-To"] = cfg["user"], cfg["his_email"], her_email
    to_him["Subject"] = "She said yes!"
    to_him.set_content(
        f"She said yes! {when}.\n\nHer email: {her_email}\n"
        f"{'She customized the picnic:' if customized else 'She kept the plan as is:'}\n\n{lines}\n"
    )
    return [to_her, to_him]


def send_all(cfg, messages, connect=None):
    """Send over one SMTP session. `connect` lets tests swap in a fake server."""
    ctx = ssl.create_default_context()
    if connect:
        server = connect()
    elif cfg["port"] == 465:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx, timeout=20)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
    with server as s:
        if not connect and cfg["port"] != 465:
            s.starttls(context=ctx)
        s.login(cfg["user"], cfg["password"])
        for message in messages:
            s.send_message(message)


def log_submission(plan, her_email, path=LOG):
    """Local backup of what she picked (git-ignored), in case email isn't set up or fails."""
    entry = {"at": datetime.now().isoformat(timespec="seconds"), "email": her_email, **plan}
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
