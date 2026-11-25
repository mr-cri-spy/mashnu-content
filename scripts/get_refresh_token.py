"""One-time: run on YOUR machine. Opens Google's Allow screen, prints the refresh token.
Usage: python scripts/get_refresh_token.py path/to/client_secret.json"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    sys.argv[1], scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
cfg = json.load(open(sys.argv[1]))
c = cfg.get("installed") or cfg.get("web")
print("\nPut these in .env:\n")
print(f"YT_CLIENT_ID={c['client_id']}")
print(f"YT_CLIENT_SECRET={c['client_secret']}")
print(f"YT_REFRESH_TOKEN={creds.refresh_token}")
