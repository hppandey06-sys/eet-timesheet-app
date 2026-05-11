"""
reminders_page.py
=================
Reminder module for chasing members with missing / short timesheets.

Three views:
   1. YESTERDAY    - members with < 8 hrs filled yesterday (working days only)
   2. LAST WEEK    - members with < (working days x 8) hrs last completed week
   3. LAST MONTH   - members with < (working days x 8) hrs last completed month

Access: admins + super_admins only.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
from urllib.parse import quote

import db

DAILY_TARGET_HOURS = 8


def _get_sb():
    """Return Supabase client regardless of how db.py exposes it."""
    candidates = ['get_supabase', 'get_client', 'get_supabase_client',
                  'supabase_client', 'client']
    for fn_name in candidates:
        if hasattr(db, fn_name):
            attr = getattr(db, fn_name)
            return attr() if callable(attr) else attr
    if hasattr(db, 'supabase'):
        return db.supabase
    raise ImportError(
        "reminders_page.py could not find a Supabase client in db.py. "
        "Expected one of: get_supabase(), get_client(), get_supabase_client(), "
        "supabase_client(), client(), or a 'supabase' attribute."
    )


# Helpers
def _working_days(start, end):
    n, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _last_working_day(today):
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _last_completed_week(today):
    this_mon = today - timedelta(days=today.weekday())
    last_mon = this_mon - timedelta(days=7)
    last_sun = last_mon + timedelta(days=6)
    return last_mon, last_sun


def _last_completed_month(today):
    first_this_month = today.replace(day=1)
    last_prev = first_this_month - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


@st.cache_data(ttl=300)
def load_members():
    sb = _get_sb()
    res = sb.table('ts_members').select(
        'id,name,email,company,department,discipline,role'
    ).execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return df
    return df[df['department'] == 'Engineering'].copy()


@st.cache_data(ttl=60)
def load_entries(start, end):
    sb = _get_sb()
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


def compute_shortfall(members_df, entries_df, start, end):
    target = _working_days(start, end) * DAILY_TARGET_HOURS
    rows = []
    for _, m in members_df.iterrows():
        mid = m['id']
        if entries_df.empty:
            filled = 0
        else:
            filled = entries_df[entries_df['member_id'] == mid]['hours'].sum()
        shortfall = max(0, target - filled)
        pct = (filled / target * 100) if target else 0
        rows.append({
            'ID': mid,
            'Name': m['name'],
            'Email': m.get('email', ''),
            'Discipline': m.get('discipline', ''),
            'Filled Hrs': round(filled, 1),
            'Target Hrs': target,
            'Shortfall': round(shortfall, 1),
            'Fill %': round(pct, 1),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(['Fill %', 'Name']).reset_index(drop=True)


def filter_below_target(df, threshold_pct=100):
    return df[df['Fill %'] < threshold_pct].copy()


def build_email(period_label, period_dates, below_df):
    subject = "Action: Timesheet pending - " + period_label + " (" + period_dates + ")"
    n = len(below_df)
    body = "Dear Team,\n\n"
    body += ("Per the records on our GCC Timesheet App (gcc-eet-timesheet.streamlit.app), "
             "the following " + str(n) + " engineer(s) have NOT completed the timesheet for "
             + period_label + " (" + period_dates + "):\n\n")
    for _, r in below_df.iterrows():
        body += ("  - " + str(r['Name']) + " - Filled "
                 + str(int(r['Filled Hrs'])) + " / " + str(int(r['Target Hrs']))
                 + " hrs (" + str(int(r['Fill %'])) + "%)\n")
    body += ("\nPlease update your entries by end of today.\n\n"
             "If you are unsure how to access the app, reach out to me, Prachi, Pradeep, or Aarti.\n\n"
             "Regards,\nHari Pandey\nDeputy Engineering Head, GCC\nEssar UK Services\n")
    return subject, body


def build_whatsapp(period_label, period_dates, n):
    return ("Timesheet Reminder\n\n"
            + str(n) + " member(s) have not completed timesheet for *" + period_label
            + "* (" + period_dates + ").\n\n"
            "Please log in and fill your hours by EOD:\n"
            "gcc-eet-timesheet.streamlit.app\n\n- Hari")


def build_excel(below_df):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as xw:
        below_df.to_excel(xw, sheet_name='Pending', index=False)
    out.seek(0)
    return out.read()


def _render_period(period_label, start, end, members_df, key_prefix):
    if start == end:
        period_dates = start.strftime('%d-%b-%Y')
    else:
        period_dates = start.strftime('%d-%b') + ' to ' + end.strftime('%d-%b-%Y')
    target = _working_days(start, end) * DAILY_TARGET_HOURS

    st.markdown("### " + period_label + " - " + period_dates)
    st.caption("Target = " + str(_working_days(start, end)) + " working days x "
               + str(DAILY_TARGET_HOURS) + " hrs = **" + str(target) + " hrs**")

    entries_df = load_entries(start, end)
    shortfall = compute_shortfall(members_df, entries_df, start, end)
    below = filter_below_target(shortfall, threshold_pct=100)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Engineers", len(shortfall))
    k2.metric("Completed", int((shortfall['Fill %'] >= 100).sum()))
    k3.metric("Pending", len(below))
    k4.metric("Avg Fill %", str(int(shortfall['Fill %'].mean())) + "%")

    if below.empty:
        st.success("All engineers have completed timesheets for " + period_label + ".")
        return

    discs = ['(All)'] + sorted(below['Discipline'].dropna().unique().tolist())
    pick = st.selectbox("Filter by discipline", discs, key=key_prefix + '_disc')
    view = below if pick == '(All)' else below[below['Discipline'] == pick]

    def _color(v):
        try:
            v = float(v)
        except Exception:
            return ''
        if v < 25:
            return 'background-color: #F8CBAD'
        if v < 75:
            return 'background-color: #FFE699'
        return 'background-color: #FFFFFF'

    styled = (view.style
                  .applymap(_color, subset=['Fill %'])
                  .format({'Filled Hrs': '{:.1f}',
                           'Shortfall': '{:.1f}',
                           'Fill %': '{:.0f}%'}))
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Ready-to-paste reminders")

    emails = ';'.join([e for e in view['Email'].dropna().tolist() if e])
    cc_admins = ("prachi.bhalerao@eetfuels.com;pradeep.kenjale@eetfuels.com;"
                 "aarti.shitole@eetfuels.com")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Email recipients (To:)**")
        st.code(emails or '(no emails on file)', language=None)
        st.markdown("**CC (Admins)**")
        st.code(cc_admins, language=None)
    with c2:
        subject, body = build_email(period_label, period_dates, view)
        st.markdown("**Send via Outlook**")
        mailto = ("mailto:" + emails + "?cc=" + cc_admins
                  + "&subject=" + quote(subject) + "&body=" + quote(body[:1500]))
        st.markdown("[Open in Outlook (mailto)](" + mailto + ")")
        st.caption("mailto truncates after ~2000 chars. Use copy-paste below for full body.")

    subject, body = build_email(period_label, period_dates, view)
    st.markdown("**Email Subject**")
    st.code(subject, language=None)
    st.markdown("**Email Body**")
    st.text_area("Email body", body, height=300, key=key_prefix + '_body',
                 label_visibility='collapsed')

    wa = build_whatsapp(period_label, period_dates, len(view))
    st.markdown("**WhatsApp Message**")
    st.code(wa, language=None)

    xls = build_excel(view)
    fname = ("Timesheet_Pending_" + period_label.replace(' ', '_') + "_"
             + start.strftime('%Y%m%d') + ".xlsx")
    st.download_button("Download Excel List", data=xls, file_name=fname,
                       mime=("application/vnd.openxmlformats-officedocument."
                             "spreadsheetml.sheet"),
                       key=key_prefix + '_dl')


def render(current_user=None):
    if current_user is None:
        current_user = st.session_state.get('user', {})
    role = current_user.get('role', 'member') if current_user else 'member'
    if role not in ('admin', 'super_admin'):
        st.error("This view is restricted to admins.")
        st.stop()

    st.markdown("## Timesheet Reminders")
    st.caption("Identify members with pending timesheets and generate ready-to-send reminders.")

    today = date.today()
    yesterday_wd = _last_working_day(today)
    last_mon, last_sun = _last_completed_week(today)
    last_m_start, last_m_end = _last_completed_month(today)

    members_df = load_members()
    if members_df.empty:
        st.warning("No Engineering members found in database.")
        return

    t1, t2, t3 = st.tabs([
        "Yesterday (" + yesterday_wd.strftime('%d-%b') + ")",
        "Last Week (" + last_mon.strftime('%d-%b') + "-" + last_sun.strftime('%d-%b') + ")",
        "Last Month (" + last_m_start.strftime('%b-%Y') + ")"
    ])

    with t1:
        _render_period("Yesterday", yesterday_wd, yesterday_wd, members_df, 'yest')
    with t2:
        _render_period("Last Week", last_mon, last_sun, members_df, 'week')
    with t3:
        _render_period("Last Month", last_m_start, last_m_end, members_df, 'month')
