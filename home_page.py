"""
Home / Compliance Dashboard — admin landing page.
Shows at-a-glance who has and has NOT filled timesheets.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from urllib.parse import quote
import db
from constants import HOLIDAYS_2026, COMPANIES, get_month_label, format_date_short


def show():
    user = st.session_state.user

    if user["role"] != "admin":
        # For members, show their own status
        show_member_home(user)
        return

    show_admin_dashboard(user)


# ════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ════════════════════════════════════════════════════
def show_admin_dashboard(user):
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    st.markdown("### 🏠 Compliance Dashboard")
    st.caption(f"Today: {today.strftime('%A, %d %B %Y')}")

    # Filter
    col1, col2 = st.columns([3, 1])
    with col1:
        company_filter = st.selectbox(
            "Filter by company",
            ["All Companies"] + COMPANIES,
            key="home_company"
        )
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Load data
    with st.spinner("Loading compliance data..."):
        members = db.get_members()
        all_entries = db.get_all_entries()

    # Apply company filter
    if company_filter != "All Companies":
        members = [m for m in members if m.get("company") == company_filter]

    if not members:
        st.warning("No members in this company")
        return

    # ────────────────────────────────────────────
    # TODAY KPIs
    # ────────────────────────────────────────────
    is_today_working = is_working_day(today)

    if is_today_working:
        members_filled_today = set(
            e["uid"] for e in all_entries
            if e["entry_date"] == today_str
        )
        total = len(members)
        filled = len([m for m in members if m["id"] in members_filled_today])
        pending = total - filled
        pct = (filled / total * 100) if total > 0 else 0
    else:
        # Weekend or holiday
        filled = pending = total = 0
        pct = 0

    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{total}</div>
                    <div class="kpi-label">Total Members</div></div>""",
                    unsafe_allow_html=True)
    with cols[1]:
        if is_today_working:
            color = "#107c10" if pct >= 80 else "#ca5010" if pct >= 50 else "#d13438"
            st.markdown(f"""<div class="kpi"><div class="kpi-value" style="color:{color}">
                        {filled}/{total}</div>
                        <div class="kpi-label">Filled Today ({pct:.0f}%)</div></div>""",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="kpi"><div class="kpi-value" style="font-size:14px;color:#605e5c">
                        Non-working day</div>
                        <div class="kpi-label">Today</div></div>""",
                        unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""<div class="kpi"><div class="kpi-value" style="color:#d13438">
                    {pending}</div>
                    <div class="kpi-label">Pending Today</div></div>""",
                    unsafe_allow_html=True)
    with cols[3]:
        # This week so far
        week_dates = get_week_so_far_working_days()
        expected = len(members) * len(week_dates)
        actual = sum(
            1 for e in all_entries
            if e["entry_date"] in week_dates
            and e["uid"] in [m["id"] for m in members]
        )
        # Count distinct member-day combinations filled
        filled_combos = set(
            (e["uid"], e["entry_date"]) for e in all_entries
            if e["entry_date"] in week_dates
            and e["uid"] in [m["id"] for m in members]
        )
        actual_compliance = len(filled_combos)
        st.markdown(f"""<div class="kpi"><div class="kpi-value">{actual_compliance}/{expected}</div>
                    <div class="kpi-label">This Week Compliance</div></div>""",
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ────────────────────────────────────────────
    # PENDING TODAY — quick reminder
    # ────────────────────────────────────────────
    if is_today_working and pending > 0:
        with st.expander(f"⚠️ {pending} members pending TODAY  ·  click to view & remind",
                          expanded=True):
            pending_members = [m for m in members if m["id"] not in members_filled_today]
            pending_members = sorted(pending_members, key=lambda m: m["name"])

            df = pd.DataFrame([{
                "Name": m["name"],
                "Email": m.get("email", ""),
                "Company": m.get("company", "—"),
                "Department": m.get("dept", "—"),
                "Discipline": m.get("discipline", "—"),
            } for m in pending_members])

            st.dataframe(df, use_container_width=True, hide_index=True, height=250)

            # Reminder buttons
            emails = [m.get("email", "") for m in pending_members if m.get("email")]
            email_str = ";".join(emails)

            col1, col2, col3 = st.columns(3)
            with col1:
                # Copy emails button (using markdown link)
                st.text_area("📋 Copy emails (Ctrl+A then Ctrl+C):",
                             value=email_str,
                             height=70,
                             key="pending_emails_copy")
            with col2:
                # Mailto link
                subject = f"Timesheet pending — {today.strftime('%d %b %Y')}"
                body = (
                    f"Hi,\n\n"
                    f"This is a reminder to fill your timesheet for "
                    f"{today.strftime('%A, %d %B %Y')}.\n\n"
                    f"Please log in: https://gcc-eet-timesheet.streamlit.app\n\n"
                    f"Thanks,\nGCC EET Fuels"
                )
                mailto = f"mailto:?bcc={email_str}&subject={quote(subject)}&body={quote(body)}"
                st.markdown(
                    f'<a href="{mailto}" target="_blank" style="display:block;text-align:center;'
                    f'padding:8px;background:#6264a7;color:white;border-radius:6px;'
                    f'text-decoration:none;font-weight:600">📧 Open in Email</a>',
                    unsafe_allow_html=True
                )
            with col3:
                st.caption(f"📊 {pending} of {total} pending  ·  {pct:.0f}% filled")

    # ────────────────────────────────────────────
    # WEEKLY HEAT MAP
    # ────────────────────────────────────────────
    st.markdown("#### 📅 7-Day Compliance Heat Map")
    st.caption("✅ Filled · ❌ Missed · ⬜ Future · ☀️ Weekend/Holiday")

    show_heatmap(members, all_entries, today)


def show_heatmap(members, all_entries, today):
    """Show 7-day rolling heat map of filled/missed days."""
    # Get last 7 calendar days
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]

    # Build DataFrame
    rows = []
    for m in sorted(members, key=lambda x: x["name"]):
        member_entries = set(
            e["entry_date"] for e in all_entries if e["uid"] == m["id"]
        )
        row = {
            "Name": m["name"],
            "Company": m.get("company", "—"),
            "Discipline": m.get("discipline", "—"),
        }
        for d in days:
            ds = d.strftime("%Y-%m-%d")
            day_label = d.strftime("%a %d")
            if d > today:
                row[day_label] = "⬜"
            elif d.weekday() >= 5:
                row[day_label] = "☀️"
            elif ds in HOLIDAYS_2026:
                row[day_label] = "🎉"
            elif ds in member_entries:
                row[day_label] = "✅"
            else:
                row[day_label] = "❌"

        # Calculate compliance %
        working_days_passed = [
            d for d in days
            if d <= today and d.weekday() < 5 and d.strftime("%Y-%m-%d") not in HOLIDAYS_2026
        ]
        if working_days_passed:
            filled_count = sum(
                1 for d in working_days_passed
                if d.strftime("%Y-%m-%d") in member_entries
            )
            row["%"] = f"{(filled_count / len(working_days_passed) * 100):.0f}%"
        else:
            row["%"] = "—"

        rows.append(row)

    df = pd.DataFrame(rows)

    # Show table
    st.dataframe(df, use_container_width=True, hide_index=True, height=500)

    # Member with worst compliance
    if rows:
        # Filter to only members with %s
        with_pct = [r for r in rows if r["%"] != "—" and r["%"] != "0%"]
        worst = sorted(rows, key=lambda r: int(r["%"].replace("%", "")) if r["%"].endswith("%") else 100)
        worst_filtered = [r for r in worst if r["%"].endswith("%") and int(r["%"].replace("%", "")) < 100]

        if worst_filtered:
            st.markdown("##### 🚨 Members needing attention (last 7 working days)")
            below_75 = [r for r in worst_filtered if int(r["%"].replace("%", "")) < 75]
            if below_75:
                for r in below_75[:5]:
                    st.markdown(
                        f"- **{r['Name']}** ({r['Company']}, {r['Discipline']}) — "
                        f"only **{r['%']}** filled"
                    )
            else:
                st.success("✅ All members above 75% compliance — great!")


# ════════════════════════════════════════════════════
# MEMBER HOME (non-admin)
# ════════════════════════════════════════════════════
def show_member_home(user):
    """Simple home for non-admin members."""
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    st.markdown(f"### 👋 Welcome, {user['name'].split()[0]}!")

    all_entries = db.get_entries_for_user(user["id"])

    # Today status
    is_today_working = is_working_day(today)
    today_filled = any(e["entry_date"] == today_str for e in all_entries)

    cols = st.columns(3)
    with cols[0]:
        if not is_today_working:
            status = "Non-working day"
            color = "#605e5c"
        elif today_filled:
            status = "✅ Filled"
            color = "#107c10"
        else:
            status = "⏳ Pending"
            color = "#ca5010"

        st.markdown(f"""<div class="kpi">
                    <div class="kpi-value" style="font-size:18px;color:{color}">{status}</div>
                    <div class="kpi-label">Today's Timesheet</div></div>""",
                    unsafe_allow_html=True)

    with cols[1]:
        # This week
        week_dates = get_week_so_far_working_days()
        filled_week = len(set(
            e["entry_date"] for e in all_entries if e["entry_date"] in week_dates
        ))
        st.markdown(f"""<div class="kpi">
                    <div class="kpi-value">{filled_week}/{len(week_dates)}</div>
                    <div class="kpi-label">Filled This Week</div></div>""",
                    unsafe_allow_html=True)

    with cols[2]:
        # This month total hours
        ym = today.strftime("%Y-%m")
        month_hrs = sum(
            float(e["hrs"]) for e in all_entries if e["entry_date"].startswith(ym)
        )
        st.markdown(f"""<div class="kpi">
                    <div class="kpi-value">{month_hrs:.1f}</div>
                    <div class="kpi-label">Hours {get_month_label(ym)}</div></div>""",
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Missing days alert
    if is_today_working and not today_filled:
        st.warning(f"⚠️ Your timesheet for **{today.strftime('%A, %d %B')}** is pending. "
                   "Click **My Timesheet** tab above to fill it now.")

    # Recent missed days
    missed = []
    for i in range(1, 8):
        d = today - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        if d.weekday() < 5 and ds not in HOLIDAYS_2026:
            if not any(e["entry_date"] == ds for e in all_entries):
                missed.append(d)

    if missed:
        st.markdown("#### 📅 Days you may have missed (last 7 days)")
        for d in missed:
            st.markdown(f"- **{d.strftime('%A, %d %b')}** — no entry yet")
        st.caption("Click 'My Timesheet' tab above to backfill these days.")
    else:
        st.success("✅ Great work! No missing days in the last 7 days.")


# ════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════
def is_working_day(d):
    """Mon-Fri and not a public holiday."""
    if d.weekday() >= 5:
        return False
    if d.strftime("%Y-%m-%d") in HOLIDAYS_2026:
        return False
    return True


def get_week_so_far_working_days():
    """Working days from Monday to today (or end of week if past)."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    days = []
    d = monday
    while d <= today and d.weekday() < 5:
        ds = d.strftime("%Y-%m-%d")
        if ds not in HOLIDAYS_2026:
            days.append(ds)
        d += timedelta(days=1)
    return days

