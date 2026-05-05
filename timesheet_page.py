"""
My Timesheet page — weekly grid with day-by-day save.
"""

import streamlit as st
from datetime import date, timedelta
import db
from constants import (
    MAX_DAY_HRS, format_date_short, format_date_full, get_week_dates,
    get_day_name, is_weekend, is_holiday, get_holiday_name,
    get_activities_for_discipline, get_month_label
)


def show():
    user = st.session_state.user
    week_offset = st.session_state.get("week_offset", 0)

    # ── Week navigator ──
    col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
    with col1:
        if st.button("◀ Previous", use_container_width=True):
            st.session_state.week_offset = week_offset - 1
            st.rerun()
    with col2:
        week_dates = get_week_dates(week_offset)
        label = f"{format_date_full(week_dates[0])}  —  {format_date_full(week_dates[6])}"
        st.markdown(f"<div style='text-align:center;padding:6px;font-weight:600;color:#6264a7;font-size:13px'>{label}</div>",
                    unsafe_allow_html=True)
    with col3:
        if st.button("Next ▶", use_container_width=True):
            st.session_state.week_offset = week_offset + 1
            st.rerun()
    with col4:
        if st.button("Today", use_container_width=True):
            st.session_state.week_offset = 0
            st.rerun()

    # ── Load this week's existing entries ──
    week_dates = get_week_dates(st.session_state.week_offset)
    all_entries = db.get_entries_for_user(user["id"])

    # Calculate week total
    week_total = sum(
        e["hrs"] for e in all_entries
        if e["entry_date"] in week_dates
    )

    # ── KPIs ──
    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{week_total:.1f}</div>
                    <div class="kpi-label">Hours this week</div></div>""", unsafe_allow_html=True)
    with cols[1]:
        days_filled = len(set(e["entry_date"] for e in all_entries if e["entry_date"] in week_dates))
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{days_filled}</div>
                    <div class="kpi-label">Days filled</div></div>""", unsafe_allow_html=True)
    with cols[2]:
        target = 40
        remaining = max(0, target - week_total)
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{remaining:.1f}</div>
                    <div class="kpi-label">Remaining (40h)</div></div>""", unsafe_allow_html=True)
    with cols[3]:
        cur_month = get_month_label(week_dates[3][:7])
        st.markdown(f"""<div class="kpi"><div class="kpi-value" style="font-size:14px">{cur_month}</div>
                    <div class="kpi-label">Current month</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Daily entries ──
    for d in week_dates:
        show_day_card(user, d, all_entries)

    # ── Submit month banner ──
    show_submit_banner(user, week_dates)


def show_day_card(user, d, all_entries):
    """Show a single day's entry card."""
    day_name = get_day_name(d)
    day_short = format_date_short(d)
    day_entries = [e for e in all_entries if e["entry_date"] == d]
    day_total = sum(e["hrs"] for e in day_entries)

    ym = d[:7]
    is_locked = db.is_month_submitted(user["id"], ym) and not db.is_month_unlocked(user["id"], ym)

    with st.container():
        # Weekend
        if is_weekend(d):
            st.markdown(f"""<div class="day-card day-card-locked" style="opacity:0.6">
                <strong>{day_name} · {day_short}</strong>
                <span style="float:right;color:#605e5c;font-size:12px">Weekend — not editable</span>
            </div>""", unsafe_allow_html=True)
            return

        # Holiday
        if is_holiday(d):
            holiday_name = get_holiday_name(d)
            st.markdown(f"""<div class="day-card day-card-locked" style="background:#fff4ce;border-color:#ffd335">
                <strong>{day_name} · {day_short}</strong>
                <span class="status-pill status-pending" style="margin-left:8px">🎉 {holiday_name}</span>
                <span style="float:right;color:#7a5700;font-size:12px">Auto-filled · 8 hrs</span>
            </div>""", unsafe_allow_html=True)
            return

        # Locked
        if is_locked:
            with st.expander(f"🔒 {day_name} · {day_short} — {day_total:.1f} hrs (Locked)", expanded=False):
                for e in day_entries:
                    st.markdown(f"- **{e['proj']}** · {e['act']} · **{e['hrs']} hrs** · {e.get('description', '—')}")
            return

        # Editable day
        status_pill = ""
        card_class = "day-card"
        if day_entries:
            status_pill = '<span class="status-pill status-saved">✓ Saved</span>'
            card_class = "day-card day-card-saved"

        with st.expander(f"{day_name} · {day_short}  —  {day_total:.1f} hrs", expanded=(day_total == 0)):
            show_day_entries_form(user, d, day_entries, all_entries)


def show_day_entries_form(user, d, day_entries, all_entries):
    """Show editable form for a day's entries."""
    projects = db.get_projects()
    project_options = [p["name"] for p in projects if p.get("status") == "Active"]
    if not project_options:
        project_options = [p["name"] for p in projects]

    custom_acts = db.get_custom_acts()
    activities = get_activities_for_discipline(user.get("discipline"), custom_acts)
    activity_options = [f"{code} — {desc}" for code, desc in activities]
    activity_codes = [code for code, desc in activities]

    # Initialize draft from existing entries
    draft_key = f"draft_{d}"
    if draft_key not in st.session_state:
        if day_entries:
            st.session_state[draft_key] = [
                {
                    "proj": e["proj"],
                    "act": e["act"],
                    "hrs": float(e["hrs"]),
                    "desc": e.get("description", "")
                }
                for e in day_entries
            ]
        else:
            # Pre-fill from last saved day
            last_entry = get_last_saved_entry(user["id"], all_entries)
            if last_entry:
                st.session_state[draft_key] = [{
                    "proj": last_entry["proj"],
                    "act": last_entry["act"],
                    "hrs": 8.0,
                    "desc": ""
                }]
                st.info(f"💡 Pre-filled from last saved day ({format_date_short(last_entry['entry_date'])})")
            else:
                st.session_state[draft_key] = [{
                    "proj": project_options[0] if project_options else "",
                    "act": activity_codes[0] if activity_codes else "OTHERS",
                    "hrs": 8.0,
                    "desc": ""
                }]

    draft = st.session_state[draft_key]

    # Show entries
    new_draft = []
    for i, entry in enumerate(draft):
        cols = st.columns([3, 3, 1, 3, 0.5])
        with cols[0]:
            current_proj = entry["proj"] if entry["proj"] in project_options else (project_options[0] if project_options else "")
            try:
                idx = project_options.index(current_proj)
            except ValueError:
                idx = 0
            proj = st.selectbox(
                "Project" if i == 0 else " ",
                project_options,
                key=f"{draft_key}_proj_{i}",
                index=idx,
                label_visibility="visible" if i == 0 else "collapsed"
            )
        with cols[1]:
            current_act = entry.get("act", "OTHERS")
            try:
                act_idx = activity_codes.index(current_act)
            except ValueError:
                act_idx = 0
            act_label = st.selectbox(
                "Activity" if i == 0 else " ",
                activity_options,
                key=f"{draft_key}_act_{i}",
                index=act_idx,
                label_visibility="visible" if i == 0 else "collapsed"
            )
            act_code = activity_codes[activity_options.index(act_label)] if act_label in activity_options else "OTHERS"
        with cols[2]:
            hrs = st.number_input(
                "Hours" if i == 0 else " ",
                min_value=0.0,
                max_value=float(MAX_DAY_HRS),
                value=float(entry["hrs"]),
                step=0.5,
                key=f"{draft_key}_hrs_{i}",
                label_visibility="visible" if i == 0 else "collapsed"
            )
        with cols[3]:
            desc = st.text_input(
                "Description (optional)" if i == 0 else " ",
                value=entry.get("desc", ""),
                key=f"{draft_key}_desc_{i}",
                placeholder="What did you work on?",
                label_visibility="visible" if i == 0 else "collapsed"
            )
        with cols[4]:
            st.markdown("<br>" if i == 0 else "", unsafe_allow_html=True)
            if st.button("✕", key=f"{draft_key}_del_{i}", help="Remove this row"):
                draft.pop(i)
                st.session_state[draft_key] = draft
                st.rerun()

        new_draft.append({"proj": proj, "act": act_code, "hrs": hrs, "desc": desc})

    st.session_state[draft_key] = new_draft

    # Total + buttons
    total = sum(e["hrs"] for e in new_draft)
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        color = "#d13438" if total > MAX_DAY_HRS else "#107c10" if total > 0 else "#605e5c"
        st.markdown(f"<div style='padding-top:8px;font-weight:600;color:{color}'>Total: {total:.1f} / {MAX_DAY_HRS} hrs</div>",
                    unsafe_allow_html=True)
    with col2:
        if len(new_draft) < 4:
            if st.button("+ Add row", key=f"{draft_key}_add", use_container_width=True):
                last_entry = get_last_saved_entry(user["id"], all_entries)
                new_proj = last_entry["proj"] if last_entry else (project_options[0] if project_options else "")
                new_act = last_entry["act"] if last_entry else (activity_codes[0] if activity_codes else "OTHERS")
                new_draft.append({"proj": new_proj, "act": new_act, "hrs": 0.0, "desc": ""})
                st.session_state[draft_key] = new_draft
                st.rerun()
    with col3:
        if st.button("↶ Reset", key=f"{draft_key}_reset", use_container_width=True):
            del st.session_state[draft_key]
            st.rerun()
    with col4:
        save_disabled = total > MAX_DAY_HRS
        if st.button("💾 Save", key=f"{draft_key}_save", type="primary",
                     use_container_width=True, disabled=save_disabled):
            save_day(user, d, new_draft)


def save_day(user, d, entries):
    """Save the day's entries to Supabase."""
    # Filter out zero-hour entries
    valid_entries = [e for e in entries if e["hrs"] > 0]

    try:
        with st.spinner("Saving..."):
            db.save_day_entries(user["id"], d, valid_entries)
        st.success(f"✅ {get_day_name(d)} saved!")
        # Clear draft so next render reads fresh from DB
        draft_key = f"draft_{d}"
        if draft_key in st.session_state:
            del st.session_state[draft_key]
        st.rerun()
    except Exception as e:
        st.error(f"Save failed: {e}")


def get_last_saved_entry(uid, all_entries):
    """Find the most recent saved entry for pre-fill."""
    work_entries = [e for e in all_entries if not e.get("is_holiday") and not e.get("is_leave")]
    if not work_entries:
        return None
    work_entries.sort(key=lambda e: e["entry_date"], reverse=True)
    return work_entries[0]


def show_submit_banner(user, week_dates):
    """Show monthly submit/lock banner."""
    ym = week_dates[3][:7]
    month_label = get_month_label(ym)

    # Get user entries for this month
    all_entries = db.get_entries_for_user(user["id"])
    month_entries = [e for e in all_entries if e["entry_date"].startswith(ym)]

    if not month_entries:
        return

    is_submitted = db.is_month_submitted(user["id"], ym)
    is_unlocked = db.is_month_unlocked(user["id"], ym)

    st.markdown("<br>", unsafe_allow_html=True)

    if is_submitted and not is_unlocked:
        st.success(f"✅ **{month_label} — Submitted**  ·  Your timesheet for this month is locked.")
        if st.button("✏️ Request Edit Access"):
            show_edit_request_modal(user, ym)
    elif is_submitted and is_unlocked:
        st.warning(f"🔓 **{month_label} — Edit Approved**  ·  Make changes and re-submit.")
        if st.button(f"📤 Re-Submit {month_label}", type="primary"):
            db.submit_month(user["id"], ym)
            st.success(f"✅ {month_label} re-submitted!")
            st.rerun()
    else:
        total_hrs = sum(e["hrs"] for e in month_entries)
        st.info(f"📤 **Ready to submit {month_label}**  ·  {len(month_entries)} entries · {total_hrs:.1f} hrs")
        if st.button(f"📤 Submit {month_label}", type="primary"):
            if st.session_state.get("confirm_submit") == ym:
                db.submit_month(user["id"], ym)
                st.success(f"✅ {month_label} submitted and locked!")
                st.session_state.pop("confirm_submit", None)
                st.rerun()
            else:
                st.session_state.confirm_submit = ym
                st.warning("Click Submit again to confirm. Once submitted, you cannot edit without admin approval.")


def show_edit_request_modal(user, ym):
    """Show modal to request edit access."""
    with st.form(f"edit_request_{ym}"):
        st.write(f"Request edit access for **{get_month_label(ym)}**")
        reason = st.text_area("Reason for edit request", placeholder="Please explain why you need to edit...")
        submit = st.form_submit_button("Send Request", type="primary")
        if submit:
            if not reason.strip():
                st.error("Please provide a reason")
            else:
                db.request_edit(user["id"], ym, reason.strip())
                st.success("✅ Edit request sent to admin!")
                st.rerun()
