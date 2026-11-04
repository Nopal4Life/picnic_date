"""Confirmation texts via Twilio's REST API (stdlib only, so there is nothing extra to install).

Needs a Twilio account (twilio.com): its Account SID, Auth Token and a Twilio phone number go in
.streamlit/secrets.toml under [twilio]; the two phone numbers go under [picnic]. A trial account can
only text numbers you have verified in the Twilio console.
"""
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from invite import details


def normalize_phone(raw):
    """'(415) 555-0134' -> '+14155550134'. 10 digits are assumed to be US; None if it can't be a number."""
    raw = (raw or "").strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def phones_from(secrets):
    """Normalized numbers of the two of us (blank/invalid ones dropped); [] if none are set up."""
    try:
        picnic = secrets["picnic"]
        return [p for p in (normalize_phone(picnic.get(k)) for k in ("her_phone", "his_phone")) if p]
    except Exception:  # no secrets file
        return []


def settings_from(secrets):
    """Twilio credentials + the phone numbers to text; None if automatic sms isn't set up."""
    try:
        twilio = secrets["twilio"]
        sid, token, sender = twilio["account_sid"], twilio["auth_token"], normalize_phone(twilio["from_number"])
    except Exception:  # no secrets file, or a key is missing
        return None
    phones = phones_from(secrets)
    return {"sid": sid, "token": token, "from": sender, "to": phones} if sid and token and sender and phones else None


def sms_link(numbers, body):
    """An sms: link that opens Messages (iPhone or Android) with the text already written.
    The `?&body=` form is the one iOS and Android both accept; with no numbers she just picks the contact."""
    return f"sms:{','.join(numbers)}?&body={urllib.parse.quote(body)}"


def confirmation_text(plan, meet=None):
    """Where / When / Bring (or her customizations instead), one per line."""
    lines = [f"{label}: {value}" for label, value in details(plan)]
    if meet:
        lines.append(f"Meet: {meet}")
    return "\n".join(lines)


def _post(url, sid, token, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError(json.loads(e.read() or b"{}").get("message", f"Twilio error {e.code}")) from None


def send_texts(cfg, body, post=_post):
    """Text `body` to every number. Returns the numbers that failed, with the reason."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['sid']}/Messages.json"
    failed = {}
    for number in cfg["to"]:
        try:
            post(url, cfg["sid"], cfg["token"], {"To": number, "From": cfg["from"], "Body": body})
        except Exception as e:
            failed[number] = str(e)
    return failed
