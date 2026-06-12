"""
Admin page — manage members, projects, edit requests, reminders.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
import db
import excel_export
import reminders_page
from constants import (
    DEPT_DISCIPLINES, DISCIPLINE_ACTIVITIES, get_month_label,
    todayIST, HOLIDAYS_2026, COMPANIES,
    ACTIVITY_CATEGORIES, CATEGORY_OPTIONS, category_label, get_act_category,
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
        reminders_page.render(user)
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
    cols_to_show = ["id", "name", "email", "company", "dept", "discipline", "role", "leads_discipline"]
    cols_present = [c for c in cols_to_show if c in df.columns]
    df = df[cols_present].copy()
    rename_map = {"id": "ID", "name": "Name", "email": "Email",
                  "company": "Company", "dept": "Department",
                  "discipline": "Discipline", "role": "Role",
                  "leads_discipline": "Leads"}
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

                # ── Discipline lead assignment ──
                all_disciplines = sorted(set(
                    d for ds in DEPT_DISCIPLINES.values() for d in ds))
                col5, col6 = st.columns(2)
                with col5:
                    new_is_lead = st.checkbox(
                        "Discipline Lead (PREP inputs + MER access)",
                        value=bool(member.get("is_discipline_lead")))
                with col6:
                    cur_lead_disc = member.get("leads_discipline") or member.get("discipline")
                    if cur_lead_disc not in all_disciplines:
                        cur_lead_disc = all_disciplines[0]
                    new_lead_disc = st.selectbox(
                        "Leads discipline", all_disciplines,
                        index=all_disciplines.index(cur_lead_disc),
                        help="Which discipline this person leads — usually their own. "
                             "Only applies if the Lead box is ticked.")

                col_save, col_del = st.columns(2)
                with col_save:
                    save = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                with col_del:
                    delete = st.form_submit_button("🗑 Delete Member", use_container_width=True)

                if save:
                    fields = {"name": new_name, "email": new_email,
                              "company": new_company, "dept": new_dept,
                              "discipline": new_disc, "role": new_role,
                              "is_discipline_lead": new_is_lead,
                              "leads_discipline": new_lead_disc if new_is_lead else None}
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

    sub_tab1, sub_tab2, sub_tab3 = st.tabs(
        ["By Discipline", "By Project (workstreams)", "Bulk Upload (Excel)"])

    with sub_tab1:
        show_discipline_codes()
    with sub_tab2:
        show_project_codes()
    with sub_tab3:
        show_bulk_upload_codes()


def show_discipline_codes():
    """Discipline activity codes — all stored in DB, all editable."""
    st.markdown("##### Discipline Activity Codes")
    st.caption("All codes are editable. OTHERS is fixed per discipline and "
               "always available for booking.")

    all_disciplines = sorted(set(
        d for discs in DEPT_DISCIPLINES.values() for d in discs
    ))

    sel_disc = st.selectbox("Filter by discipline", ["All"] + all_disciplines, key="disc_filter")

    custom_acts = db.get_custom_acts()

    with st.expander("➕ Add activity code", expanded=False):
        with st.form("add_act"):
            col1, col2 = st.columns(2)
            with col1:
                code = st.text_input("Code", placeholder="e.g. PRS-12")
                disc = st.selectbox("Discipline", all_disciplines, key="add_act_disc")
            with col2:
                desc = st.text_input("Description", placeholder="e.g. HAZOP Review")
                cat = st.selectbox("Productivity category", CATEGORY_OPTIONS, key="add_act_cat")

            if st.form_submit_button("Add", type="primary"):
                if code and desc and disc:
                    dup = (code.upper() == "OTHERS" or any(
                        c["code"].upper() == code.upper() and c["discipline"] == disc
                        for c in custom_acts))
                    if dup:
                        st.error(f"❌ {code.upper()} already exists for {disc}")
                    else:
                        try:
                            db.add_custom_act(code, desc, disc, cat.split(".")[0])
                            st.success(f"✅ {code.upper()} added")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")

    rows = []
    disc_list = all_disciplines if sel_disc == "All" else [sel_disc]
    db_discs = {c.get("discipline") for c in custom_acts}
    for disc in disc_list:
        disc_codes = [c for c in custom_acts if c.get("discipline") == disc]
        for c in sorted(disc_codes, key=lambda x: x["code"]):
            rows.append({"Code": c["code"], "Description": c["description"],
                         "Discipline": c["discipline"],
                         "Category": category_label(c.get("category") or "8")})
        if disc not in db_discs:
            # Not yet migrated to DB — show seed list (read-only fallback)
            for code, desc in DISCIPLINE_ACTIVITIES.get(disc, []):
                if code != "OTHERS":
                    rows.append({"Code": code, "Description": desc + "  (seed — run "
                                 "migration SQL to make editable)",
                                 "Discipline": disc,
                                 "Category": category_label(get_act_category(code, disc))})
        rows.append({"Code": "OTHERS", "Description": "Others", "Discipline": disc,
                     "Category": category_label("8") + "  (fixed)"})

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No activity codes for this discipline")

    # ── Edit / delete codes ──
    edit_pool = [c for c in custom_acts
                 if sel_disc == "All" or c.get("discipline") == sel_disc]
    if edit_pool:
        st.markdown("##### ✏️ Edit / delete code")
        options = ["—"] + [f"{c['discipline']} · {c['code']} — {c['description']} (ID:{c['id']})"
                           for c in sorted(edit_pool,
                                           key=lambda x: (x["discipline"], x["code"]))]
        sel = st.selectbox("Select code", options, key="edit_act_sel")
        if sel != "—":
            act_id = int(sel.split("ID:")[1].rstrip(")"))
            act = next(c for c in edit_pool if c["id"] == act_id)
            cur_cat = str(act.get("category") or "8")
            with st.form("edit_act"):
                col1, col2 = st.columns(2)
                with col1:
                    new_code = st.text_input("Code", value=act["code"])
                    new_disc = st.selectbox("Discipline", all_disciplines,
                                            index=all_disciplines.index(act["discipline"])
                                            if act["discipline"] in all_disciplines else 0)
                with col2:
                    new_desc = st.text_input("Description", value=act["description"])
                    cat_idx = list(ACTIVITY_CATEGORIES.keys()).index(cur_cat) \
                        if cur_cat in ACTIVITY_CATEGORIES else 7
                    new_cat = st.selectbox("Productivity category", CATEGORY_OPTIONS,
                                           index=cat_idx)
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 Update", type="primary"):
                        try:
                            db.update_custom_act(act_id, code=new_code, description=new_desc,
                                                 discipline=new_disc,
                                                 category=new_cat.split(".")[0])
                            st.success(f"✅ {new_code.upper()} updated")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                with c2:
                    if st.form_submit_button("🗑 Delete this code"):
                        try:
                            db.delete_custom_act(act_id)
                            st.success("Deleted")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
            st.caption("⚠️ Renaming or deleting a code does not change hours already "
                       "booked against it — those entries keep the old code string.")


def show_bulk_upload_codes():
    """Bulk upload custom activity codes + categories from the mapping Excel."""
    st.markdown("##### 📤 Bulk Upload Activity Codes")
    st.caption("Upload the 'GCC Activity Code Category Mapping' Excel. Every code row "
               "is added or updated (matched on Code + Discipline). OTHERS rows are "
               "ignored — OTHERS is fixed per discipline.")

    f = st.file_uploader("Excel file (.xlsx)", type=["xlsx"], key="bulk_act_upload")
    if not f:
        return

    try:
        df = pd.read_excel(f, sheet_name=0, dtype=str).fillna("")
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return

    needed = {"Code", "Description", "Discipline"}
    if not needed.issubset(df.columns):
        st.error(f"Missing columns. Expected at least: {', '.join(sorted(needed))}")
        return
    cat_col = next((c for c in df.columns if "categor" in c.lower()), None)
    if not cat_col:
        st.error("No category column found (e.g. 'Proposed Category').")
        return

    all_disciplines = sorted(set(d for discs in DEPT_DISCIPLINES.values() for d in discs))
    rows, problems = [], []
    seen = set()
    for i, r in df.iterrows():
        code = str(r["Code"]).strip().upper()
        disc = str(r["Discipline"]).strip()
        desc = str(r["Description"]).strip()
        cat = str(r[cat_col]).strip().split(".")[0]
        if not code or code == "OTHERS":
            continue
        if disc not in all_disciplines:
            problems.append(f"Row {i+2}: unknown discipline '{disc}' ({code})")
            continue
        if cat not in ACTIVITY_CATEGORIES:
            problems.append(f"Row {i+2}: invalid category '{r[cat_col]}' ({code})")
            continue
        if (code, disc) in seen:
            problems.append(f"Row {i+2}: {code} appears twice for {disc} (second skipped)")
            continue
        seen.add((code, disc))
        rows.append({"code": code, "description": desc, "discipline": disc, "category": cat})

    existing = {(c["code"].upper(), c["discipline"]) for c in db.get_custom_acts()}
    n_new = sum(1 for r in rows if (r["code"], r["discipline"]) not in existing)
    n_upd = len(rows) - n_new

    st.info(f"Ready: **{n_new} new** codes, **{n_upd} updates** to existing custom codes.")
    if problems:
        with st.expander(f"⚠️ {len(problems)} rows skipped — review", expanded=True):
            for p in problems:
                st.write("• " + p)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if st.button("✅ Apply upload", type="primary", key="apply_bulk_acts"):
            try:
                added, updated = db.bulk_upsert_custom_acts(rows)
                st.success(f"Done — {added} added, {updated} updated.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")


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
        project_options = ["ALL PROJECTS"] + [p["name"] for p in projects]
        sel_project = st.selectbox("Project", project_options, key="export_project",
                                    help="Choose 'ALL PROJECTS' to combine all projects in one Excel")

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
                # Get entries for member
                entries = db.get_entries_for_user(sel_member["id"])

                # Get project-specific activity codes (empty for ALL PROJECTS)
                if sel_project == "ALL PROJECTS":
                    project_acts = []
                else:
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

                proj_label = "All_Projects" if sel_project == "ALL PROJECTS" else sel_project.replace(' ', '_')
                filename = f"Timesheet_{sel_member['name'].replace(' ', '_')}_{proj_label}_{from_date.strftime('%b%Y')}.xlsx"

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

    # ── BULK EXPORT — all members at once ──
    st.markdown("---")
    st.markdown("##### 📦 Bulk Export — All Members (ZIP file)")
    st.caption("Generate Excel files for ALL team members in one go, packaged as a ZIP.")

    col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
    with col1:
        bulk_company = st.selectbox("Company filter",
                                     ["All"] + COMPANIES,
                                     key="bulk_company")
    with col2:
        bulk_proj_options = ["ALL PROJECTS"] + [p["name"] for p in projects]
        bulk_project = st.selectbox("Project", bulk_proj_options, key="bulk_project")
    with col3:
        bulk_from = st.date_input("From", value=last_month_start, key="bulk_from")
    with col4:
        bulk_to = st.date_input("To", value=last_month_end, key="bulk_to")

    if st.button("📦 Generate Bulk ZIP", type="secondary"):
        # Filter members
        if bulk_company == "All":
            members_to_export = members
        else:
            members_to_export = [m for m in members if m.get("company") == bulk_company]

        if not members_to_export:
            st.error("No members found for the selected company")
            return

        try:
            import zipfile
            from io import BytesIO

            zip_buf = BytesIO()
            with st.spinner(f"Generating Excel for {len(members_to_export)} members..."):
                progress = st.progress(0)
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, m in enumerate(members_to_export):
                        try:
                            entries = db.get_entries_for_user(m["id"])
                            # Skip members with no entries in the date range
                            from_str = bulk_from.strftime("%Y-%m-%d")
                            to_str = bulk_to.strftime("%Y-%m-%d")
                            relevant = [e for e in entries
                                       if from_str <= e["entry_date"] <= to_str]
                            if not relevant:
                                continue

                            if bulk_project == "ALL PROJECTS":
                                p_acts = []
                            else:
                                p_acts = db.get_project_acts(bulk_project)

                            buf = excel_export.export_member_timesheet(
                                member=m,
                                project_name=bulk_project,
                                project_acts=p_acts,
                                entries=entries,
                                from_date=from_str,
                                to_date=to_str,
                                company=m.get("company", "GCC")
                            )

                            proj_label = "All_Projects" if bulk_project == "ALL PROJECTS" else bulk_project.replace(' ', '_')
                            fname = f"{m['company']}_{m['name'].replace(' ', '_')}_{proj_label}_{bulk_from.strftime('%b%Y')}.xlsx"
                            zf.writestr(fname, buf.getvalue())
                        except Exception as e:
                            st.warning(f"Skipped {m['name']}: {e}")

                        progress.progress((i + 1) / len(members_to_export))

            zip_buf.seek(0)
            zip_size_kb = len(zip_buf.getvalue()) / 1024
            zip_filename = f"Timesheets_{bulk_company}_{bulk_from.strftime('%b%Y')}.zip"

            st.success(f"✅ ZIP ready ({zip_size_kb:.0f} KB) — click below to download")
            st.download_button(
                f"📥 Download {zip_filename}",
                zip_buf.getvalue(),
                zip_filename,
                "application/zip",
                type="primary"
            )

        except Exception as e:
            st.error(f"Bulk export failed: {e}")
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
