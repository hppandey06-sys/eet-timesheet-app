"""
reminders_page.py
=================
Reminder module for chasing members with missing / short timesheets.

Three views:
   1. YESTERDAY    - members with < 8 hrs filled yesterday (working days only)
   2. LAST WEEK    - members with < (working days x 8) hrs last completed week
   3. LAST MONTH   - members with < (working days x 8) hrs last completed month

Uses db.get_members() and db.get_all_entries() (existing app functions) so
schema mismatches cannot occur.

Access: admins + super_admins only.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
from urllib.parse import quote

import db

DAILY_TARGET_HOURS = 8


# -------------------------------------------------
# Helpers
# -------------------------------------------------
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


def _to_date(d):
    """Coerce a date-like value (str or date) to date."""
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return pd.to_datetime(d).date()
    return d


# -------------------------------------------------
# Core computation - uses db.get_members() and db.get_all_entries()
# -------------------------------------------------
def _fetch_entries_in_range(start, end):
    """Fetch ts_entries within [start, end] directly, paginated to bypass
    Supabase 1000-row default limit."""
    sb = db.get_client()
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        result = (sb.table("ts_entries")
                    .select("*")
                    .gte("entry_date", start.isoformat())
                    .lte("entry_date", end.isoformat())
                    .order("entry_date")
                    .range(offset, offset + page_size - 1)
                    .execute())
        batch = result.data or []
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return all_rows


def compute_shortfall(start, end):
    """For each Engineering member, compute filled vs target hrs in [start,end]."""
    members = db.get_members()
    in_range = _fetch_entries_in_range(start, end)
    target = _working_days(start, end) * DAILY_TARGET_HOURS

    # Sum hrs by uid
    hrs_by_uid = {}
    for e in in_range:
        uid = e.get('uid')
        hrs = float(e.get('hrs', 0) or 0)
        hrs_by_uid[uid] = hrs_by_uid.get(uid, 0) + hrs

    # Build rows for Engineering members only
    rows = []
    for m in members:
        if m.get('dept') != 'Engineering':
            continue
        mid = m.get('id')
        filled = hrs_by_uid.get(mid, 0)
        shortfall = max(0, target - filled)
        pct = (filled / target * 100) if target else 0
        rows.append({
            'ID': mid,
            'Name': m.get('name', ''),
            'Email': m.get('email', ''),
            'Discipline': m.get('discipline', ''),
            'Filled Hrs': round(filled, 1),
            'Target Hrs': target,
            'Shortfall': round(shortfall, 1),
            'Fill %': round(pct, 1),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(['Fill %', 'Name']).reset_index(drop=True)


def filter_below_target(df, threshold_pct=100):
    return df[df['Fill %'] < threshold_pct].copy()


# -------------------------------------------------
# Message builders
# -------------------------------------------------
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


# -------------------------------------------------
# Period renderer
# -------------------------------------------------
def _render_period(period_label, start, end, key_prefix):
    if start == end:
        period_dates = start.strftime('%d-%b-%Y')
    else:
        period_dates = start.strftime('%d-%b') + ' to ' + end.strftime('%d-%b-%Y')
    target = _working_days(start, end) * DAILY_TARGET_HOURS

    st.markdown("### " + period_label + " - " + period_dates)
    st.caption("Target = " + str(_working_days(start, end)) + " working days x "
               + str(DAILY_TARGET_HOURS) + " hrs = **" + str(target) + " hrs**")

    shortfall = compute_shortfall(start, end)
    if shortfall.empty:
        st.warning("No Engineering members found.")
        return

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
                  .map(_color, subset=['Fill %'])
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


# -------------------------------------------------
# Main entry point - call from admin_page.py
# -------------------------------------------------
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

    t1, t2, t3 = st.tabs([
        "Yesterday (" + yesterday_wd.strftime('%d-%b') + ")",
        "Last Week (" + last_mon.strftime('%d-%b') + "-" + last_sun.strftime('%d-%b') + ")",
        "Last Month (" + last_m_start.strftime('%b-%Y') + ")"
    ])

    with t1:
        _render_period("Yesterday", yesterday_wd, yesterday_wd, 'yest')
    with t2:
        _render_period("Last Week", last_mon, last_sun, 'week')
    with t3:
        _render_period("Last Month", last_m_start, last_m_end, 'month')
