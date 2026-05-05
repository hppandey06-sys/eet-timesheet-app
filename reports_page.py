"""
Reports page — comprehensive reporting and Excel exports.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
import db
from constants import DEPT_DISCIPLINES, get_month_label


def show():
    user = st.session_state.user
    is_admin = user["role"] == "admin"

    st.markdown("### 📊 Reports")

    if not is_admin:
        st.warning("Reports are admin-only. You can see your own data in 'My Timesheet'.")
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        from_date = st.date_input("From", value=date.today() - timedelta(days=30))
    with col2:
        to_date = st.date_input("To", value=date.today())
    with col3:
        st.write("")
        st.write("")
        run = st.button("Run Report", type="primary", use_container_width=True)

    col4, col5, col6 = st.columns(3)
    members = db.get_members()
    projects = db.get_projects()

    with col4:
        depts = ["All"] + sorted(set(m["dept"] for m in members if m.get("dept")))
        dept_filter = st.selectbox("Department", depts, key="rep_dept")
    with col5:
        if dept_filter == "All":
            disciplines = ["All"] + sorted(set(m["discipline"] for m in members if m.get("discipline")))
        else:
            disciplines = ["All"] + sorted(DEPT_DISCIPLINES.get(dept_filter, []))
        disc_filter = st.selectbox("Discipline", disciplines, key="rep_disc")
    with col6:
        proj_options = ["All"] + sorted([p["name"] for p in projects])
        proj_filter = st.selectbox("Project", proj_options, key="rep_proj")

    if not run and "report_data" not in st.session_state:
        st.info("Click 'Run Report' to generate.")
        return

    # Load and filter
    with st.spinner("Loading data..."):
        all_entries = db.get_all_entries()
        members_dict = {m["id"]: m for m in members}

        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        filtered = []
        for e in all_entries:
            if not (from_str <= e["entry_date"] <= to_str):
                continue
            m = members_dict.get(e["uid"])
            if not m:
                continue
            if dept_filter != "All" and m.get("dept") != dept_filter:
                continue
            if disc_filter != "All" and m.get("discipline") != disc_filter:
                continue
            if proj_filter != "All" and e["proj"] != proj_filter:
                continue
            filtered.append({**e, "_member": m})

    if not filtered:
        st.warning("No entries found for the selected filters.")
        return

    # KPIs
    total_hrs = sum(e["hrs"] for e in filtered)
    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{total_hrs:.1f}</div>
                    <div class="kpi-label">Total Hours</div></div>""", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{len(filtered)}</div>
                    <div class="kpi-label">Entries</div></div>""", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{len(set(e['uid'] for e in filtered))}</div>
                    <div class="kpi-label">Members</div></div>""", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{len(set(e['proj'] for e in filtered))}</div>
                    <div class="kpi-label">Projects</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Build dataframe
    df = pd.DataFrame([{
        "Name": e["_member"]["name"],
        "Department": e["_member"].get("dept", "—"),
        "Discipline": e["_member"].get("discipline", "—"),
        "Project": e["proj"],
        "Activity": e["act"],
        "Date": e["entry_date"],
        "Hours": float(e["hrs"]),
        "Description": e.get("description", "")
    } for e in filtered])
    df = df.sort_values("Date", ascending=False)

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📋 Detailed Entries", "📊 Summary by Member", "📊 Summary by Project"])

    with tab1:
        st.dataframe(df, use_container_width=True, height=400)

        # Downloads
        col_a, col_b = st.columns(2)
        with col_a:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", csv,
                               f"report_{from_str}_to_{to_str}.csv", "text/csv",
                               use_container_width=True)
        with col_b:
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Entries", index=False)
            st.download_button("📥 Download Excel", excel_buffer.getvalue(),
                               f"report_{from_str}_to_{to_str}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)

    with tab2:
        summary_member = df.groupby(["Name", "Department", "Discipline"])["Hours"].sum().reset_index()
        summary_member = summary_member.sort_values("Hours", ascending=False)
        st.dataframe(summary_member, use_container_width=True, height=400)
        st.bar_chart(summary_member.set_index("Name")["Hours"])

    with tab3:
        summary_proj = df.groupby("Project")["Hours"].sum().reset_index()
        summary_proj = summary_proj.sort_values("Hours", ascending=False)
        st.dataframe(summary_proj, use_container_width=True, height=400)
        st.bar_chart(summary_proj.set_index("Project")["Hours"])
