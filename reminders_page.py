"""
reminders_page.py
=================
Reminder module for chasing members with missing / short timesheets.

Three views:
   1. YESTERDAY    — members with < 8 hrs filled yesterday (working days only)
   2. LAST WEEK    — members with < (working days × 8) hrs last completed week
   3. LAST MONTH   — members with < (working days × 8) hrs last completed month

For each view:
   • Filter by discipline
   • Ready-to-paste email body
   • Ready-to-paste WhatsApp message
   • Recipient email list (semicolon-separated for Outlook)
   • Excel download

Access: admins + super_admins only.

Author: Hari Pandey, GCC
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from io import BytesIO

from db import get_supabase

DAILY_TARGET_HOURS = 8


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────
def _working_days(start: date, end: date):
    n, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _last_working_day(today: date) -> date:
    """Most recent Mon-Fri before today."""
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _last_completed_week(today: date):
    """Mon-Sun bounds of the last completed ISO week."""
    this_mon = today - timedelta(days=today.weekday())
    last_mon = this_mon - timedelta(days=7)
    last_sun = last_mon + timedelta(days=6)
    return last_mon, last_sun


def _last_completed_month(today: date):
    """First and last day of the previous calendar month."""
    first_this_month = today.replace(day=1)
    last_prev = first_this_month - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


# ────────────────────────────────────────────
# Data loaders
# ────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_members():
    sb = get_supabase()
    res = sb.table('ts_members').select(
        'id,name,email,company,department,discipline,role'
    ).execute()
    df = pd.DataFrame(res.data)
    # Engineering only
    return df[df['department'] == 'Engineering'].copy()


@st.cache_data(ttl=60)
def load_entries(start: date, end: date) -> pd.DataFrame:
    sb = get_supabase()
    res = (sb.table('ts_entries')
             .select('member_id,project,activity,entry_date,hours')
             .gte('entry_date', start.isoformat())
             .lte('entry_date', end.isoformat())
             .execute())
    df = pd.DataFrame(res.data)
    if df.empty:
        return df
    df['entry_date'] = pd.to_datetime(df['entry_date']).dt.date
    df['hours'] = pd.to_numeric(df['hours'], errors='coerce').fillna(0)
    return df


# ────────────────────────────────────────────
# Core report
# ────────────────────────────────────────────
def compute_shortfall(members_df, entries_df, start: date, end: date) -> pd.DataFrame:
    """Per-member: filled hrs, target hrs, shortfall, fill %."""
    target = _working_days(start, end) * DAILY_TARGET_HOURS

    rows = []
    for _, m in members_df.iterrows():
        mid = m['id']
        filled = entries_df[entries_df['member_id'] == mid]['hours'].sum() if not entries_df.empty else 0
        shortfall = max(0, target - filled)
        pct = (filled / target * 100) if target else 0
        rows.append({
            'ID': mid,
            'Name': m['name'],
            'Email': m['email'],
            'Discipline': m['discipline'],
            'Filled Hrs': round(filled, 1),
            'Target Hrs': target,
            'Shortfall': round(shortfall, 1),
            'Fill %': round(pct, 1),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(['Fill %', 'Name']).reset_index(drop=True)


def filter_below_target(df: pd.DataFrame, threshold_pct: float = 100) -> pd.DataFrame:
    """Members with fill % below threshold."""
    return df[df['Fill %'] < threshold_pct].copy()


# ────────────────────────────────────────────
# Message templates
# ────────────────────────────────────────────
def build_email(period_label: str, period_dates: str, below_df: pd.DataFrame) -> tuple[str, str]:
    """Returns (subject, body)."""
    subject = f"Action: Timesheet pending — {period_label} ({period_dates})"
    n = len(below_df)
    body = f"""Dear Team,

Per the records on our GCC Timesheet App (gcc-eet-timesheet.streamlit.app), the following {n} engineer(s) have NOT completed the timesheet for {period_label} ({period_dates}):

"""
    for _, r in below_df.iterrows():
        body += f"  • {r['Name']:25s} — Filled {r['Filled Hrs']:.0f} / {r['Target Hrs']:.0f} hrs ({r['Fill %']:.0f}%)\n"

    body += f"""
Please update your entries by end of today.

If you are unsure how to access the app, reach out to me, Prachi, Pradeep, or Aarti.

Regards,
Hari Pandey
Deputy Engineering Head, GCC
Essar UK Services
"""
    return subject, body


def build_whatsapp(period_label: str, period_dates: str, n: int) -> str:
    return f"""⏰ *Timesheet Reminder*

{n} member(s) have not completed timesheet for *{period_label}* ({period_dates}).

Please log in and fill your hours by EOD:
🔗 gcc-eet-timesheet.streamlit.app

— Hari"""


# ────────────────────────────────────────────
# Excel export
# ────────────────────────────────────────────
def build_excel(below_df: pd.DataFrame, period_label: str) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as xw:
        below_df.to_excel(xw, sheet_name='Pending', index=False)
    out.seek(0)
    return out.read()


# ────────────────────────────────────────────
# View renderer
# ────────────────────────────────────────────
def _render_period(period_label: str, start: date, end: date, members_df, key_prefix: str):
    period_dates = (f"{start.strftime('%d-%b-%Y')}" if start == end
                    else f"{start.strftime('%d-%b')} → {end.strftime('%d-%b-%Y')}")
    target = _working_days(start, end) * DAILY_TARGET_HOURS
    st.markdown(f"### {period_label} — {period_dates}")
    st.caption(f"Target = {_working_days(start, end)} working days × {DAILY_TARGET_HOURS} hrs = **{target} hrs**")

    entries_df = load_entries(start, end)
    shortfall = compute_shortfall(members_df, entries_df, start, end)
    below = filter_below_target(shortfall, threshold_pct=100)

    # KPI strip
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Engineers", len(shortfall))
    k2.metric("Completed", (shortfall['Fill %'] >= 100).sum())
    k3.metric("Pending", len(below))
    k4.metric("Avg Fill %", f"{shortfall['Fill %'].mean():.0f}%")

    if below.empty:
        st.success(f"✅ All engineers have completed timesheets for {period_label}.")
        return

    # Discipline filter
    discs = ['(All)'] + sorted(below['Discipline'].dropna().unique().tolist())
    pick = st.selectbox("Filter by discipline", discs, key=f'{key_prefix}_disc')
    view = below if pick == '(All)' else below[below['Discipline'] == pick]

    # Colour-coded display
    def _color(v):
        try:
            v = float(v)
        except:
            return ''
        if v < 25: return 'background-color: #F8CBAD'
        if v < 75: return 'background-color: #FFE699'
        return 'background-color: #FFFFFF'

    styled = (view.style
                  .applymap(_color, subset=['Fill %'])
                  .format({'Filled Hrs': '{:.1f}', 'Shortfall': '{:.1f}', 'Fill %': '{:.0f}%'}))
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 📨 Ready-to-paste reminders")

    # Recipient list
    emails = ';'.join(view['Email'].dropna().tolist())
    cc_admins = "prachi.bhalerao@eetfuels.com;pradeep.kenjale@eetfuels.com;aarti.shitole@eetfuels.com"

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Email recipients (To:)**")
        st.code(emails, language=None)
        st.markdown("**CC (Admins)**")
        st.code(cc_admins, language=None)

    with c2:
        st.markdown("**Send via Outlook**")
        # mailto link
        subject, body = build_email(period_label, period_dates, view)
        from urllib.parse import quote
        mailto = f"mailto:{emails}?cc={cc_admins}&subject={quote(subject)}&body={quote(body[:1500])}"
        st.markdown(f"[📧 Open in Outlook (mailto)]({mailto})")
        st.caption("Note: mailto truncates after ~2000 chars. Use copy-paste below for full body.")

    # Email body
    subject, body = build_email(period_label, period_dates, view)
    st.markdown("**Email Subject**")
    st.code(subject, language=None)
    st.markdown("**Email Body**")
    st.text_area("", body, height=300, key=f'{key_prefix}_body')

    # WhatsApp
    wa = build_whatsapp(period_label, period_dates, len(view))
    st.markdown("**WhatsApp Message**")
    st.code(wa, language=None)

    # Download
    xls = build_excel(view, period_label)
    fname = f"Timesheet_Pending_{period_label.replace(' ','_')}_{start.strftime('%Y%m%d')}.xlsx"
    st.download_button("📥 Download Excel List", data=xls, file_name=fname,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=f'{key_prefix}_dl')


# ────────────────────────────────────────────
# Main render — called from admin_page.py or app.py
# ────────────────────────────────────────────
def render(current_user: dict):
    role = current_user.get('role', 'member')
    if role not in ('admin', 'super_admin'):
        st.error("⛔ This view is restricted to admins.")
        st.stop()

    st.markdown("## 📨 Timesheet Reminders")
    st.caption("Identify members with pending timesheets and generate ready-to-send reminders.")

    today = date.today()
    yesterday_wd = _last_working_day(today)
    last_mon, last_sun = _last_completed_week(today)
    last_m_start, last_m_end = _last_completed_month(today)

    members_df = load_members()

    t1, t2, t3 = st.tabs([
        f"📅 Yesterday ({yesterday_wd.strftime('%d-%b')})",
        f"📆 Last Week ({last_mon.strftime('%d-%b')}–{last_sun.strftime('%d-%b')})",
        f"🗓️ Last Month ({last_m_start.strftime('%b-%Y')})"
    ])

    with t1:
        _render_period("Yesterday", yesterday_wd, yesterday_wd, members_df, 'yest')

    with t2:
        _render_period("Last Week", last_mon, last_sun, members_df, 'week')

    with t3:
        _render_period("Last Month", last_m_start, last_m_end, members_df, 'month')
