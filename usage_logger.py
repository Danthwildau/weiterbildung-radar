"""
usage_logger.py — DIAGNOSTIC VERSION (temporary).
Same behaviour as the normal logger, but instead of failing silently it
shows the exact Supabase response in the Streamlit UI so we can see what's
going wrong. REVERT to the silent version once logging is confirmed working.
"""
import os
import csv
import uuid
import datetime
from pathlib import Path

import requests

try:
    import streamlit as st
except Exception:
    st = None

ALLOWED_EVENTS = {
    "app_open", "search_run", "phase2_view", "phase3_view", "export_click",
}

_BACKEND      = os.getenv("USAGE_BACKEND", "supabase").lower()
_SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
_CSV_PATH     = Path(os.getenv("USAGE_CSV_PATH", "usage_events.csv"))


def _diag(msg):
    """Show a diagnostic message in the app (and never crash if st is absent)."""
    if st is not None:
        st.warning(f"[usage_logger] {msg}")
    else:
        print(f"[usage_logger] {msg}")


def _today():
    return datetime.date.today().isoformat()


def _clean(value, maxlen=120):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:maxlen]


def _log_supabase(row):
    # Show what config the running app actually sees.
    if not _SUPABASE_URL:
        _diag("SUPABASE_URL is EMPTY in the running app.")
        return False
    if not _SUPABASE_KEY:
        _diag("SUPABASE_ANON_KEY is EMPTY in the running app.")
        return False
    # Show a masked view so we can confirm the values are present & shaped right.
    _diag(f"URL seen by app: {_SUPABASE_URL}")
    _diag(f"Key length seen by app: {len(_SUPABASE_KEY)} chars, "
          f"starts '{_SUPABASE_KEY[:6]}...'")
    endpoint = f"{_SUPABASE_URL}/rest/v1/usage_events"
    try:
        resp = requests.post(
            endpoint,
            headers={
                "apikey": _SUPABASE_KEY,
                "Authorization": f"Bearer {_SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=row,
            timeout=6,
        )
        if resp.status_code in (200, 201, 204):
            _diag(f"SUCCESS — Supabase accepted the insert (HTTP {resp.status_code}).")
            return True
        # The important line: show the exact status + body Supabase returned.
        _diag(f"FAILED — HTTP {resp.status_code} at {endpoint}\n"
              f"Response body: {resp.text[:500]}")
        return False
    except Exception as e:
        _diag(f"EXCEPTION talking to Supabase at {endpoint}: {type(e).__name__}: {e}")
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
    except Exception as e:
        _diag(f"CSV write failed: {e}")
        return False


def get_session_id(st_session_state):
    if "_usage_sid" not in st_session_state:
        st_session_state["_usage_sid"] = uuid.uuid4().hex[:12]
    return st_session_state["_usage_sid"]


def log_event(event_type, abschluss=None, wissensgebiet=None, session_id=None):
    if event_type not in ALLOWED_EVENTS:
        _diag(f"Event '{event_type}' not in allow-list — ignored.")
        return False
    _diag(f"Backend in use: {_BACKEND!r}")
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
