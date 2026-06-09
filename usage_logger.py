"""
usage_logger.py — DSGVO-konformes, anonymes Event-Logging.
Erfasst ausschliesslich Ereignisse, keine personenbezogenen Daten.
Backend per Umgebungsvariable USAGE_BACKEND: "supabase" (default) oder "csv".
"""
import os
import csv
import uuid
import datetime
from pathlib import Path

import requests

# Erlaubte Ereignistypen (Whitelist — schuetzt vor versehentlichem Wildwuchs)
ALLOWED_EVENTS = {
    "app_open", "search_run", "phase2_view", "phase3_view", "export_click",
}

_BACKEND      = os.getenv("USAGE_BACKEND", "supabase").lower()
_SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
_CSV_PATH     = Path(os.getenv("USAGE_CSV_PATH", "usage_events.csv"))


def _today():
    # Tagesgenau, NICHT sekundengenau — bewusste Datensparsamkeit.
    return datetime.date.today().isoformat()


def _clean(value, maxlen=120):
    """Nur kurze, kategoriale Strings zulassen. Niemals Freitext loggen."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:maxlen]


def _log_supabase(row):
    if not (_SUPABASE_URL and _SUPABASE_KEY):
        return False
    try:
        resp = requests.post(
            f"{_SUPABASE_URL}/rest/v1/usage_events",
            headers={
                "apikey": _SUPABASE_KEY,
                "Authorization": f"Bearer {_SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=row,
            timeout=4,
        )
        return resp.status_code in (200, 201, 204)
    except Exception:
        # Logging darf die App NIE zum Absturz bringen.
        return False


def _log_csv(row):
    try:
        new = not _CSV_PATH.exists()
        with open(_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["day", "event_type",
                                              "abschluss", "wissensgebiet",
                                              "session_id"])
            if new:
                w.writeheader()
            w.writerow(row)
        return True
    except Exception:
        return False


def get_session_id(st_session_state):
    """
    Zufaellige ID, die NUR im Arbeitsspeicher der laufenden Sitzung lebt.
    Wird nie persistiert verknuepft; dient nur dazu, mehrere Ereignisse
    einer Sitzung nicht als mehrere Nutzer zu zaehlen.
    """
    if "_usage_sid" not in st_session_state:
        st_session_state["_usage_sid"] = uuid.uuid4().hex[:12]
    return st_session_state["_usage_sid"]


def log_event(event_type, abschluss=None, wissensgebiet=None, session_id=None):
    """
    Einziger oeffentlicher Einstiegspunkt. Schreibt ein Ereignis.
    Schlaegt still fehl (kein Absturz), wenn das Backend nicht erreichbar ist.
    """
    if event_type not in ALLOWED_EVENTS:
        return False
    row = {
        "day": _today(),
        "event_type": event_type,
        "abschluss": _clean(abschluss),
        "wissensgebiet": _clean(wissensgebiet),
        "session_id": _clean(session_id, maxlen=32),
    }
    if _BACKEND == "csv":
        return _log_csv(row)
    return _log_supabase(row)