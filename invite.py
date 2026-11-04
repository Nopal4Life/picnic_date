"""Create the picnic as a Google Calendar event with a Google Meet link.

Calendar emails both attendees the invitation (with the Meet link) when the event is created,
so this is the "reserve the time" email. Credentials come from .streamlit/secrets.toml;
run `python setup_google.py client_secret.json` once to create it.
"""
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")  # Mission Dolores Park
START_AT = time(14, 30)  # "This Saturday @ 2:30 pm"
EVENT_MINUTES = 120
DEFAULT_PLACE = "Mission Dolores Park"
WHEN_TEXT = "This Saturday @ 2:30 pm"
DEFAULT_BRING = "Your fav wine and your cute self ;P"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def next_saturday(now=None):
    """Start/end of the coming Saturday 2:30 pm (today if it's Saturday and not yet 2:30)."""
    now = now or datetime.now(TZ)
    days = (5 - now.weekday()) % 7
    start = datetime.combine(now.date() + timedelta(days=days), START_AT, tzinfo=TZ)
    if start <= now:
        start += timedelta(days=7)
    return start, start + timedelta(minutes=EVENT_MINUTES)


def settings_from(secrets):
    """My email + google credentials out of st.secrets; None if the calendar isn't set up."""
    try:
        google = secrets["google"]
        cfg = {
            "his_email": secrets["picnic"]["his_email"].strip(),
            "client_id": google["client_id"],
            "client_secret": google["client_secret"],
            "refresh_token": google["refresh_token"],
        }
    except Exception:  # no secrets file, or a key is missing
        return None
    return cfg if all(cfg.values()) else None


def details(plan):
    """The (label, value) rows shared by the page, the text, the invite and the .ics.
    Her customizations replace the default Bring line; where she only changed the place, Bring stays."""
    rows = [("Where", plan.get("where") or DEFAULT_PLACE), ("When", WHEN_TEXT)]
    custom = [(label, plan[key]) for label, key in (("Food", "food"), ("Drinks", "drinks"), ("Won't eat", "avoid")) if plan.get(key)]
    return rows + (custom or [("Bring", DEFAULT_BRING)])


def describe(plan):
    """Plain-text body for the invite."""
    return "\n".join(["Picnic date!"] + [f"{label}: {value}" for label, value in details(plan)])


def build_event(plan, emails, start, end):
    place = plan.get("where") or DEFAULT_PLACE
    return {
        "summary": "Picnic Date",
        "location": place,
        "description": describe(plan),
        "start": {"dateTime": start.isoformat(), "timeZone": str(TZ)},
        "end": {"dateTime": end.isoformat(), "timeZone": str(TZ)},
        "attendees": [{"email": e} for e in emails],
        "conferenceData": {
            "createRequest": {
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }


def calendar_service(cfg):
    from google.oauth2.credentials import Credentials  # imported here so the app runs without the libs
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def send_invite(plan, cfg, her_email, service=None, now=None):
    """Create the event and email both attendees (her, as typed in the app, and me). Returns the event's time, link and meet link."""
    start, end = next_saturday(now)
    event = build_event(plan, [her_email, cfg["his_email"]], start, end)
    service = service or calendar_service(cfg)
    created = (
        service.events()
        .insert(calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates="all")
        .execute()
    )
    return {"start": start, "meet": created.get("hangoutLink"), "link": created.get("htmlLink")}


def make_ics(plan, start, end, meet=None):
    """A .ics file: iPhones (and everything else) offer to add it to the calendar when it's opened."""

    def esc(text):
        return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    def utc(moment):
        return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def fold(line):  # RFC 5545: lines are at most 75 characters, continuations start with a space
        chunks = [line[:75]] + [line[i : i + 74] for i in range(75, len(line), 74)]
        return "\r\n ".join(chunks)

    description = describe(plan) + (f"\nGoogle Meet: {meet}" if meet else "")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Picnic Date//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@picnic-date",
        f"DTSTAMP:{utc(datetime.now(timezone.utc))}",
        f"DTSTART:{utc(start)}",
        f"DTEND:{utc(end)}",
        "SUMMARY:Picnic Date",
        f"LOCATION:{esc(plan.get('where') or DEFAULT_PLACE)}",
        f"DESCRIPTION:{esc(description)}",
        "BEGIN:VALARM",
        "TRIGGER:-PT1H",
        "ACTION:DISPLAY",
        "DESCRIPTION:Picnic Date",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
