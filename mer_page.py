"""
mer_page.py
===========
Monthly Engineering Review (MER) module — Delivery 2.

Provides:
  • OVERVIEW tab  — combined cockpit (timesheet KPIs + meeting data + flags)
  • PREP tab      — discipline lead inputs before each monthly meeting
  • MEETING tab   — (placeholder, Delivery 3)
  • REPORT tab    — (placeholder, Delivery 3)

Permission model:
  • OWNER (HP)              → full access, can grant/revoke super admin
  • SUPER_ADMIN             → full access (no permission grants)
  • DISCIPLINE LEAD         → PREP tab only (own discipline section)
  • OTHER MEMBER            → hidden / no access

Reads from:
  ts_members, ts_entries, ts_projects,
  ts_mer_meetings, ts_mer_inputs, ts_mer_actions,
  ts_mer_decisions, ts_mer_attendance, ts_mer_super_admins
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import json
import re

import db


# ════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════

CAT_COLORS = {
    'DESIGN':  '#0F6E56',
    'REVIEW':  '#185FA5',
    'COORD':   '#7F77DD',
    'DOC':     '#BA7517',
    'ADMIN':   '#888880',
    'LEAVE':   '#5DCAA5',
    'UNCLASS': '#A32D2D',
}
CAT_ORDER = ['DESIGN', 'REVIEW', 'COORD', 'DOC', 'ADMIN', 'LEAVE', 'UNCLASS']
CAT_LABEL = {
    'DESIGN': 'Design',
    'REVIEW': 'Review',
    'COORD': 'Coordination',
    'DOC': 'Documentation',
    'ADMIN': 'Admin',
    'LEAVE': 'Leave',
    'UNCLASS': '⚠ Unclassified',
}

STATE_LABEL = {
    'DRAFT': '📋 Draft',
    'PREP_OPEN': '📝 PREP OPEN',
    'PREP_CLOSED': '🔒 PREP CLOSED',
    'IN_MEETING': '🗓 IN MEETING',
    'COMPLETED': '✅ COMPLETED',
    'PUBLISHED': '📤 PUBLISHED',
    'ARCHIVED': '🗄 ARCHIVED',
}


# ════════════════════════════════════════════════════
# ACTIVITY CLASSIFICATION (categorise raw activities)
# Reused from productivity dashboard design.
# ════════════════════════════════════════════════════

def classify_activity(activity_str, description_str=""):
    """Return one of: DESIGN, REVIEW, COORD, DOC, ADMIN, LEAVE, UNCLASS."""
    a = str(activity_str or "").strip()
    d = str(description_str or "").strip()
    a_low = a.lower()
    d_low = d.lower()

    # Leave / Holiday
    if 'leave' in a_low or a_low == 'hol' or 'holiday' in a_low:
        return 'LEAVE'

    # Admin (internal / low-value)
    if any(k in a_low for k in ['tool box', 'idle', 'training', 'sap', 'self learning']):
        return 'ADMIN'

    # Try discipline-code patterns first
    code_patterns = [
        (r'^prs[-_]?0?[12]$', 'DESIGN'),
        (r'^prs[-_]?0?[45]$', 'REVIEW'),
        (r'^prs[-_]?0?[789]$', 'DESIGN'),
        (r'^prs[-_]?1[01]$', 'COORD'),
        (r'^civ[-_]?0?[1-4]$', 'DESIGN'),
        (r'^civ[-_]?0?[5-7]$', 'REVIEW'),
        (r'^civ[-_]?0?8$', 'COORD'),
        (r'^civ[-_]?0?9$', 'DOC'),
        (r'^civ[-_]?1[01]$', 'COORD'),
        (r'^elec[-_]?0?[1-4]$', 'DESIGN'),
        (r'^elec[-_]?0?[5-8]$', 'REVIEW'),
        (r'^elec[-_]?0?9$', 'COORD'),
        (r'^elec[-_]?1[01]$', 'DOC'),
        (r'^inst[-_]?0?[1-3]$', 'DESIGN'),
        (r'^inst[-_]?0?[4-5]$', 'REVIEW'),
        (r'^mech[-_]?0?[1-3]$', 'DESIGN'),
        (r'^mech[-_]?0?4$', 'REVIEW'),
        (r'^mech[-_]?0?6$', 'COORD'),
        (r'^mech[-_]?0?[7-9]$', 'DESIGN'),
        (r'^mech[-_]?10$', 'REVIEW'),
        (r'^mech[-_]?1[12]$', 'COORD'),
        (r'^ms[-_]?0?[1-2]$', 'DESIGN'),
        (r'^ms[-_]?0?[3-4]$', 'REVIEW'),
        (r'^mr[-_]?0?[1-2]$', 'DESIGN'),
        (r'^mr[-_]?0?3$', 'REVIEW'),
        (r'^pip[-_]?0?[1-3]$', 'DESIGN'),
        (r'^hse[-_]?0?\d$', 'REVIEW'),
        (r'^doc[-_]?0?\d$', 'DOC'),
    ]
    for pat, cat in code_patterns:
        if re.match(pat, a_low):
            return cat

    # Free-text activity name
    if any(k in a_low for k in ['mto', '3d model', 'drawing', 'iso', 'isometric',
                                  'layout', 'plot plan', 'sld', 'datasheet', 'spec',
                                  'calc', 'p&id', 'load list', 'mds', 'pms', 'vds']):
        return 'DESIGN'
    if any(k in a_low for k in ['vendor', 'offer', 'rfq', 'tbe', 'quer', 'meeting',
                                  'contractor', 'tq', 'discussion']):
        return 'COORD'
    if 'review' in a_low or 'check' in a_low or 'verif' in a_low:
        return 'REVIEW'
    if any(k in a_low for k in ['mdr', 'mom', 'minutes', 'report', 'planning']):
        return 'DOC'

    # OTHERS / blank — fall back to description text
    if any(k in d_low for k in ['mto', 'drawing', 'iso', 'spec', 'datasheet',
                                  'calc', 'p&id', 'layout', 'model', 'sld']):
        return 'DESIGN'
    if any(k in d_low for k in ['vendor', 'offer', 'rfq', 'tbe', 'quer',
                                  'meeting', 'tq']):
        return 'COORD'
    if 'review' in d_low or 'check' in d_low or 'verif' in d_low:
        return 'REVIEW'
    if any(k in d_low for k in ['mdr', 'mom', 'report', 'minutes']):
        return 'DOC'

    return 'UNCLASS'


# ════════════════════════════════════════════════════
# DATA LOADERS  (cached)
# ════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def load_meeting_by_id(meeting_id):
    sb = db.get_client()
    r = sb.table('ts_mer_meetings').select('*').eq('id', meeting_id).execute()
    return r.data[0] if r.data else None


@st.cache_data(ttl=60)
def load_current_meeting():
    """Return the most recent DRAFT/PREP_OPEN/PREP_CLOSED/IN_MEETING meeting."""
    sb = db.get_client()
    r = (sb.table('ts_mer_meetings')
           .select('*')
           .in_('status', ['DRAFT', 'PREP_OPEN', 'PREP_CLOSED', 'IN_MEETING'])
           .order('meeting_no', desc=True)
           .limit(1)
           .execute())
    return r.data[0] if r.data else None


@st.cache_data(ttl=60)
def load_all_meetings():
    sb = db.get_client()
    r = sb.table('ts_mer_meetings').select('*').order('meeting_no', desc=True).execute()
    return r.data or []


@st.cache_data(ttl=60)
def load_inputs_for_meeting(meeting_id):
    sb = db.get_client()
    r = sb.table('ts_mer_inputs').select('*').eq('meeting_id', meeting_id).execute()
    return r.data or []


def load_input_for_discipline(meeting_id, discipline):
    """Not cached — for live editing in PREP tab."""
    sb = db.get_client()
    r = (sb.table('ts_mer_inputs')
           .select('*')
           .eq('meeting_id', meeting_id)
           .eq('discipline', discipline)
           .execute())
    return r.data[0] if r.data else None


@st.cache_data(ttl=60)
def load_open_actions():
    sb = db.get_client()
    r = (sb.table('ts_mer_actions')
           .select('*')
           .in_('status', ['OPEN', 'IN_PROGRESS'])
           .order('due_date')
           .execute())
    return r.data or []


@st.cache_data(ttl=120)
def load_entries_for_month(year, month):
    """All entries for a given month, paginated."""
    sb = db.get_client()
    start = date(year, month, 1).isoformat()
    if month == 12:
        end = date(year + 1, 1, 1).isoformat()
    else:
        end = date(year, month + 1, 1).isoformat()
    # Use the existing pagination helper if available, else paginate locally
    all_rows = []
    offset = 0
    while True:
        r = (sb.table('ts_entries')
               .select('*')
               .gte('entry_date', start)
               .lt('entry_date', end)
               .order('entry_date')
               .order('id')
               .range(offset, offset + 999)
               .execute())
        batch = r.data or []
        all_rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return all_rows


# ════════════════════════════════════════════════════
# PERMISSION HELPERS
# ════════════════════════════════════════════════════

def get_user_role(user):
    """Return one of: OWNER, SUPER_ADMIN, DISCIPLINE_LEAD, MEMBER."""
    if not user:
        return 'NONE'
    if user.get('is_owner'):
        return 'OWNER'
    if user.get('is_super_admin'):
        return 'SUPER_ADMIN'
    if user.get('is_discipline_lead'):
        return 'DISCIPLINE_LEAD'
    return 'MEMBER'


def can_access_mer(user):
    role = get_user_role(user)
    return role in ('OWNER', 'SUPER_ADMIN', 'DISCIPLINE_LEAD')


def can_access_admin_tabs(user):
    """OVERVIEW / MEETING / REPORT — super admins only."""
    role = get_user_role(user)
    return role in ('OWNER', 'SUPER_ADMIN')


# ════════════════════════════════════════════════════
# OVERVIEW TAB
# ════════════════════════════════════════════════════

def render_overview_tab(meeting, user):
    """Combined cockpit — timesheet + meeting data."""
    review_month = meeting['review_month']  # 'YYYY-MM'
    year, month = map(int, review_month.split('-'))
    month_name = date(year, month, 1).strftime('%B %Y')

    # Cycle banner
    sched = meeting.get('scheduled_date', '')
    prep_close = meeting.get('prep_closes_at', '')
    cycle_text = f"📅 **Monthly cycle:** Review month = {month_name} · "
    if sched:
        cycle_text += f"Meeting scheduled: **{sched}** · "
    cycle_text += f"Status: {STATE_LABEL.get(meeting['status'], meeting['status'])}"
    st.markdown(
        f"<div style='background:#F0F7FB;padding:10px 14px;border-radius:8px;"
        f"font-size:12px;color:#185FA5;margin-bottom:12px;'>{cycle_text}</div>",
        unsafe_allow_html=True
    )

    # ── Load and process timesheet data ──
    entries = load_entries_for_month(year, month)
    members = db.get_members()

    if not entries:
        st.warning(f"No timesheet entries for {month_name}.")
        return

    df = pd.DataFrame(entries)
    df['Hours'] = df['hrs'].astype(float)
    df['Description'] = df['description'].fillna('').astype(str)

    # Build member lookup
    mem_lookup = {m['id']: m for m in members}
    df['member_name'] = df['uid'].map(lambda u: mem_lookup.get(u, {}).get('name', f'uid:{u}'))
    df['discipline'] = df['uid'].map(lambda u: mem_lookup.get(u, {}).get('discipline', '-'))

    # Exclude leadership (HP + Sangeeta) from productivity numbers
    excluded_uids = {m['id'] for m in members if m.get('excluded_from_productivity')}
    df_eng = df[~df['uid'].isin(excluded_uids)].copy()

    # Classify each entry
    df_eng['Category'] = df_eng.apply(
        lambda r: classify_activity(r['act'], r['Description']), axis=1
    )

    # ── Section 1: Month KPIs ──
    st.markdown("### ① Month KPIs <span style='font-size:11px;color:#666;'>(from timesheet)</span>",
                unsafe_allow_html=True)

    total_hrs = df_eng['Hours'].sum()
    n_reporting = df_eng['uid'].nunique()
    eng_members_total = sum(
        1 for m in members
        if m.get('dept') == 'Engineering' and m['id'] not in excluded_uids
    )
    n_projects = df_eng['proj'].nunique()

    cat_totals = df_eng.groupby('Category')['Hours'].sum()
    hv = sum(cat_totals.get(c, 0) for c in ['DESIGN', 'REVIEW', 'COORD'])
    hv_pct = hv / total_hrs * 100 if total_hrs else 0
    unclass = cat_totals.get('UNCLASS', 0)
    unclass_pct = unclass / total_hrs * 100 if total_hrs else 0
    leave = cat_totals.get('LEAVE', 0)
    leave_pct = leave / total_hrs * 100 if total_hrs else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Hours filled", f"{total_hrs:,.0f}")
    c2.metric("Reporting", f"{n_reporting} / {eng_members_total}")
    c3.metric("Projects active", n_projects)
    c4.metric("High-value", f"{hv_pct:.0f}%", help="Design + Review + Coord")
    c5.metric("Unclassified", f"{unclass_pct:.0f}%",
              delta_color="inverse",
              help="Data quality flag — OTHERS or blank descriptions")
    c6.metric("Leave", f"{leave_pct:.0f}%")

    st.markdown("---")

    # ── Section 2: Discipline activity profile ──
    st.markdown("### ② Discipline Activity Profile <span style='font-size:11px;color:#666;'>(category mix)</span>",
                unsafe_allow_html=True)

    disc_summary = (df_eng.groupby('discipline')
                          .agg(Hours=('Hours', 'sum'), Members=('uid', 'nunique'))
                          .reset_index()
                          .sort_values('Hours', ascending=False))

    for _, row in disc_summary.iterrows():
        d = row['discipline']
        sub = df_eng[df_eng['discipline'] == d]
        cat_mix = sub.groupby('Category')['Hours'].sum()
        total = sub['Hours'].sum()
        if total == 0:
            continue
        cols = st.columns([2, 1, 5])
        cols[0].markdown(f"**{d}**")
        cols[1].markdown(f"{int(row['Hours'])}h · {int(row['Members'])} members")
        # Build a horizontal bar
        bar_html = '<div style="display:flex;height:18px;border-radius:4px;overflow:hidden;background:#eee;">'
        for c in CAT_ORDER:
            v = cat_mix.get(c, 0)
            if v > 0:
                pct = v / total * 100
                bar_html += (
                    f'<div style="width:{pct:.0f}%;background:{CAT_COLORS[c]};'
                    f'color:white;font-size:10px;display:flex;align-items:center;'
                    f'justify-content:center;font-weight:500;" '
                    f'title="{CAT_LABEL[c]}: {int(v)}h">{pct:.0f}%</div>'
                )
        bar_html += '</div>'
        cols[2].markdown(bar_html, unsafe_allow_html=True)

    # Legend
    legend_html = '<div style="margin-top:6px;font-size:10px;">'
    for c in CAT_ORDER:
        legend_html += (
            f'<span style="display:inline-block;margin-right:10px;">'
            f'<span style="display:inline-block;width:10px;height:10px;'
            f'background:{CAT_COLORS[c]};vertical-align:middle;border-radius:2px;"></span> '
            f'{CAT_LABEL[c]}</span>'
        )
    legend_html += '</div>'
    st.markdown(legend_html, unsafe_allow_html=True)

    st.markdown("---")

    # ── Section 3: Data Quality Flags ──
    st.markdown("### ③ Data Quality Flags")
    st.caption("Members with timesheet hygiene issues. Discipline leads see only their team.")

    role = get_user_role(user)
    is_admin = role in ('OWNER', 'SUPER_ADMIN')

    # For each engineering member, compute flag
    flags = []
    eng_members = [m for m in members
                   if m.get('dept') == 'Engineering'
                   and m['id'] not in excluded_uids]
    
    for m in eng_members:
        mid = m['id']
        sub = df_eng[df_eng['uid'] == mid]
        m_hrs = sub['Hours'].sum()
        if m_hrs == 0:
            flags.append({
                'Discipline': m.get('discipline', '-'),
                'Member': m['name'],
                'Issue': '🔴 0 hrs filled',
                'severity': 3,
            })
            continue
        # Hours on OTHERS / unclassified
        unclass_h = sub[sub['Category'] == 'UNCLASS']['Hours'].sum()
        unclass_pct = unclass_h / m_hrs * 100
        # Blank descriptions
        n_entries = len(sub)
        n_blank = (sub['Description'].str.len() < 5).sum()
        blank_pct = n_blank / n_entries * 100 if n_entries else 0

        if unclass_pct > 50:
            flags.append({
                'Discipline': m.get('discipline', '-'),
                'Member': m['name'],
                'Issue': f'🔴 {unclass_pct:.0f}% on OTHERS',
                'severity': 3,
            })
        elif unclass_pct > 25:
            flags.append({
                'Discipline': m.get('discipline', '-'),
                'Member': m['name'],
                'Issue': f'🟡 {unclass_pct:.0f}% on OTHERS',
                'severity': 2,
            })
        elif blank_pct > 50:
            flags.append({
                'Discipline': m.get('discipline', '-'),
                'Member': m['name'],
                'Issue': f'🟡 {blank_pct:.0f}% blank descriptions',
                'severity': 2,
            })

    # Filter by discipline if lead
    if not is_admin and role == 'DISCIPLINE_LEAD':
        my_disc = user.get('leads_discipline', '')
        flags = [f for f in flags if f['Discipline'] == my_disc]

    if flags:
        df_flags = pd.DataFrame(flags).sort_values('severity', ascending=False).drop(columns=['severity'])
        st.dataframe(df_flags, use_container_width=True, hide_index=True)
        st.caption(f"🔴 Red: 0 hrs or >50% on OTHERS · 🟡 Amber: 25-50% · 🟢 Green: <25% · "
                   f"Total flagged: {len(flags)} of {len(eng_members)} reporting")
    else:
        st.success("✅ No data quality flags this month — clean reporting!")

    st.markdown("---")

    # ── Section 4: Open Action Items ──
    st.markdown("### ④ Open Action Items <span style='font-size:11px;color:#666;'>(across all meetings)</span>",
                unsafe_allow_html=True)

    actions = load_open_actions()
    if actions:
        adf = pd.DataFrame(actions)
        today = date.today()
        adf['_due'] = pd.to_datetime(adf['due_date']).dt.date
        adf['Status'] = adf.apply(
            lambda r: ('🔴 Overdue' if r['_due'] and r['_due'] < today
                       else '🟡 Due Soon' if r['_due'] and (r['_due'] - today).days <= 7
                       else '🟢 On Track'), axis=1)
        adf_show = adf[['Status', 'action_text', 'owner_name', 'due_date', 'discipline', 'source_phase']]
        adf_show.columns = ['Status', 'Action', 'Owner', 'Due', 'Discipline', 'Raised in']
        st.dataframe(adf_show, use_container_width=True, hide_index=True)
        st.caption(f"Total open: {len(actions)} · "
                   f"Overdue: {sum(1 for a in actions if a.get('due_date') and pd.to_datetime(a['due_date']).date() < today)}")
    else:
        st.info("No open action items.")

    st.markdown("---")

    # ── Section 5: PREP Submission Status ──
    st.markdown("### ⑤ PREP Submission Status")

    inputs = load_inputs_for_meeting(meeting['id'])
    submitted_discs = {i['discipline']: i for i in inputs}

    all_disciplines = sorted(set(
        m['leads_discipline'] for m in members
        if m.get('is_discipline_lead') and m.get('leads_discipline')
    ))

    cols = st.columns(min(4, max(1, len(all_disciplines))))
    for i, d in enumerate(all_disciplines):
        col = cols[i % len(cols)]
        if d in submitted_discs:
            sub_status = submitted_discs[d].get('status', 'DRAFT')
            if sub_status == 'SUBMITTED':
                col.markdown(f"✅ **{d}**  \n<span style='font-size:10px;color:#0F6E56;'>submitted</span>",
                             unsafe_allow_html=True)
            elif sub_status == 'LATE':
                col.markdown(f"⚠️ **{d}**  \n<span style='font-size:10px;color:#A32D2D;'>LATE</span>",
                             unsafe_allow_html=True)
            else:
                col.markdown(f"📝 **{d}**  \n<span style='font-size:10px;color:#BA7517;'>draft</span>",
                             unsafe_allow_html=True)
        else:
            col.markdown(f"⏳ **{d}**  \n<span style='font-size:10px;color:#888;'>pending</span>",
                         unsafe_allow_html=True)

    n_submitted = sum(1 for i in inputs if i.get('status') == 'SUBMITTED')
    n_late = sum(1 for i in inputs if i.get('status') == 'LATE')
    n_pending = len(all_disciplines) - len(submitted_discs)
    st.caption(f"{n_submitted} submitted · {n_late} late · {n_pending} pending · "
               f"Deadline: {meeting.get('prep_closes_at', 'TBD')[:10] if meeting.get('prep_closes_at') else 'TBD'}")

    # ── Super Admin section ──
    if role == 'OWNER':
        st.markdown("---")
        with st.expander("🔒 Super Admin Permissions (owner only)", expanded=False):
            sb = db.get_client()
            r = (sb.table('ts_mer_super_admins')
                   .select('*, member:ts_members!member_id(name)')
                   .eq('is_active', True)
                   .execute())
            sa_data = r.data or []
            if sa_data:
                rows = []
                for sa in sa_data:
                    mem = sa.get('member', {}) or {}
                    rows.append({
                        'Name': mem.get('name', '?'),
                        'Role': sa['role'],
                        'Granted on': sa.get('granted_at', '')[:10] if sa.get('granted_at') else '',
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption("To add a new super admin, contact HP via the Admin tab (Delivery 3 will add UI here).")


# ════════════════════════════════════════════════════
# PREP TAB
# ════════════════════════════════════════════════════

def render_prep_tab(meeting, user):
    """Discipline lead inputs for the meeting."""
    role = get_user_role(user)

    # Header
    st.markdown(f"### 📝 PREP — Meeting #{meeting['meeting_no']} ({meeting['review_month']})")
    st.caption(
        f"Status: {STATE_LABEL.get(meeting['status'], meeting['status'])} · "
        f"Closes: {meeting.get('prep_closes_at', 'TBD')[:16] if meeting.get('prep_closes_at') else 'TBD'} · "
        f"Meeting: {meeting.get('scheduled_date', 'TBD')}"
    )

    # Determine which discipline to show
    if role == 'DISCIPLINE_LEAD':
        # Lead sees only own discipline
        my_disc = user.get('leads_discipline', '')
        if not my_disc:
            st.error("You are flagged as a discipline lead but no discipline is set. Contact HP.")
            return
        active_disc = my_disc
        st.info(f"You are submitting for: **{active_disc}**")
    else:
        # Admin sees discipline picker
        members = db.get_members()
        all_disciplines = sorted(set(
            m['leads_discipline'] for m in members
            if m.get('is_discipline_lead') and m.get('leads_discipline')
        ))
        # Use selectbox with admin's choice
        inputs = load_inputs_for_meeting(meeting['id'])
        submitted_lookup = {i['discipline']: i.get('status', 'DRAFT') for i in inputs}
        disc_labels = [f"{d} ({submitted_lookup.get(d, 'pending')})" for d in all_disciplines]
        pick = st.selectbox(
            "View discipline:",
            range(len(all_disciplines)),
            format_func=lambda i: disc_labels[i],
            key='mer_prep_disc_pick'
        )
        active_disc = all_disciplines[pick]

    st.markdown("---")

    # ── Auto-filled timesheet stats for this discipline ──
    year, month = map(int, meeting['review_month'].split('-'))
    entries = load_entries_for_month(year, month)
    members = db.get_members()
    mem_lookup = {m['id']: m for m in members}

    df = pd.DataFrame(entries) if entries else pd.DataFrame()
    if len(df):
        df['Hours'] = df['hrs'].astype(float)
        df['Description'] = df['description'].fillna('').astype(str)
        df['discipline'] = df['uid'].map(lambda u: mem_lookup.get(u, {}).get('discipline', '-'))
        df_disc = df[df['discipline'] == active_disc]
    else:
        df_disc = pd.DataFrame()

    if len(df_disc):
        total_hrs = df_disc['Hours'].sum()
        n_members = df_disc['uid'].nunique()
        top_project_g = df_disc.groupby('proj')['Hours'].sum().sort_values(ascending=False)
        top_project = top_project_g.index[0] if len(top_project_g) else '-'
        top_proj_hrs = top_project_g.iloc[0] if len(top_project_g) else 0

        df_disc['Category'] = df_disc.apply(
            lambda r: classify_activity(r['act'], r['Description']), axis=1
        )
        cat_tot = df_disc.groupby('Category')['Hours'].sum()
        hv = sum(cat_tot.get(c, 0) for c in ['DESIGN', 'REVIEW', 'COORD'])
        hv_pct = hv / total_hrs * 100 if total_hrs else 0
    else:
        total_hrs = n_members = top_proj_hrs = 0
        top_project = '-'
        cat_tot = pd.Series(dtype=float)
        hv_pct = 0

    st.markdown("##### 🤖 Auto-filled from timesheet")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total hrs", f"{total_hrs:,.0f}")
    c2.metric("Members reporting", n_members)
    c3.metric("Top project", top_project, help=f"{top_proj_hrs:.0f} hrs")
    c4.metric("High-value", f"{hv_pct:.0f}%")

    # Category mix bar
    if total_hrs > 0:
        bar_html = '<div style="display:flex;height:16px;border-radius:4px;overflow:hidden;margin-top:6px;background:#eee;">'
        for c in CAT_ORDER:
            v = cat_tot.get(c, 0)
            if v > 0:
                pct = v / total_hrs * 100
                bar_html += (
                    f'<div style="width:{pct:.0f}%;background:{CAT_COLORS[c]};'
                    f'color:white;font-size:10px;display:flex;align-items:center;'
                    f'justify-content:center;" title="{CAT_LABEL[c]}: {int(v)}h">{pct:.0f}%</div>'
                )
        bar_html += '</div>'
        st.markdown(bar_html, unsafe_allow_html=True)

    # ── Data quality flags for this team ──
    eng_members = [m for m in members
                   if m.get('discipline') == active_disc
                   and m.get('dept') == 'Engineering'
                   and not m.get('excluded_from_productivity')]

    flags = []
    for m in eng_members:
        mid = m['id']
        sub = df_disc[df_disc['uid'] == mid] if len(df_disc) else pd.DataFrame()
        m_hrs = sub['Hours'].sum() if len(sub) else 0
        if m_hrs == 0:
            flags.append(f"🔴 **{m['name']}** — 0 hrs filled")
            continue
        unclass_h = sub[sub['Category'] == 'UNCLASS']['Hours'].sum() if len(sub) else 0
        unclass_pct = unclass_h / m_hrs * 100 if m_hrs else 0
        if unclass_pct > 50:
            flags.append(f"🔴 **{m['name']}** — {unclass_pct:.0f}% on OTHERS")
        elif unclass_pct > 25:
            flags.append(f"🟡 **{m['name']}** — {unclass_pct:.0f}% on OTHERS")

    if flags:
        with st.expander(f"⚠ Data quality flags for {active_disc} ({len(flags)} members)", expanded=True):
            for f in flags:
                st.markdown(f"- {f}")
            st.caption("Chase these members before PREP closes.")

    st.markdown("---")

    # ── Manual input fields ──
    st.markdown("##### ✏️ Your discipline inputs")

    # Load existing submission if any
    existing = load_input_for_discipline(meeting['id'], active_disc)

    can_edit = (
        meeting['status'] in ('DRAFT', 'PREP_OPEN', 'PREP_CLOSED')  # allow LATE
        and (role in ('OWNER', 'SUPER_ADMIN')
             or (role == 'DISCIPLINE_LEAD' and active_disc == user.get('leads_discipline')))
    )

    if not can_edit:
        st.warning("View-only mode (you don't have edit rights for this discipline or meeting is closed).")

    # Form
    with st.form(key=f"prep_form_{active_disc}_{meeting['id']}"):
        key_activities = st.text_area(
            "Key activities completed this month",
            value=(existing or {}).get('key_activities', '') or '',
            height=100,
            placeholder="• Bullet what your discipline delivered this month\n• Be specific: drawing names, decisions, milestones",
            disabled=not can_edit,
        )

        concerns = st.text_area(
            "Concerns / blockers",
            value=(existing or {}).get('concerns', '') or '',
            height=80,
            placeholder="Issues that need leadership attention",
            disabled=not can_edit,
        )

        col_a, col_b = st.columns(2)
        with col_a:
            manpower = st.text_area(
                "Manpower / resource issues",
                value=(existing or {}).get('manpower_issues', '') or '',
                height=80,
                placeholder="Headcount, training gaps, allocation issues",
                disabled=not can_edit,
            )
        with col_b:
            software = st.text_area(
                "Software / training needs",
                value=(existing or {}).get('software_needs', '') or '',
                height=80,
                placeholder="License renewals, training nominations",
                disabled=not can_edit,
            )

        critical = st.text_area(
            "Critical concerns & decisions needed",
            value=(existing or {}).get('critical_items', '') or '',
            height=80,
            placeholder="What needs Sangeeta's review / sign-off",
            disabled=not can_edit,
        )

        # Project status — JSON-stored, displayed as text for now
        proj_status_default = ''
        if existing and existing.get('project_status'):
            ps = existing['project_status']
            if isinstance(ps, list):
                proj_status_default = '\n'.join(
                    f"{p.get('project','')} | {p.get('phase','')} | {p.get('pct','')}% | {p.get('status','')}"
                    for p in ps
                )
            elif isinstance(ps, str):
                proj_status_default = ps

        project_status_text = st.text_area(
            "Project status (one per line: Project | Phase | % | Status)",
            value=proj_status_default,
            height=120,
            placeholder="HPP1 | FEED+ | 85% | GAP done, awaiting FID\nCHP Ph1A | FEED Verif | 70% | DM plant TBE ongoing\n...",
            disabled=not can_edit,
            help="Format: 'Project name | Phase | Percent complete | Status/concerns'",
        )

        # Proposed actions
        actions_default = ''
        if existing and existing.get('proposed_actions'):
            pa = existing['proposed_actions']
            if isinstance(pa, list):
                actions_default = '\n'.join(
                    f"{a.get('text','')} | {a.get('owner','')} | {a.get('due','')}"
                    for a in pa
                )
            elif isinstance(pa, str):
                actions_default = pa

        actions_text = st.text_area(
            "Proposed action items (one per line: Action | Owner | Due date)",
            value=actions_default,
            height=100,
            placeholder="SAF Worley bid decision | HP | 30-Jun-2026\nHTRI training nomination | HP | 15-Jul-2026",
            disabled=not can_edit,
            help="Format: 'Action description | Owner name | Due date'",
        )

        # Submit buttons
        col1, col2, col3 = st.columns([1, 1, 3])
        save_draft = col1.form_submit_button("💾 Save draft", disabled=not can_edit)
        submit_final = col2.form_submit_button(
            "✓ Submit & lock",
            type="primary",
            disabled=not can_edit,
        )

        if save_draft or submit_final:
            # Parse structured fields
            proj_status_list = []
            for line in project_status_text.strip().split('\n'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4 and parts[0]:
                    proj_status_list.append({
                        'project': parts[0],
                        'phase': parts[1],
                        'pct': parts[2],
                        'status': parts[3],
                    })

            actions_list = []
            for line in actions_text.strip().split('\n'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 1 and parts[0]:
                    actions_list.append({
                        'text': parts[0],
                        'owner': parts[1] if len(parts) > 1 else '',
                        'due': parts[2] if len(parts) > 2 else '',
                    })

            # Determine status
            now = datetime.utcnow().isoformat()
            new_status = 'SUBMITTED' if submit_final else 'DRAFT'
            is_late = False
            if submit_final and meeting.get('prep_closes_at'):
                try:
                    deadline = pd.to_datetime(meeting['prep_closes_at']).to_pydatetime().replace(tzinfo=None)
                    if datetime.utcnow() > deadline:
                        new_status = 'LATE'
                        is_late = True
                except Exception:
                    pass

            payload = {
                'meeting_id': meeting['id'],
                'discipline': active_disc,
                'submitted_by': user['id'],
                'key_activities': key_activities,
                'project_status': proj_status_list,
                'concerns': concerns,
                'manpower_issues': manpower,
                'software_needs': software,
                'critical_items': critical,
                'proposed_actions': actions_list,
                'status': new_status,
                'is_late': is_late,
                'submitted_at': now if submit_final else None,
                'updated_at': now,
            }

            sb = db.get_client()
            if existing:
                # Update
                sb.table('ts_mer_inputs').update(payload).eq('id', existing['id']).execute()
                st.success("✅ Saved!" if save_draft else
                           f"✅ Submitted{' (LATE)' if is_late else ''} by {user['name']}")
            else:
                # Insert
                sb.table('ts_mer_inputs').insert(payload).execute()
                st.success("✅ Saved!" if save_draft else
                           f"✅ Submitted{' (LATE)' if is_late else ''} by {user['name']}")

            st.cache_data.clear()
            st.rerun()

    # Show submission info if exists
    if existing:
        st.caption(
            f"Last saved: {existing.get('updated_at', 'never')[:16]} · "
            f"Status: {existing.get('status', 'DRAFT')}"
            + (' · ⚠ LATE' if existing.get('is_late') else '')
        )


# ════════════════════════════════════════════════════
# PLACEHOLDERS for MEETING & REPORT tabs (Delivery 3)
# ════════════════════════════════════════════════════

def render_meeting_tab(meeting, user):
    st.info("🚧 **MEETING tab** — Coming in Delivery 3\n\n"
            "This tab will provide live capture during the monthly meeting:\n"
            "- Attendance tracking\n"
            "- Decisions captured\n"
            "- Action items raised live\n"
            "- Per-discipline agenda walkthrough")


def render_report_tab(meeting, user):
    st.info("🚧 **REPORT tab** — Coming in Delivery 3\n\n"
            "This tab will generate the final monthly report:\n"
            "- Executive Summary DOCX (4-5 pages)\n"
            "- Per-Discipline Report DOCX (15-20 pages)\n"
            "- Distribution log")


# ════════════════════════════════════════════════════
# MAIN ENTRY POINT — call from app.py
# ════════════════════════════════════════════════════

def render(user=None):
    """Top-level MER page renderer. Call from app.py main router."""
    if user is None:
        user = st.session_state.get('user', {})

    if not user:
        st.error("You must be logged in to access MER.")
        return

    if not can_access_mer(user):
        st.error("🔒 You do not have access to the Monthly Engineering Review module.")
        st.caption(
            "MER is restricted to super admins (HP, Sangeeta, Prachi, Pradeep, Aarti) "
            "and discipline leads."
        )
        return

    # Header
    st.markdown("# 📅 Monthly Engineering Review (MER)")
    role = get_user_role(user)
    role_label = {
        'OWNER': "👑 Owner",
        'SUPER_ADMIN': "⭐ Super Admin",
        'DISCIPLINE_LEAD': f"📝 {user.get('leads_discipline', 'Lead')}",
    }.get(role, role)
    st.caption(f"Logged in as: **{user.get('name', '?')}** · Role: {role_label}")

    # Load current meeting
    meeting = load_current_meeting()
    if not meeting:
        st.warning(
            "No active meeting found. Create the next meeting in the database "
            "(or run schema setup if MER tables don't exist)."
        )
        return

    # Tab selector — based on permissions
    if can_access_admin_tabs(user):
        # Super admin / owner — all 4 tabs
        tab_overview, tab_prep, tab_meeting, tab_report = st.tabs(
            ["📊 Overview", "📝 PREP", "🗓 Meeting", "📄 Report"]
        )
        with tab_overview:
            render_overview_tab(meeting, user)
        with tab_prep:
            render_prep_tab(meeting, user)
        with tab_meeting:
            render_meeting_tab(meeting, user)
        with tab_report:
            render_report_tab(meeting, user)
    else:
        # Discipline lead — PREP only
        st.info(
            f"👋 Welcome {user.get('name', '').split()[0]}. "
            f"As a discipline lead, you can fill PREP inputs for your discipline."
        )
        render_prep_tab(meeting, user)

