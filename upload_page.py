"""
Upload page — bulk member import + historical timesheet data upload.
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import db
from constants import DEPT_DISCIPLINES


def show():
    user = st.session_state.user
    if user["role"] != "admin":
        st.error("Admin access required")
        return

    st.markdown("### 📤 Upload Data")

    tab1, tab2 = st.tabs(["👥 Bulk Add Members", "📋 Historical Timesheet Data"])

    with tab1:
        show_bulk_members()

    with tab2:
        show_historical_data()


# ════════════════════════════════════════════════════
# BULK ADD MEMBERS
# ════════════════════════════════════════════════════
def show_bulk_members():
    st.markdown("""
    Upload a CSV or Excel file to add multiple members at once.

    **Required columns:** `Name`, `Email`, `Department`, `Discipline`, `Role`
    **Optional:** `Password` (defaults to 1234)

    **Valid Departments:** Engineering, Project, Procurement
    """)

    # Download template
    template_df = pd.DataFrame([
        {"Name": "John Smith", "Email": "john@eetfuels.com",
         "Department": "Engineering", "Discipline": "Process",
         "Role": "member", "Password": "1234"},
        {"Name": "Jane Doe", "Email": "jane@eetfuels.com",
         "Department": "Project", "Discipline": "Document Control",
         "Role": "member", "Password": "1234"},
    ])

    col1, col2 = st.columns([1, 1])
    with col1:
        csv_template = template_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV Template", csv_template,
                           "members_template.csv", "text/csv",
                           use_container_width=True)
    with col2:
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            template_df.to_excel(writer, sheet_name="Members", index=False)
        st.download_button("📥 Download Excel Template", excel_buffer.getvalue(),
                           "members_template.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    st.markdown("---")

    uploaded = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx", "xls"], key="member_file")

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)

            # Normalize column names
            df.columns = [c.strip() for c in df.columns]

            required = ["Name", "Email"]
            missing_cols = [c for c in required if c not in df.columns]
            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
                return

            st.markdown("##### Preview")
            st.dataframe(df.head(20), use_container_width=True)
            st.caption(f"Total rows: {len(df)}")

            if st.button("✅ Import All Members", type="primary"):
                members_data = []
                for _, row in df.iterrows():
                    m = {
                        "name": str(row.get("Name", "")).strip(),
                        "email": str(row.get("Email", "")).strip(),
                        "dept": str(row.get("Department", "Engineering")).strip(),
                        "discipline": str(row.get("Discipline", "")).strip(),
                        "role": str(row.get("Role", "member")).strip().lower(),
                        "password": str(row.get("Password", "1234")).strip()
                    }
                    if m["name"] and m["email"]:
                        members_data.append(m)

                if not members_data:
                    st.error("No valid rows to import")
                    return

                with st.spinner("Importing..."):
                    added, skipped = db.bulk_add_members(members_data)

                st.success(f"✅ Imported {added} members")
                if skipped:
                    st.warning(f"Skipped (email already exists): {', '.join(skipped)}")
        except Exception as e:
            st.error(f"Error reading file: {e}")


# ════════════════════════════════════════════════════
# HISTORICAL DATA UPLOAD
# ════════════════════════════════════════════════════
def show_historical_data():
    st.markdown("""
    Upload historical timesheet entries.

    **Required columns:** `Name`, `Date`, `Project`, `Hours`
    **Optional:** `Activity`, `Description`

    **Date format:** YYYY-MM-DD or DD-Mon-YY (e.g., `2026-04-15` or `15-Apr-26`)
    """)

    # Template
    template_df = pd.DataFrame([
        {"Name": "Piyush Patil", "Date": "2026-04-15",
         "Project": "HPP1", "Activity": "PRS-02", "Hours": 8.0,
         "Description": "P&ID review"},
        {"Name": "Manoj Gupta", "Date": "2026-04-15",
         "Project": "MTJ", "Activity": "OTHERS", "Hours": 6.0,
         "Description": "MTJ coordination"},
    ])

    col1, col2 = st.columns(2)
    with col1:
        csv_t = template_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 CSV Template", csv_t, "timesheet_template.csv",
                           "text/csv", use_container_width=True)
    with col2:
        eb = BytesIO()
        with pd.ExcelWriter(eb, engine="openpyxl") as w:
            template_df.to_excel(w, sheet_name="Timesheet", index=False)
        st.download_button("📥 Excel Template", eb.getvalue(),
                           "timesheet_template.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    st.markdown("---")

    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"], key="hist_file")

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)

            df.columns = [c.strip() for c in df.columns]
            st.markdown("##### Preview")
            st.dataframe(df.head(20), use_container_width=True)

            # Match members
            members = db.get_members()
            members_by_name = {m["name"].lower(): m for m in members}

            preview_data = []
            for _, row in df.iterrows():
                name = str(row.get("Name", "")).strip()
                m = members_by_name.get(name.lower())

                # Parse date
                date_str = str(row.get("Date", "")).strip()
                try:
                    if "-" in date_str and len(date_str.split("-")[0]) == 4:
                        parsed_date = date_str
                    else:
                        parsed_date = pd.to_datetime(date_str).strftime("%Y-%m-%d")
                except:
                    parsed_date = None

                hrs = 0
                try:
                    hrs = float(row.get("Hours", 0))
                except:
                    pass

                status = "✅ Valid"
                if not m:
                    status = f"❌ Member '{name}' not found"
                elif not parsed_date:
                    status = "❌ Invalid date"
                elif hrs <= 0:
                    status = "❌ Invalid hours"

                preview_data.append({
                    "Status": status,
                    "Name": name,
                    "Date": parsed_date or date_str,
                    "Project": str(row.get("Project", "")),
                    "Activity": str(row.get("Activity", "OTHERS")),
                    "Hours": hrs,
                    "Description": str(row.get("Description", "")),
                    "_uid": m["id"] if m else None
                })

            preview_df = pd.DataFrame(preview_data)
            valid_count = sum(1 for p in preview_data if p["Status"] == "✅ Valid")
            invalid_count = len(preview_data) - valid_count

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Valid rows", valid_count)
            with col2:
                st.metric("Invalid (will skip)", invalid_count)

            st.dataframe(preview_df.drop(columns=["_uid"]), use_container_width=True)

            if valid_count > 0 and st.button(f"✅ Import {valid_count} Valid Entries", type="primary"):
                # Group by user+date for save_day_entries
                from collections import defaultdict
                grouped = defaultdict(list)
                for p in preview_data:
                    if p["Status"] == "✅ Valid":
                        key = (p["_uid"], p["Date"])
                        grouped[key].append({
                            "proj": p["Project"],
                            "act": p["Activity"] or "OTHERS",
                            "hrs": p["Hours"],
                            "desc": p["Description"]
                        })

                imported = 0
                with st.spinner(f"Importing {valid_count} entries..."):
                    progress = st.progress(0)
                    for i, ((uid, dt), entries) in enumerate(grouped.items()):
                        try:
                            db.save_day_entries(uid, dt, entries)
                            imported += len(entries)
                        except Exception as e:
                            st.warning(f"Failed for uid {uid} on {dt}: {e}")
                        progress.progress((i + 1) / len(grouped))

                st.success(f"✅ Imported {imported} entries across {len(grouped)} day-records")

        except Exception as e:
            st.error(f"Error: {e}")
