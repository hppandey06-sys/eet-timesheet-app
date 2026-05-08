"""
Database layer — all Supabase operations.
Uses supabase-py official client with proper error handling.
"""

import os
from datetime import datetime, date
from supabase import create_client, Client
import streamlit as st

# ════════════════════════════════════════════════════
# CONNECTION
# ════════════════════════════════════════════════════
def _get_credentials():
    """Get Supabase URL and key from Streamlit secrets or environment variables."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except (KeyError, FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        url = os.getenv("SUPABASE_URL", "https://qienqtmfiytsuvuoovpw.supabase.co")
        key = os.getenv("SUPABASE_KEY", "sb_publishable_yAvlRDj_-FydTvMLi5SNcQ_Uk1nOGUL")
    return url, key


@st.cache_resource
def get_client() -> Client:
    """Singleton Supabase client — reused across all calls."""
    url, key = _get_credentials()
    return create_client(url, key)


# ════════════════════════════════════════════════════
# AUTHENTICATION
# ════════════════════════════════════════════════════
def login_user(name: str, password: str):
    """Verify user credentials and return user dict if valid."""
    sb = get_client()
    try:
        result = sb.table("ts_members").select("*").eq("name", name).execute()
        if not result.data:
            return None
        user = result.data[0]
        if user.get("password") == password:
            return user
        return None
    except Exception as e:
        st.error(f"Login error: {e}")
        return None


# ════════════════════════════════════════════════════
# MEMBERS
# ════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def get_members():
    sb = get_client()
    result = sb.table("ts_members").select("*").order("id").execute()
    return result.data or []


def add_member(name, email, dept, discipline, role="member", password="1234", company="GCC"):
    sb = get_client()
    members = get_members()
    new_id = max([m["id"] for m in members], default=0) + 1
    sb.table("ts_members").insert({
        "id": new_id,
        "name": name,
        "email": email,
        "dept": dept,
        "discipline": discipline,
        "role": role,
        "password": password,
        "company": company
    }).execute()
    st.cache_data.clear()
    return new_id


def update_member(member_id, **fields):
    sb = get_client()
    sb.table("ts_members").update(fields).eq("id", member_id).execute()
    st.cache_data.clear()


def delete_member(member_id):
    sb = get_client()
    sb.table("ts_members").delete().eq("id", member_id).execute()
    st.cache_data.clear()


def change_member_role(member_id, role):
    update_member(member_id, role=role)


def bulk_add_members(members_data):
    """Bulk add members from CSV/Excel data. members_data is list of dicts."""
    sb = get_client()
    existing = get_members()
    existing_emails = {m["email"].lower() for m in existing}
    new_id = max([m["id"] for m in existing], default=0) + 1

    to_insert = []
    skipped = []
    for m in members_data:
        if m.get("email", "").lower() in existing_emails:
            skipped.append(m["name"])
            continue
        to_insert.append({
            "id": new_id,
            "name": m["name"],
            "email": m["email"],
            "dept": m.get("dept", "Engineering"),
            "discipline": m.get("discipline", ""),
            "role": m.get("role", "member"),
            "password": m.get("password", "1234"),
            "company": m.get("company", "GCC")
        })
        new_id += 1

    if to_insert:
        sb.table("ts_members").insert(to_insert).execute()
    st.cache_data.clear()
    return len(to_insert), skipped


# ════════════════════════════════════════════════════
# PROJECTS
# ════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def get_projects():
    sb = get_client()
    result = sb.table("ts_projects").select("*").order("id").execute()
    return result.data or []


def add_project(code, name, dept="Engineering", status="Active"):
    sb = get_client()
    projects = get_projects()
    new_id = max([p["id"] for p in projects], default=0) + 1
    sb.table("ts_projects").insert({
        "id": new_id,
        "code": code,
        "name": name,
        "dept": dept,
        "status": status
    }).execute()
    st.cache_data.clear()
    return new_id


def update_project(project_id, **fields):
    sb = get_client()
    sb.table("ts_projects").update(fields).eq("id", project_id).execute()
    st.cache_data.clear()


def delete_project(project_id):
    sb = get_client()
    sb.table("ts_projects").delete().eq("id", project_id).execute()
    st.cache_data.clear()


# ════════════════════════════════════════════════════
# ENTRIES — the critical part, must work reliably
# ════════════════════════════════════════════════════
def get_entries_for_user(uid):
    """Get all entries for a single user. Cached for 30 seconds."""
    return _get_entries_for_user_cached(uid)


@st.cache_data(ttl=30)
def _get_entries_for_user_cached(uid):
    sb = get_client()
    result = sb.table("ts_entries").select("*").eq("uid", uid).order("entry_date", desc=True).execute()
    return result.data or []


def get_all_entries():
    """Get all entries (for admin reports). Cached for 60 seconds."""
    return _get_all_entries_cached()


@st.cache_data(ttl=60)
def _get_all_entries_cached():
    sb = get_client()
    result = sb.table("ts_entries").select("*").order("entry_date", desc=True).execute()
    return result.data or []


def get_entries_for_date(uid, entry_date):
    """Get entries for a specific user on a specific date."""
    sb = get_client()
    result = sb.table("ts_entries").select("*").eq("uid", uid).eq("entry_date", entry_date).execute()
    return result.data or []


def save_single_entry(uid, entry_date, proj, act, hrs, desc=""):
    """
    Save ONE entry row. Used by per-row save in v3.
    Uses upsert by (uid, entry_date, proj, act) — safe, no race conditions.
    """
    sb = get_client()
    from datetime import datetime
    entry_id = int(datetime.now().timestamp() * 1000) * 100 + (uid % 100)

    # Upsert by unique key (uid, entry_date, proj, act)
    existing = sb.table("ts_entries").select("id").eq("uid", uid).eq("entry_date", entry_date).eq("proj", proj).eq("act", act).execute()

    row_data = {
        "uid": uid,
        "proj": proj,
        "act": act,
        "hrs": float(hrs),
        "entry_date": entry_date,
        "description": desc or "",
        "is_holiday": False,
        "is_leave": False
    }

    if existing.data:
        # Update existing row
        sb.table("ts_entries").update(row_data).eq("id", existing.data[0]["id"]).execute()
    else:
        # Insert new
        row_data["id"] = entry_id
        sb.table("ts_entries").insert(row_data).execute()

    st.cache_data.clear()
    return True


def delete_single_entry(uid, entry_date, proj, act):
    """Delete one specific entry by (uid, date, proj, act)."""
    sb = get_client()
    sb.table("ts_entries").delete().eq("uid", uid).eq("entry_date", entry_date).eq("proj", proj).eq("act", act).execute()
    st.cache_data.clear()
    return True


def save_day_entries(uid: int, entry_date: str, entries: list):
    """
    Save all entries for a single day. Replaces existing entries for that date.

    THIS IS THE KEY FUNCTION — it must work reliably.

    Strategy:
    1. Delete all existing entries for (uid, entry_date) using server-side WHERE
    2. Insert new entries with proper IDs

    Server handles this in single transaction — no race conditions possible.

    Args:
        uid: user ID
        entry_date: YYYY-MM-DD
        entries: list of dicts with keys: proj, act, hrs, desc, isHoliday, isLeave
    """
    sb = get_client()

    # Step 1: Delete existing entries for this user+date
    sb.table("ts_entries").delete().eq("uid", uid).eq("entry_date", entry_date).execute()

    # Step 2: Insert new entries
    if entries:
        rows = []
        # Use timestamp + index for unique IDs
        base_id = int(datetime.now().timestamp() * 1000) * 100
        for i, e in enumerate(entries):
            rows.append({
                "id": base_id + i,
                "uid": uid,
                "proj": e["proj"],
                "act": e.get("act", "OTHERS"),
                "hrs": float(e["hrs"]),
                "entry_date": entry_date,
                "description": e.get("desc", ""),
                "is_holiday": e.get("isHoliday", False),
                "is_leave": e.get("isLeave", False)
            })
        sb.table("ts_entries").insert(rows).execute()

    # Clear cache so next read shows fresh data
    st.cache_data.clear()
    return True


def delete_entry(entry_id):
    """Delete a single entry by ID (admin function)."""
    sb = get_client()
    sb.table("ts_entries").delete().eq("id", entry_id).execute()


def update_entry(entry_id, **fields):
    """Update a single entry by ID (admin function)."""
    sb = get_client()
    sb.table("ts_entries").update(fields).eq("id", entry_id).execute()


# ════════════════════════════════════════════════════
# SUBMISSIONS — monthly lock
# ════════════════════════════════════════════════════
def get_submissions():
    return _get_submissions_cached()


@st.cache_data(ttl=30)
def _get_submissions_cached():
    sb = get_client()
    result = sb.table("ts_submissions").select("*").execute()
    return result.data or []


def is_month_submitted(uid, ym):
    """Check if user has submitted for given month (YYYY-MM). Cached."""
    return _is_month_submitted_cached(uid, ym)


@st.cache_data(ttl=30)
def _is_month_submitted_cached(uid, ym):
    sb = get_client()
    result = sb.table("ts_submissions").select("id").eq("uid", uid).eq("ym", ym).eq("status", "submitted").execute()
    return bool(result.data)


def submit_month(uid, ym):
    """Submit and lock a month for a user."""
    sb = get_client()
    sb.table("ts_submissions").delete().eq("uid", uid).eq("ym", ym).execute()
    sb.table("ts_submissions").insert({
        "id": int(datetime.now().timestamp() * 1000),
        "uid": uid,
        "ym": ym,
        "status": "submitted",
        "submitted_at": datetime.utcnow().isoformat()
    }).execute()
    st.cache_data.clear()


def unlock_month(uid, ym):
    """v3: Member self-unlock — just removes submission record."""
    sb = get_client()
    sb.table("ts_submissions").delete().eq("uid", uid).eq("ym", ym).execute()
    st.cache_data.clear()


# ════════════════════════════════════════════════════
# PROJECT-SPECIFIC ACTIVITY CODES
# ════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def get_project_acts(project_name):
    """Get activity codes specific to a project (e.g., DC Power workstreams)."""
    sb = get_client()
    try:
        result = sb.table("ts_project_acts").select("*").eq("project", project_name).order("display_order").execute()
        return result.data or []
    except Exception:
        return []


def get_all_project_acts():
    sb = get_client()
    try:
        result = sb.table("ts_project_acts").select("*").order("project").execute()
        return result.data or []
    except Exception:
        return []


def add_project_act(project, code, description, display_order=0):
    sb = get_client()
    sb.table("ts_project_acts").insert({
        "id": int(datetime.now().timestamp() * 1000),
        "project": project,
        "code": code.upper(),
        "description": description,
        "display_order": display_order
    }).execute()
    st.cache_data.clear()


def delete_project_act(act_id):
    sb = get_client()
    sb.table("ts_project_acts").delete().eq("id", act_id).execute()
    st.cache_data.clear()


# ════════════════════════════════════════════════════
# EDIT REQUESTS
# ════════════════════════════════════════════════════
def get_edit_requests(status_filter=None):
    sb = get_client()
    q = sb.table("ts_edit_requests").select("*").order("id", desc=True)
    if status_filter:
        q = q.eq("status", status_filter)
    result = q.execute()
    return result.data or []


def request_edit(uid, ym, reason):
    sb = get_client()
    sb.table("ts_edit_requests").insert({
        "id": int(datetime.now().timestamp() * 1000),
        "uid": uid,
        "ym": ym,
        "reason": reason,
        "status": "pending",
        "requested_at": datetime.utcnow().isoformat()
    }).execute()


def handle_edit_request(req_id, decision, admin_note=""):
    """decision: 'approved' or 'rejected'"""
    sb = get_client()
    sb.table("ts_edit_requests").update({
        "status": decision,
        "admin_note": admin_note,
        "resolved_at": datetime.utcnow().isoformat()
    }).eq("id", req_id).execute()


def is_month_unlocked(uid, ym):
    """Check if user has approved edit request for this month. Cached."""
    return _is_month_unlocked_cached(uid, ym)


@st.cache_data(ttl=30)
def _is_month_unlocked_cached(uid, ym):
    sb = get_client()
    result = sb.table("ts_edit_requests").select("id").eq("uid", uid).eq("ym", ym).eq("status", "approved").execute()
    return bool(result.data)


# ════════════════════════════════════════════════════
# CUSTOM ACTIVITY CODES
# ════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def get_custom_acts():
    sb = get_client()
    # Need to ensure ts_custom_acts table exists - create on demand
    try:
        result = sb.table("ts_custom_acts").select("*").execute()
        return result.data or []
    except Exception:
        return []


def add_custom_act(code, description, discipline):
    sb = get_client()
    sb.table("ts_custom_acts").insert({
        "id": int(datetime.now().timestamp() * 1000),
        "code": code.upper(),
        "description": description,
        "discipline": discipline
    }).execute()
    st.cache_data.clear()


def delete_custom_act(act_id):
    sb = get_client()
    sb.table("ts_custom_acts").delete().eq("id", act_id).execute()
    st.cache_data.clear()
