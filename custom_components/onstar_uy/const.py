"""Defaults shared by the mobile application, separate from account data."""
import json
from pathlib import Path

APP_DEFAULTS = json.loads(Path(__file__).with_name("app_client.json").read_text(encoding="utf-8"))
APP_CLIENT_ID = APP_DEFAULTS["client_id"]
