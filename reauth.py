"""Re-authenticate the bot's YouTube OAuth and produce a fresh token.json.

Run this when the GitHub Actions log shows:
    google.auth.exceptions.RefreshError: invalid_grant: Token has been expired or revoked

What it does:
  1. Deletes any stale token.json in this folder.
  2. Opens your browser so you can sign in with the YouTube channel's Google
     account and grant access again.
  3. Writes a fresh token.json next to this file.
  4. Prints the JSON contents so you can paste them into the GitHub secret
     GOOGLE_TOKEN_JSON (Settings -> Secrets and variables -> Actions).

Usage:
    python reauth.py
"""
from __future__ import annotations

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
ROOT = Path(__file__).resolve().parent
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN_PATH = ROOT / "token.json"


def main() -> None:
    if not CLIENT_SECRET.exists():
        raise SystemExit(f"client_secret.json not found at {CLIENT_SECRET}")

    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        print(f"[reauth] removed stale {TOKEN_PATH.name}")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    print(f"\n[reauth] wrote fresh token to {TOKEN_PATH}")
    print("\n=== COPY THE BLOCK BELOW INTO GITHUB SECRET 'GOOGLE_TOKEN_JSON' ===\n")
    print(TOKEN_PATH.read_text(encoding="utf-8"))
    print("\n=== END ===\n")
    print("After updating the secret, re-run a workflow at:")
    print("https://github.com/thebmstudios/shorts-bot/actions")


if __name__ == "__main__":
    main()
