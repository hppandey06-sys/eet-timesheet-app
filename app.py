"""
EET Fuels Team Timesheet — Streamlit App
Replaces the GitHub Pages HTML with a proper Python web app.
Backend: Supabase (already set up)
"""

import streamlit as st
from datetime import date, datetime, timedelta
from db import (
    get_members, get_projects, get_entries_for_user, get_all_entries,
    save_day_entries, get_submissions, get_edit_requests,
    submit_month, request_edit, handle_edit_request,
    add_member, update_member, delete_member, change_member_role,
    add_project, update_project, delete_project,
    add_custom_act, get_custom_acts, delete_custom_act,
    bulk_add_members, login_user
)
from constants import (
    APP_TITLE, MAX_DAY_HRS, HOLIDAYS_2026, DEPT_DISCIPLINES,
    DISCIPLINE_ACTIVITIES, format_date_short, get_month_label,
    get_working_days, todayIST
)

# ════════════════════════════════════════════════════
# PAGE SETUP
# ════════════════════════════════════════════════════
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⏱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for cleaner look
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}

    /* Clean header */
    .app-header {
        background: linear-gradient(135deg, #464775 0%, #6264a7 100%);
        color: white;
        padding: 14px 22px;
        border-radius: 10px;
        margin-bottom: 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .app-title {
        font-size: 17px;
        font-weight: 700;
    }

    /* Day cards */
    .day-card {
        background: white;
        border: 1px solid #e1dfdd;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .day-card-saved {
        background: #f0fff0;
        border-color: #107c10;
    }
    .day-card-locked {
        background: #fafafa;
        border-color: #d2d0ce;
    }

    /* KPI cards */
    .kpi {
        background: white;
        border: 1px solid #e1dfdd;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: 700;
        color: #6264a7;
    }
    .kpi-label {
        font-size: 10px;
        color: #605e5c;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Buttons */
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
    }

    /* Status pill */
    .status-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
    }
    .status-saved { background: #dff6dd; color: #107c10; }
    .status-pending { background: #fff4ce; color: #7a5700; }
    .status-locked { background: #fde7e9; color: #d13438; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# SESSION STATE
# ════════════════════════════════════════════════════
if "user" not in st.session_state:
    st.session_state.user = None
if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0
if "draft_entries" not in st.session_state:
    st.session_state.draft_entries = {}
if "page" not in st.session_state:
    st.session_state.page = "home"


# ════════════════════════════════════════════════════
# LOGIN SCREEN
# ════════════════════════════════════════════════════
def show_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(f"""
        <div style="text-align:center;margin-bottom:20px">
            <div style="font-size:42px">⏱</div>
            <h1 style="font-size:22px;color:#6264a7;margin-top:8px">{APP_TITLE}</h1>
            <p style="color:#605e5c;font-size:13px;margin-top:4px">Sign in to your account</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            members = get_members()
            members_sorted = sorted(members, key=lambda m: m["name"])
            options = ["— Choose your name —"] + [m["name"] for m in members_sorted]
            selected_name = st.selectbox("Select your name", options)
            password = st.text_input("Password", type="password", placeholder="Default: 1234")
            submit = st.form_submit_button("Sign In →", use_container_width=True, type="primary")

            if submit:
                if selected_name == "— Choose your name —":
                    st.error("Please select your name")
                elif not password:
                    st.error("Please enter your password")
                else:
                    user = login_user(selected_name, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Incorrect password")


# ════════════════════════════════════════════════════
# TOP BAR
# ════════════════════════════════════════════════════
def show_topbar():
    user = st.session_state.user
    is_admin = user["role"] == "admin"

    initials = "".join([w[0].upper() for w in user["name"].split()[:2]])
    st.markdown(f"""
    <div class="app-header">
        <div>
            <span style="font-size:18px;margin-right:8px">⏱</span>
            <span class="app-title">{APP_TITLE}</span>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
            <div style="width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,0.25);
                        display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px">
                {initials}
            </div>
            <div>
                <div style="font-size:13px;font-weight:600">{user["name"]}</div>
                <div style="font-size:10px;opacity:0.75">{user["dept"]} · {user["discipline"]} · {user["role"]}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Navigation tabs
    tabs = ["🏠 Home", "📋 My Timesheet", "👥 Team View", "📊 Reports"]
    page_ids = ["home", "timesheet", "team", "reports"]

    # MER tab visible to super admins + discipline leads
    import mer_page
    if mer_page.can_access_mer(user):
        tabs.append("📅 MER")
        page_ids.append("mer")

    if is_admin:
        tabs.extend(["⚙️ Admin", "📤 Upload Data"])
        page_ids.extend(["admin", "upload"])

    cols = st.columns(len(tabs) + 1)
    for i, tab_label in enumerate(tabs):
        with cols[i]:
            page_id = page_ids[i]
            if st.button(tab_label, key=f"nav_{page_id}", use_container_width=True,
                         type="primary" if st.session_state.page == page_id else "secondary"):
                st.session_state.page = page_id
                st.rerun()
    with cols[-1]:
        if st.button("Sign Out", use_container_width=True):
            st.session_state.user = None
            st.session_state.draft_entries = {}
            st.rerun()


# ════════════════════════════════════════════════════
# MAIN ROUTER
# ════════════════════════════════════════════════════
def main():
    if st.session_state.user is None:
        show_login()
        return

    show_topbar()

    page = st.session_state.page

    # Lazy imports of page modules to keep app.py clean
    if page == "home":
        import home_page
        home_page.show()
    elif page == "timesheet":
        import timesheet_page
        timesheet_page.show()
    elif page == "team":
        import team_view
        team_view.show()
    elif page == "reports":
        import reports_page
        reports_page.show()
    elif page == "mer":
        import mer_page
        mer_page.render(st.session_state.user)
    elif page == "admin":
        import admin_page
        admin_page.show()
    elif page == "upload":
        import upload_page
        upload_page.show()


if __name__ == "__main__":
    main()
