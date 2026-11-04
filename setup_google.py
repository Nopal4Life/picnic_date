"""Optional one-time setup for the Google Meet / Calendar invite. Run it yourself:
    python setup_google.py client_secret.json

(The confirmation emails don't need this, only the [email] app password in secrets.toml.)

1. In Google Cloud Console: create a project, enable the Google Calendar API, create an
   OAuth client ID of type "Desktop app", add yourself as a test user, download the JSON.
2. Run this script. A browser window asks you to approve calendar access.
3. It writes the [google] block into .streamlit/secrets.toml (git-ignored) and keeps your other settings.
"""
import sys
import tomllib
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from invite import SCOPES

SECRETS = Path(__file__).parent / ".streamlit" / "secrets.toml"

if len(sys.argv) != 2:
    sys.exit(__doc__)
existing = tomllib.loads(SECRETS.read_text()) if SECRETS.exists() else {}
picnic = existing.get("picnic", {})
his = input(f"Your email, the invite is created from this Google account [{picnic.get('his_email', '')}]: ").strip() or picnic.get("his_email", "")

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

if SECRETS.exists():
    SECRETS.rename(SECRETS.with_name("secrets.toml.bak"))  # keep the old one just in case
email = existing.get("email", {})
SECRETS.write_text(
    f'''[picnic]
his_email = "{his}"

[email]
username = "{email.get('username', '')}"
app_password = "{email.get('app_password', '')}"

[google]
client_id = "{creds.client_id}"
client_secret = "{creds.client_secret}"
refresh_token = "{creds.refresh_token}"
'''
)
SECRETS.chmod(0o600)
print(f"Saved {SECRETS}")
