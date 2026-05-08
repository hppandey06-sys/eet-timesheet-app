"""
My Timesheet page — v3
NEW: Per-row save with color-coded buttons.
NEW: Member self-unlock (no admin approval needed).
NEW: Project-specific activity codes.
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

    # Week navigator
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

    week_dates = get_week_dates(st.session_state.week_offset)
    all_entries = db.get_entries_for_user(user["id"])
    projects = db.get_projects()
    custom_acts = db.get_custom_acts()

    visible_months = set(d[:7] for d in week_dates)
    submission_status = {ym: db.is_month_submitted(user["id"], ym) for ym in visible_months}

    week_total = sum(e["hrs"] for e in all_entries if e["entry_date"] in week_dates)

    # KPIs
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

    for d in week_dates:
        show_day_card(user, d, all_entries, projects, custom_acts, submission_status)

    show_submit_banner(user, week_dates, all_entries)


def show_day_card(user, d, all_entries, projects, custom_acts, submission_status):
    day_name = get_day_name(d)
    day_short = format_date_short(d)
    day_entries = [e for e in all_entries if e["entry_date"] == d]
    day_total = sum(e["hrs"] for e in day_entries)

    ym = d[:7]
    is_locked = submission_status.get(ym, False)

    if is_weekend(d):
        st.markdown(f"""<div class="day-card day-card-locked" style="opacity:0.6">
            <strong>{day_name} · {day_short}</strong>
            <span style="float:right;color:#605e5c;font-size:12px">Weekend — not editable</span>
        </div>""", unsafe_allow_html=True)
        return

    if is_holiday(d):
        holiday_name = get_holiday_name(d)
        st.markdown(f"""<div class="day-card day-card-locked" style="background:#fff4ce;border-color:#ffd335">
            <strong>{day_name} · {day_short}</strong>
            <span class="status-pill status-pending" style="margin-left:8px">🎉 {holiday_name}</span>
            <span style="float:right;color:#7a5700;font-size:12px">Auto-filled · 8 hrs</span>
        </div>""", unsafe_allow_html=True)
        return

    if is_locked:
        with st.expander(f"🔒 {day_name} · {day_short} — {day_total:.1f} hrs (Locked)", expanded=False):
            for e in day_entries:
                st.markdown(f"- **{e['proj']}** · {e['act']} · **{e['hrs']} hrs** · {e.get('description', '—')}")
        return

    # Default to expanded for current week and recent weeks
    expanded = (st.session_state.week_offset >= -1)
    with st.expander(f"{day_name} · {day_short}  —  {day_total:.1f} hrs", expanded=expanded):
        show_day_entries_form(user, d, day_entries, all_entries, projects, custom_acts)


def show_day_entries_form(user, d, day_entries, all_entries, projects, custom_acts):
    """Show editable form with PER-ROW save."""
    project_options = [p["name"] for p in projects if p.get("status") == "Active"]
    if not project_options:
        project_options = [p["name"] for p in projects]

    draft_key = f"draft_{d}_v3"

    if draft_key not in st.session_state:
        if day_entries:
            st.session_state[draft_key] = [
                {
                    "proj": e["proj"], "act": e["act"], "hrs": float(e["hrs"]),
                    "desc": e.get("description", ""),
                    "saved": True,
                    "saved_proj": e["proj"], "saved_act": e["act"],
                    "saved_hrs": float(e["hrs"]), "saved_desc": e.get("description", ""),
                }
                for e in day_entries
            ]
        else:
            last_entry = get_last_saved_entry(user["id"], all_entries)
            if last_entry:
                st.session_state[draft_key] = [{
                    "proj": last_entry["proj"], "act": last_entry["act"],
                    "hrs": 8.0, "desc": "", "saved": False,
                }]
            else:
                st.session_state[draft_key] = [{
                    "proj": project_options[0] if project_options else "",
                    "act": "OTHERS", "hrs": 8.0, "desc": "", "saved": False,
                }]

    draft = st.session_state[draft_key]

    # Header row
    cols = st.columns([2.5, 2.5, 0.9, 2.5, 1.3, 0.4])
    with cols[0]: st.caption("**Project**")
    with cols[1]: st.caption("**Activity**")
    with cols[2]: st.caption("**Hours**")
    with cols[3]: st.caption("**Description**")
    with cols[4]: st.caption("**Status**")
    with cols[5]: st.caption("")

    rows_to_delete = []

    for i, entry in enumerate(draft):
        proj = entry.get("proj", "")
        activities = get_activities_for_discipline_and_project(
            user.get("discipline"), proj, custom_acts
        )
        activity_options = [f"{code} — {desc}" for code, desc in activities]
        activity_codes = [code for code, desc in activities]

        cols = st.columns([2.5, 2.5, 0.9, 2.5, 1.3, 0.4])

        with cols[0]:
            try:
                idx = project_options.index(proj) if proj in project_options else 0
            except ValueError:
                idx = 0
            new_proj = st.selectbox(
                " ", project_options, index=idx,
                key=f"{draft_key}_proj_{i}", label_visibility="collapsed"
            )

        with cols[1]:
            try:
                act_idx = activity_codes.index(entry["act"]) if entry["act"] in activity_codes else 0
            except ValueError:
                act_idx = 0
            act_label = st.selectbox(
                " ", activity_options, index=act_idx,
                key=f"{draft_key}_act_{i}", label_visibility="collapsed"
            )
            new_act = activity_codes[activity_options.index(act_label)] if act_label in activity_options else "OTHERS"

        with cols[2]:
            new_hrs = st.number_input(
                " ", min_value=0.0, max_value=float(MAX_DAY_HRS),
                value=float(entry["hrs"]), step=0.5,
                key=f"{draft_key}_hrs_{i}", label_visibility="collapsed"
            )

        with cols[3]:
            new_desc = st.text_input(
                " ", value=entry.get("desc", ""),
                placeholder="What did you work on?",
                key=f"{draft_key}_desc_{i}", label_visibility="collapsed"
            )

        # Update draft entry with current values
        entry["proj"] = new_proj
        entry["act"] = new_act
        entry["hrs"] = new_hrs
        entry["desc"] = new_desc

        is_saved = entry.get("saved", False)
        is_changed = is_saved and (
            entry.get("saved_proj") != new_proj
            or entry.get("saved_act") != new_act
            or entry.get("saved_hrs") != new_hrs
            or entry.get("saved_desc") != new_desc
        )

        with cols[4]:
            if is_saved and not is_changed:
                st.markdown(
                    "<div style='padding:6px 0;text-align:center;background:#dff6dd;color:#107c10;"
                    "border-radius:6px;font-size:11px;font-weight:600;border:1px solid #107c10'>✓ Saved</div>",
                    unsafe_allow_html=True
                )
            else:
                if st.button("💾 Save", key=f"{draft_key}_save_{i}", type="primary",
                             use_container_width=True):
                    save_single_row(user, d, entry, draft_key, i)

        with cols[5]:
            if st.button("✕", key=f"{draft_key}_del_{i}", help="Remove this row"):
                rows_to_delete.append(i)

    # Process deletions after iteration
    if rows_to_delete:
        for i in sorted(rows_to_delete, reverse=True):
            entry = draft[i]
            if entry.get("saved"):
                try:
                    db.delete_single_entry(user["id"], d, entry["saved_proj"], entry["saved_act"])
                except Exception as e:
                    st.error(f"Delete failed: {e}")
            draft.pop(i)
        st.session_state[draft_key] = draft
        st.rerun()

    st.session_state[draft_key] = draft

    # Day total + add row
    total = sum(e["hrs"] for e in draft)
    col1, col2 = st.columns([3, 1])
    with col1:
        color = "#d13438" if total > MAX_DAY_HRS else "#107c10" if total > 0 else "#605e5c"
        st.markdown(f"<div style='padding-top:8px;font-weight:600;color:{color}'>"
                    f"Day total: {total:.1f} / {MAX_DAY_HRS} hrs</div>",
                    unsafe_allow_html=True)
    with col2:
        if len(draft) < 4:
            if st.button("+ Add Row", key=f"{draft_key}_add", use_container_width=True):
                last_entry = get_last_saved_entry(user["id"], all_entries)
                new_proj = last_entry["proj"] if last_entry else (project_options[0] if project_options else "")
                new_act = last_entry["act"] if last_entry else "OTHERS"
                draft.append({"proj": new_proj, "act": new_act, "hrs": 0.0,
                              "desc": "", "saved": False})
                st.session_state[draft_key] = draft
                st.rerun()


def save_single_row(user, d, entry, draft_key, row_idx):
    if entry["hrs"] <= 0:
        st.error("Hours must be > 0")
        return

    draft = st.session_state[draft_key]
    duplicates = [
        i for i, e in enumerate(draft)
        if i != row_idx and e["proj"] == entry["proj"] and e["act"] == entry["act"]
    ]
    if duplicates:
        st.error("Duplicate Project+Activity in this day. Use a different combination.")
        return

    try:
        with st.spinner("Saving..."):
            if entry.get("saved") and (
                entry.get("saved_proj") != entry["proj"]
                or entry.get("saved_act") != entry["act"]
            ):
                try:
                    db.delete_single_entry(user["id"], d, entry["saved_proj"], entry["saved_act"])
                except Exception:
                    pass

            db.save_single_entry(
                user["id"], d, entry["proj"], entry["act"],
                entry["hrs"], entry["desc"]
            )

        entry["saved"] = True
        entry["saved_proj"] = entry["proj"]
        entry["saved_act"] = entry["act"]
        entry["saved_hrs"] = entry["hrs"]
        entry["saved_desc"] = entry["desc"]
        draft[row_idx] = entry
        st.session_state[draft_key] = draft

        st.success("✅ Saved!")
        st.rerun()
    except Exception as e:
        st.error(f"Save failed: {e}")


def get_last_saved_entry(uid, all_entries):
    work_entries = [e for e in all_entries if not e.get("is_holiday") and not e.get("is_leave")]
    if not work_entries:
        return None
    work_entries.sort(key=lambda e: e["entry_date"], reverse=True)
    return work_entries[0]


def get_activities_for_discipline_and_project(discipline, project, custom_acts=None):
    result = []
    project_acts = db.get_project_acts(project) if project else []
    for pa in project_acts:
        result.append((pa["code"], pa["description"]))
    builtin = get_activities_for_discipline(discipline, custom_acts)
    for code, desc in builtin:
        if code not in [r[0] for r in result]:
            result.append((code, desc))
    if not result:
        result = [("OTHERS", "Others")]
    return result


def show_submit_banner(user, week_dates, all_entries):
    """NEW: member self-unlock — no admin approval."""
    ym = week_dates[3][:7]
    month_label = get_month_label(ym)

    month_entries = [e for e in all_entries if e["entry_date"].startswith(ym)]
    if not month_entries:
        return

    is_submitted = db.is_month_submitted(user["id"], ym)

    st.markdown("<br>", unsafe_allow_html=True)

    if is_submitted:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success(f"🔒 **{month_label} — Submitted and Locked**  ·  Click 'Unlock' to make changes.")
        with col2:
            if st.button(f"🔓 Unlock {month_label}", use_container_width=True):
                db.unlock_month(user["id"], ym)
                st.success(f"✅ {month_label} unlocked.")
                st.rerun()
    else:
        total_hrs = sum(e["hrs"] for e in month_entries)
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📤 **{month_label} — Open**  ·  {len(month_entries)} entries · {total_hrs:.1f} hrs")
        with col2:
            confirm_key = f"confirm_submit_{ym}"
            if st.button(f"📤 Submit {month_label}", type="primary", use_container_width=True):
                if st.session_state.get(confirm_key):
                    db.submit_month(user["id"], ym)
                    st.success(f"✅ {month_label} submitted!")
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
                else:
                    st.session_state[confirm_key] = True
                    st.warning("Click Submit again to confirm.")
