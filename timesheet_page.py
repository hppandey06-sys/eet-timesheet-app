"""
Admin page — manage members, projects, edit requests, reminders.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
import db
import excel_export
from constants import (
    DEPT_DISCIPLINES, DISCIPLINE_ACTIVITIES, get_month_label,
    todayIST, HOLIDAYS_2026, COMPANIES
)


def show():
    user = st.session_state.user
    if user["role"] != "admin":
        st.error("Admin access required")
        return

    st.markdown("### ⚙️ Admin Panel")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 Members", "📁 Projects", "🏷️ Activity Codes",
        "📧 Reminders", "🗂 Entries"
    ])

    with tab1:
        show_members_tab()
    with tab2:
        show_projects_tab()
    with tab3:
        show_activity_codes_tab()
    with tab4:
        show_reminders_tab()
    with tab5:
        show_entries_tab()


# ════════════════════════════════════════════════════
# MEMBERS
# ════════════════════════════════════════════════════
def show_members_tab():
    st.markdown("#### Team Members")

    with st.expander("➕ Add new member", expanded=False):
        with st.form("add_member"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name")
                email = st.text_input("Email", placeholder="user@eetfuels.com")
                company = st.selectbox("Company", COMPANIES, index=0)
            with col2:
                dept = st.selectbox("Department", list(DEPT_DISCIPLINES.keys()))
                discipline = st.selectbox("Discipline", DEPT_DISCIPLINES[dept])

            col3, col4 = st.columns(2)
            with col3:
                role = st.selectbox("Role", ["member", "admin"])
            with col4:
                password = st.text_input("Default Password", value="1234")

            if st.form_submit_button("Add Member", type="primary"):
                if not name or not email:
                    st.error("Name and email are required")
                else:
                    try:
                        new_id = db.add_member(name, email, dept, discipline, role, password, company)
                        st.success(f"✅ {name} added (ID: {new_id})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    # Member list
    members = db.get_members()
    if not members:
        st.info("No members yet")
        return

    df = pd.DataFrame(members)
    cols_to_show = ["id", "name", "email", "company", "dept", "discipline", "role"]
    cols_present = [c for c in cols_to_show if c in df.columns]
    df = df[cols_present].copy()
    rename_map = {"id": "ID", "name": "Name", "email": "Email",
                  "company": "Company", "dept": "Department",
                  "discipline": "Discipline", "role": "Role"}
    df.columns = [rename_map.get(c, c) for c in df.columns]
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("##### 📥 Export Member Timesheet")
    show_export_section(members)
    st.markdown("---")

    # Edit/delete
    st.markdown("##### Edit or delete a member")
    selected_member = st.selectbox(
        "Select member to edit/delete",
        ["—"] + [f"{m['name']} (ID:{m['id']})" for m in members]
    )

    if selected_member != "—":
        member_id = int(selected_member.split("ID:")[1].rstrip(")"))
        member = next((m for m in members if m["id"] == member_id), None)
        if member:
            with st.form(f"edit_member_{member_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Name", value=member["name"])
                    new_email = st.text_input("Email", value=member["email"])
                    cur_company = member.get("company", "GCC")
                    if cur_company not in COMPANIES:
                        cur_company = "GCC"
                    new_company = st.selectbox("Company", COMPANIES,
                                               index=COMPANIES.index(cur_company))
                with col2:
                    cur_dept = member.get("dept", "Engineering")
                    if cur_dept not in DEPT_DISCIPLINES:
                        cur_dept = "Engineering"
                    new_dept = st.selectbox("Department", list(DEPT_DISCIPLINES.keys()),
                                            index=list(DEPT_DISCIPLINES.keys()).index(cur_dept))
                    discs = DEPT_DISCIPLINES[new_dept]
                    cur_disc = member.get("discipline", discs[0])
                    if cur_disc not in discs:
                        cur_disc = discs[0]
                    new_disc = st.selectbox("Discipline", discs, index=discs.index(cur_disc))

                col3, col4 = st.columns(2)
                with col3:
                    new_role = st.selectbox("Role", ["member", "admin"],
                                            index=0 if member.get("role") == "member" else 1)
                with col4:
                    new_pw = st.text_input("Reset Password (leave blank to keep)", placeholder="(unchanged)")

                col_save, col_del = st.columns(2)
                with col_save:
                    save = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                with col_del:
                    delete = st.form_submit_button("🗑 Delete Member", use_container_width=True)

                if save:
                    fields = {"name": new_name, "email": new_email,
                              "company": new_company, "dept": new_dept,
                              "discipline": new_disc, "role": new_role}
                    if new_pw.strip():
                        fields["password"] = new_pw.strip()
                    db.update_member(member_id, **fields)
                    st.success(f"✅ {new_name} updated")
                    st.rerun()

                if delete:
                    db.delete_member(member_id)
                    st.success(f"Deleted {member['name']}")
                    st.rerun()


# ════════════════════════════════════════════════════
# PROJECTS
# ════════════════════════════════════════════════════
def show_projects_tab():
    st.markdown("#### Projects")

    with st.expander("➕ Add new project", expanded=False):
        with st.form("add_project"):
            col1, col2 = st.columns(2)
            with col1:
                code = st.text_input("Project Code", placeholder="e.g. DC-PWR")
                name = st.text_input("Project Name", placeholder="e.g. DC Power")
            with col2:
                dept = st.selectbox("Department", list(DEPT_DISCIPLINES.keys()), key="proj_dept")
                status = st.selectbox("Status", ["Active", "On Hold", "Closed"])

            if st.form_submit_button("Add Project", type="primary"):
                if not code or not name:
                    st.error("Code and name required")
                else:
                    try:
                        db.add_project(code.upper(), name, dept, status)
                        st.success(f"✅ {name} added")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    projects = db.get_projects()
    if not projects:
        st.info("No projects yet")
        return

    df = pd.DataFrame(projects)
    df = df[["id", "code", "name", "dept", "status"]].copy()
    df.columns = ["ID", "Code", "Name", "Department", "Status"]
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Edit/delete
    selected = st.selectbox(
        "Select project to edit/delete",
        ["—"] + [f"{p['name']} (ID:{p['id']})" for p in projects],
        key="proj_select"
    )

    if selected != "—":
        proj_id = int(selected.split("ID:")[1].rstrip(")"))
        proj = next((p for p in projects if p["id"] == proj_id), None)
        if proj:
            with st.form(f"edit_proj_{proj_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_code = st.text_input("Code", value=proj["code"])
                    new_name = st.text_input("Name", value=proj["name"])
                with col2:
                    new_status = st.selectbox("Status", ["Active", "On Hold", "Closed"],
                                              index=["Active", "On Hold", "Closed"].index(proj.get("status", "Active")))

                col_s, col_d = st.columns(2)
                with col_s:
                    save = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
                with col_d:
                    delete = st.form_submit_button("🗑 Delete", use_container_width=True)

                if save:
                    db.update_project(proj_id, code=new_code, name=new_name, status=new_status)
                    st.success("Updated")
                    st.rerun()
                if delete:
                    db.delete_project(proj_id)
                    st.success("Deleted")
                    st.rerun()


# ════════════════════════════════════════════════════
# ACTIVITY CODES
# ════════════════════════════════════════════════════
def show_activity_codes_tab():
    st.markdown("#### 🏷️ Activity Codes")

    sub_tab1, sub_tab2 = st.tabs(["By Discipline", "By Project (workstreams)"])

    with sub_tab1:
        show_discipline_codes()
    with sub_tab2:
        show_project_codes()


def show_discipline_codes():
    """Discipline-based activity codes."""
    st.markdown("##### Discipline Activity Codes")

    all_disciplines = sorted(set(
        d for discs in DEPT_DISCIPLINES.values() for d in discs
    ))

    sel_disc = st.selectbox("Filter by discipline", ["All"] + all_disciplines, key="disc_filter")

    with st.expander("➕ Add custom activity code", expanded=False):
        with st.form("add_act"):
            col1, col2, col3 = st.columns(3)
            with col1:
                code = st.text_input("Code", placeholder="e.g. PRS-12")
            with col2:
                desc = st.text_input("Description", placeholder="e.g. HAZOP Review")
            with col3:
                disc = st.selectbox("Discipline", all_disciplines, key="add_act_disc")

            if st.form_submit_button("Add", type="primary"):
                if code and desc and disc:
                    try:
                        db.add_custom_act(code, desc, disc)
                        st.success(f"✅ {code} added")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    rows = []
    if sel_disc == "All":
        for disc in all_disciplines:
            for code, desc in DISCIPLINE_ACTIVITIES.get(disc, []):
                rows.append({"Code": code, "Description": desc, "Discipline": disc, "Type": "Built-in"})
    else:
        for code, desc in DISCIPLINE_ACTIVITIES.get(sel_disc, []):
            rows.append({"Code": code, "Description": desc, "Discipline": sel_disc, "Type": "Built-in"})

    custom_acts = db.get_custom_acts()
    if sel_disc == "All":
        custom_filter = custom_acts
    else:
        custom_filter = [c for c in custom_acts if c.get("discipline") == sel_disc]

    for c in custom_filter:
        rows.append({"Code": c["code"], "Description": c["description"],
                     "Discipline": c["discipline"], "Type": "Custom"})

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No activity codes for this discipline")


def show_project_codes():
    """Project-specific activity codes (e.g., DC Power workstreams)."""
    st.markdown("##### Project-Specific Activity Codes (Workstreams)")
    st.caption("Add codes that apply only to a specific project — like WS1, WS2 for DC Power.")

    projects = db.get_projects()

    col1 = st.columns(1)[0]
    with col1:
        proj_options = ["All"] + sorted([p["name"] for p in projects])
        sel_proj = st.selectbox("Filter by project", proj_options, key="proj_acts_filter")

    with st.expander("➕ Add project activity code", expanded=False):
        with st.form("add_proj_act"):
            col1, col2 = st.columns(2)
            with col1:
                proj_name = st.selectbox("Project", [p["name"] for p in projects], key="proj_act_proj")
                code = st.text_input("Code", placeholder="e.g. WS1, WS2")
            with col2:
                desc = st.text_input("Description", placeholder="e.g. Commercialisation")
                order = st.number_input("Display Order", min_value=0, max_value=100, value=0)

            if st.form_submit_button("Add", type="primary"):
                if proj_name and code and desc:
                    try:
                        db.add_project_act(proj_name, code, desc, order)
                        st.success(f"✅ {code} added to {proj_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    # Display
    if sel_proj == "All":
        all_proj_acts = db.get_all_project_acts()
    else:
        all_proj_acts = db.get_project_acts(sel_proj)

    if all_proj_acts:
        df = pd.DataFrame(all_proj_acts)
        cols = ["project", "code", "description", "display_order"]
        df = df[[c for c in cols if c in df.columns]]
        df.columns = [c.title() for c in df.columns]
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("##### Delete project activity code")
        sel_to_del = st.selectbox(
            "Select to delete",
            ["—"] + [f"{a['project']} · {a['code']} (ID:{a['id']})" for a in all_proj_acts]
        )
        if sel_to_del != "—":
            act_id = int(sel_to_del.split("ID:")[1].rstrip(")"))
            if st.button("🗑 Delete this code", type="secondary"):
                db.delete_project_act(act_id)
                st.success("Deleted")
                st.rerun()
    else:
        st.info("No project-specific codes yet.")


# ════════════════════════════════════════════════════
# EXPORT MEMBER TIMESHEET (replaces Edit Requests)
# ════════════════════════════════════════════════════
def show_export_section(members):
    """Export per-member, per-project timesheet in DC Power format."""
    projects = db.get_projects()

    col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])

    with col1:
        member_options = sorted([m["name"] for m in members])
        sel_member_name = st.selectbox("Member", member_options, key="export_member")
        sel_member = next((m for m in members if m["name"] == sel_member_name), None)

    with col2:
        project_options = [p["name"] for p in projects]
        sel_project = st.selectbox("Project", project_options, key="export_project")

    # Default to last calendar month
    today = date.today()
    last_month_end = date(today.year, today.month, 1) - timedelta(days=1)
    last_month_start = date(last_month_end.year, last_month_end.month, 1)

    with col3:
        from_date = st.date_input("From", value=last_month_start, key="export_from")
    with col4:
        to_date = st.date_input("To", value=last_month_end, key="export_to")

    if st.button("📥 Generate Excel", type="primary"):
        if not sel_member or not sel_project:
            st.error("Please select member and project")
            return

        try:
            with st.spinner("Generating Excel..."):
                # Get entries
                entries = db.get_entries_for_user(sel_member["id"])
                # Get project-specific activity codes
                project_acts = db.get_project_acts(sel_project)

                buffer = excel_export.export_member_timesheet(
                    member=sel_member,
                    project_name=sel_project,
                    project_acts=project_acts,
                    entries=entries,
                    from_date=from_date.strftime("%Y-%m-%d"),
                    to_date=to_date.strftime("%Y-%m-%d"),
                    company=sel_member.get("company", "GCC")
                )

                filename = f"Timesheet_{sel_member['name'].replace(' ', '_')}_{sel_project.replace(' ', '_')}_{from_date.strftime('%b%Y')}.xlsx"

                st.download_button(
                    "📥 Download " + filename,
                    buffer.getvalue(),
                    filename,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
                st.success(f"✅ Excel ready — click download above!")

        except Exception as e:
            st.error(f"Export failed: {e}")
            import traceback
            st.code(traceback.format_exc())


# ════════════════════════════════════════════════════
# FRIDAY REMINDERS
# ════════════════════════════════════════════════════
def show_reminders_tab():
    st.markdown("#### 📧 Send Reminder Emails")

    today = date.today()
    period = st.selectbox("Check missing entries for:",
                          ["Yesterday", "Today", "This Week"])

    if period == "Yesterday":
        check_dates = [(today - timedelta(days=1)).strftime("%Y-%m-%d")]
    elif period == "Today":
        check_dates = [today.strftime("%Y-%m-%d")]
    else:
        # This week — Mon to today
        monday = today - timedelta(days=today.weekday())
        check_dates = []
        d = monday
        while d <= today:
            ds = d.strftime("%Y-%m-%d")
            if d.weekday() < 5 and ds not in HOLIDAYS_2026:
                check_dates.append(ds)
            d += timedelta(days=1)

    if not check_dates:
        st.info("No working days to check")
        return

    if st.button("🔍 Check missing", type="primary"):
        members = db.get_members()
        all_entries = db.get_all_entries()

        missing = []
        for m in members:
            entries = [e for e in all_entries if e["uid"] == m["id"]]
            entry_dates = set(e["entry_date"] for e in entries)
            missing_dates = [d for d in check_dates if d not in entry_dates]
            if missing_dates:
                missing.append({"member": m, "missing_days": missing_dates})

        if not missing:
            st.success("✅ All members have filled timesheets")
            return

        st.session_state.missing_members = missing
        st.warning(f"⚠️ {len(missing)} member(s) with missing entries")

    if "missing_members" in st.session_state:
        missing = st.session_state.missing_members
        for item in missing:
            m = item["member"]
            n = len(item["missing_days"])
            st.markdown(f"- **{m['name']}** ({m['email']}) — {n} day(s) missing")

        emails = ";".join([item["member"]["email"] for item in missing])
        body = "Hi Team,\n\nThis is a reminder to complete your timesheet.\n\nMissing members:\n"
        for item in missing:
            body += f"- {item['member']['name']} — {len(item['missing_days'])} day(s)\n"
        body += "\nPlease log in and fill your timesheet.\n\nThanks,\nEET Fuels"

        import urllib.parse
        mailto = f"mailto:{emails}?subject={urllib.parse.quote('Timesheet Reminder')}&body={urllib.parse.quote(body)}"
        st.markdown(f"[📧 Open Email Client]({mailto})")


# ════════════════════════════════════════════════════
# ENTRIES (admin can edit any)
# ════════════════════════════════════════════════════
def show_entries_tab():
    st.markdown("#### 🗂 All Entries")

    members = db.get_members()
    member_dict = {m["id"]: m for m in members}

    member_filter = st.selectbox(
        "Filter by member",
        ["All"] + sorted([m["name"] for m in members])
    )

    if member_filter == "All":
        entries = db.get_all_entries()[:200]
        st.caption(f"Showing latest 200 entries (filter by member to see specific data)")
    else:
        m = next((m for m in members if m["name"] == member_filter), None)
        if m:
            entries = db.get_entries_for_user(m["id"])
        else:
            entries = []

    if not entries:
        st.info("No entries")
        return

    df_data = []
    for e in entries:
        m = member_dict.get(e["uid"], {})
        df_data.append({
            "ID": e["id"],
            "Date": e["entry_date"],
            "Member": m.get("name", "?"),
            "Project": e["proj"],
            "Activity": e["act"],
            "Hours": float(e["hrs"]),
            "Description": e.get("description", "")
        })
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
