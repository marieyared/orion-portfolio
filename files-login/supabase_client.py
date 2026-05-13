"""
supabase_client.py
──────────────────
Auth + DB helpers for Orion. All Supabase calls go through here.
"""

import os
from datetime import date
import streamlit as st
from supabase import create_client


def _client(access_token: str = "", refresh_token: str = ""):
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    client = create_client(url, key)
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
    return client


# ── Auth ───────────────────────────────────────────────────────────

def sign_up(email: str, password: str):
    return _client().auth.sign_up({"email": email, "password": password})


def sign_in(email: str, password: str):
    return _client().auth.sign_in_with_password({"email": email, "password": password})


# ── Date serialisation helpers ─────────────────────────────────────

def _entry_rows_to_json(rows: list) -> list:
    out = []
    for r in rows:
        row = dict(r)
        if isinstance(row.get("date"), date):
            row["date"] = row["date"].isoformat()
        out.append(row)
    return out


def _entry_rows_from_json(rows: list) -> list:
    out = []
    for r in rows:
        row = dict(r)
        if isinstance(row.get("date"), str):
            try:
                row["date"] = date.fromisoformat(row["date"])
            except (ValueError, TypeError):
                row["date"] = date.today()
        out.append(row)
    return out


def _bond_rows_to_json(rows: list) -> list:
    out = []
    for r in rows:
        row = dict(r)
        for field in ("maturity", "purchase_date"):
            if isinstance(row.get(field), date):
                row[field] = row[field].isoformat()
        out.append(row)
    return out


def _bond_rows_from_json(rows: list) -> list:
    out = []
    for r in rows:
        row = dict(r)
        for field in ("maturity", "purchase_date"):
            if isinstance(row.get(field), str):
                try:
                    row[field] = date.fromisoformat(row[field])
                except (ValueError, TypeError):
                    row[field] = date.today()
        out.append(row)
    return out


# ── Portfolio DB ───────────────────────────────────────────────────

def load_portfolio(access_token: str, refresh_token: str, user_id: str) -> dict | None:
    client = _client(access_token, refresh_token)
    result = client.table("portfolios").select("*").eq("user_id", user_id).execute()
    if not result.data:
        return None
    row = result.data[0]
    return {
        "entry_rows": _entry_rows_from_json(row.get("entry_rows") or []),
        "cash_rows":  row.get("cash_rows") or [],
        "bond_rows":  _bond_rows_from_json(row.get("bond_rows") or []),
    }


def save_portfolio(
    access_token: str,
    refresh_token: str,
    user_id: str,
    entry_rows: list,
    cash_rows: list,
    bond_rows: list,
):
    client = _client(access_token, refresh_token)
    payload = {
        "user_id":    user_id,
        "entry_rows": _entry_rows_to_json(entry_rows),
        "cash_rows":  cash_rows,
        "bond_rows":  _bond_rows_to_json(bond_rows),
    }
    existing = client.table("portfolios").select("id").eq("user_id", user_id).execute()
    if existing.data:
        client.table("portfolios").update(payload).eq("user_id", user_id).execute()
    else:
        client.table("portfolios").insert(payload).execute()


def save_snapshot(
    access_token: str,
    refresh_token: str,
    user_id: str,
    total_value: float,
    total_paid: float,
):
    client = _client(access_token, refresh_token)
    client.table("portfolio_snapshots").upsert(
        {
            "user_id":     user_id,
            "total_value": total_value,
            "total_paid":  total_paid,
        },
        on_conflict="user_id,snapped_at",
    ).execute()
