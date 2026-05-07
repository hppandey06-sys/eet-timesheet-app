"""
Team View — see all team members' timesheet entries.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import db
from constants import format_date_short, get_week_dates, DEPT_DISCIPLINES, COMPANIES


def show():
    user = st.session_state.user
    is_admin = user["role"] == "admin"

    st.markdown("### 👥 Team View")

    # Filters - row 1
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        period = st.selectbox("Period", ["This Week", "Last Week", "This Month", "Last Month", "Custom"])

    if period == "Custom":
        with col2:
            from_date = st.date_input("From", value=date.today() - timedelta(days=7))
        with col3:
            to_date = st.date_input("To", value=date.today())
    else:
        if period == "This Week":
            week = get_week_dates(0)
            from_date, to_date = date.fromisoformat(week[0]), date.fromisoformat(week[6])
        elif period == "Last Week":
            week = get_week_dates(-1)
            from_date, to_date = date.fromisoformat(week[0]), date.fromisoformat(week[6])
        elif period == "This Month":
            today = date.today()
            from_date = date(today.year, today.month, 1)
            to_date = today
        elif period == "Last Month":
            today = date.today()
            first = date(today.year, today.month, 1)
            to_date = first - timedelta(days=1)
            from_date = date(to_date.year, to_date.month, 1)

    members = db.get_members()

    # Company filter (new)
    with col2 if period != "Custom" else col4:
        companies = ["All"] + COMPANIES
        company_filter = st.selectbox("Company", companies)

    # Filters - row 2
    cols2 = st.columns(3)
    with cols2[0]:
        # Filter members by company first
        filtered_for_dept = members
        if company_filter != "All":
            filtered_for_dept = [m for m in members if m.get("company") == company_filter]
        depts = ["All"] + sorted(set(m["dept"] for m in filtered_for_dept if m.get("dept")))
        dept_filter = st.selectbox("Department", depts)

    with cols2[1]:
        if dept_filter == "All":
            disciplines = ["All"] + sorted(set(m["discipline"] for m in filtered_for_dept if m.get("discipline")))
        else:
            disciplines = ["All"] + sorted(DEPT_DISCIPLINES.get(dept_filter, []))
        disc_filter = st.selectbox("Discipline", disciplines)

    with cols2[2]:
        member_options = ["All Members"]
        filtered_members = members
        if company_filter != "All":
            filtered_members = [m for m in filtered_members if m.get("company") == company_filter]
        if dept_filter != "All":
            filtered_members = [m for m in filtered_members if m.get("dept") == dept_filter]
        if disc_filter != "All":
            filtered_members = [m for m in filtered_members if m.get("discipline") == disc_filter]
        member_options += sorted([m["name"] for m in filtered_members])
        member_filter = st.selectbox("Member", member_options)

    # Load entries
    if not is_admin:
        st.info("Showing your own entries only. Admin can see all team data.")
        entries = db.get_entries_for_user(user["id"])
    else:
        entries = db.get_all_entries()

    # Apply filters
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")
    members_dict = {m["id"]: m for m in members}

    filtered = []
    for e in entries:
        if not (from_str <= e["entry_date"] <= to_str):
            continue
        m = members_dict.get(e["uid"])
        if not m:
            continue
        if company_filter != "All" and m.get("company") != company_filter:
            continue
        if dept_filter != "All" and m.get("dept") != dept_filter:
            continue
        if disc_filter != "All" and m.get("discipline") != disc_filter:
            continue
        if member_filter != "All Members" and m.get("name") != member_filter:
            continue
        filtered.append({**e, "_member": m})

    # KPIs
    total_hrs = sum(e["hrs"] for e in filtered)
    unique_members = len(set(e["uid"] for e in filtered))
    unique_projects = len(set(e["proj"] for e in filtered))

    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{total_hrs:.1f}</div>
                    <div class="kpi-label">Total Hours</div></div>""", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{len(filtered)}</div>
                    <div class="kpi-label">Entries</div></div>""", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{unique_members}</div>
                    <div class="kpi-label">Members</div></div>""", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{unique_projects}</div>
                    <div class="kpi-label">Projects</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not filtered:
        st.info("No entries found for the selected filters.")
        return

    # Build dataframe
    df_data = []
    for e in filtered:
        m = e["_member"]
        df_data.append({
            "Name": m["name"],
            "Company": m.get("company", "—"),
            "Department": m.get("dept", "—"),
            "Discipline": m.get("discipline", "—"),
            "Project": e["proj"],
            "Activity": e["act"],
            "Date": e["entry_date"],
            "Hours": float(e["hrs"]),
            "Description": e.get("description", "")
        })
    df = pd.DataFrame(df_data)
    df = df.sort_values("Date", ascending=False)

    st.dataframe(df, use_container_width=True, height=500)

    # Download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download CSV",
        csv,
        f"team_view_{from_str}_to_{to_str}.csv",
        "text/csv"
    )
