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
    """OVERVIEW tab — formatted to match the GCC Monthly Engineering Meeting Word template.
    
    Sections:
      1. Meeting header (date, no, chair, attendees)
      2. Project Status Table
      3. Engineering Activity Summary (from timesheet)
      4. Engineering Strength Discipline-wise
      5. Open Action Items
      6. Critical Items / Decisions Needed
    """
    review_month = meeting['review_month']  # 'YYYY-MM'
    year, month = map(int, review_month.split('-'))
    month_name = date(year, month, 1).strftime('%B %Y')
    last_day = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)

    # ── Meeting Header ──
    st.markdown(
        f"<div style='background:#1F4E78;color:#FFF;padding:14px 18px;border-radius:10px;"
        f"margin-bottom:14px;'>"
        f"<table style='width:100%;color:#FFF;font-size:12px;'>"
        f"<tr><td><b>GCC – Engineering Monthly Meeting</b></td>"
        f"<td style='text-align:right;'>Meeting No: <b>{meeting['meeting_no']:02d}</b></td></tr>"
        f"<tr><td>Reviewing: <b>{month_name}</b> (data as of {last_day.strftime('%d-%b-%Y')})</td>"
        f"<td style='text-align:right;'>Scheduled: <b>{meeting.get('scheduled_date', 'TBD')}</b></td></tr>"
        f"<tr><td>Chair / Presenter: <b>{meeting.get('chair', 'HP')}</b></td>"
        f"<td style='text-align:right;'>Reviewer: <b>{meeting.get('reviewer', 'Sangeeta')}</b></td></tr>"
        f"<tr><td>Location: <b>GCC Arioli, Mumbai</b></td>"
        f"<td style='text-align:right;'>Status: <b>{STATE_LABEL.get(meeting['status'], meeting['status'])}</b></td></tr>"
        f"</table></div>",
        unsafe_allow_html=True
    )

    # ── Load timesheet data for the review month ──
    entries = load_entries_for_month(year, month)
    members = db.get_members()

    if not entries:
        st.warning(f"No timesheet entries for {month_name}. Showing structure only.")
        df = pd.DataFrame()
    else:
        df = pd.DataFrame(entries)
        df['Hours'] = df['hrs'].astype(float)
        df['Description'] = df['description'].fillna('').astype(str)
        mem_lookup = {m['id']: m for m in members}
        df['member_name'] = df['uid'].map(lambda u: mem_lookup.get(u, {}).get('name', f'uid:{u}'))
        df['discipline'] = df['uid'].map(lambda u: mem_lookup.get(u, {}).get('discipline', '-'))

    excluded_uids = {m['id'] for m in members if m.get('excluded_from_productivity')}
    df_eng = df[~df['uid'].isin(excluded_uids)].copy() if len(df) else pd.DataFrame()
    if len(df_eng):
        df_eng['Category'] = df_eng.apply(
            lambda r: classify_activity(r['act'], r['Description']), axis=1
        )

    # ════════════════════════════════════════
    # SECTION 1: PROJECT STATUS TABLE
    # ════════════════════════════════════════
    st.markdown("## 1. Project Status — Key Updates from Each Project")

    # Aggregate hours by project from timesheet
    if len(df_eng):
        proj_hours = df_eng.groupby('proj').agg(
            Hours=('Hours', 'sum'),
            Members=('uid', 'nunique'),
        ).reset_index().sort_values('Hours', ascending=False)
    else:
        proj_hours = pd.DataFrame(columns=['proj', 'Hours', 'Members'])

    # Try to pull PREP-submitted project status from this month's inputs
    inputs = load_inputs_for_meeting(meeting['id'])
    all_project_statuses = {}
    for inp in inputs:
        ps = inp.get('project_status') or []
        if isinstance(ps, list):
            for p in ps:
                pname = (p.get('project') or '').strip()
                if not pname:
                    continue
                if pname not in all_project_statuses:
                    all_project_statuses[pname] = []
                all_project_statuses[pname].append({
                    'phase': p.get('phase', ''),
                    'pct': p.get('pct', ''),
                    'status': p.get('status', ''),
                    'discipline': inp.get('discipline', ''),
                })

    # Build display rows: union of (project-with-hours) + (project-with-PREP-status)
    all_project_names = set(proj_hours['proj'].tolist()) | set(all_project_statuses.keys())
    
    if all_project_names:
        rows = []
        for sl_no, pname in enumerate(sorted(all_project_names), 1):
            hrs_row = proj_hours[proj_hours['proj'] == pname]
            hours = int(hrs_row['Hours'].iloc[0]) if len(hrs_row) else 0
            n_disc = int(hrs_row['Members'].iloc[0]) if len(hrs_row) else 0
            
            # Aggregate PREP status if available
            statuses = all_project_statuses.get(pname, [])
            if statuses:
                phase = statuses[0].get('phase', '')
                pct = statuses[0].get('pct', '')
                status_text = ' / '.join(s['status'] for s in statuses if s.get('status'))[:200]
            else:
                phase = ''
                pct = ''
                status_text = '— No PREP input yet —'
            
            rows.append({
                'Sl': sl_no,
                'Project': pname,
                'Phase': phase or '(not set)',
                'Hours': hours,
                'Members': n_disc,
                'Status / Activities': status_text,
            })
        
        df_proj = pd.DataFrame(rows)
        st.dataframe(df_proj, use_container_width=True, hide_index=True)
        st.caption(
            f"Total: {len(rows)} projects · "
            f"{int(proj_hours['Hours'].sum())} hours booked · "
            f"Phase/Status fills from PREP submissions (currently {len(inputs)} disciplines submitted)"
        )
    else:
        st.info("No project activity recorded for this month.")

    st.markdown("---")

    # ════════════════════════════════════════
    # SECTION 2: ENGINEERING ACTIVITY SUMMARY
    # ════════════════════════════════════════
    st.markdown("## 2. Engineering Activity Summary")
    st.caption(f"Workhours analysis extracted from Timesheet · Data as of {last_day.strftime('%d-%b-%Y')}")

    if len(df_eng):
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
        leave_pct = cat_totals.get('LEAVE', 0) / total_hrs * 100 if total_hrs else 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total hours", f"{total_hrs:,.0f}")
        c2.metric("Reporting", f"{n_reporting} / {eng_members_total}")
        c3.metric("Projects", n_projects)
        c4.metric("High-value", f"{hv_pct:.0f}%", help="Design + Review + Coord")
        c5.metric("Unclassified", f"{unclass_pct:.0f}%", delta_color="inverse")
        c6.metric("Leave", f"{leave_pct:.0f}%")

        # Category mix bar
        bar_html = '<div style="display:flex;height:18px;border-radius:4px;overflow:hidden;margin-top:10px;background:#eee;">'
        for c in CAT_ORDER:
            v = cat_totals.get(c, 0)
            if v > 0:
                pct = v / total_hrs * 100
                bar_html += (
                    f'<div style="width:{pct:.0f}%;background:{CAT_COLORS[c]};'
                    f'color:white;font-size:10px;display:flex;align-items:center;'
                    f'justify-content:center;font-weight:500;" '
                    f'title="{CAT_LABEL[c]}: {int(v)}h">{CAT_LABEL[c]} {pct:.0f}%</div>'
                )
        bar_html += '</div>'
        st.markdown(bar_html, unsafe_allow_html=True)

        # Per-discipline breakdown table
        with st.expander("📊 Discipline-wise breakdown", expanded=False):
            disc_summary = (df_eng.groupby('discipline')
                                  .agg(Hours=('Hours', 'sum'), Members=('uid', 'nunique'))
                                  .reset_index()
                                  .sort_values('Hours', ascending=False))
            st.dataframe(disc_summary, use_container_width=True, hide_index=True)
    else:
        st.info(f"No timesheet data for {month_name}.")

    st.markdown("---")

    # ════════════════════════════════════════
    # SECTION 3: ENGINEERING STRENGTH (DISCIPLINE-WISE)
    # ════════════════════════════════════════
    st.markdown("## 3. Engineering Strength — Discipline-wise")

    # Count members per discipline (excluding non-engineering)
    eng_members = [m for m in members if m.get('dept') == 'Engineering']
    disc_counts = {}
    for m in eng_members:
        d = m.get('discipline', '-') or '-'
        disc_counts[d] = disc_counts.get(d, 0) + 1
    
    strength_rows = []
    total_strength = 0
    for d, count in sorted(disc_counts.items(), key=lambda x: -x[1]):
        # Find lead for this discipline
        lead = next(
            (m['name'] for m in members
             if m.get('is_discipline_lead') and m.get('leads_discipline') == d),
            '—'
        )
        strength_rows.append({
            'Discipline': d,
            'Strength': count,
            'Lead': lead,
        })
        total_strength += count
    
    if strength_rows:
        df_strength = pd.DataFrame(strength_rows)
        st.dataframe(df_strength, use_container_width=True, hide_index=True)
        st.caption(f"Total Engineering strength: **{total_strength}**")

    st.markdown("---")

    # ════════════════════════════════════════
    # SECTION 4: OPEN ACTION ITEMS
    # ════════════════════════════════════════
    st.markdown("## 4. Open Action Items")
    
    actions = load_open_actions()
    if actions:
        adf = pd.DataFrame(actions)
        today = date.today()
        if 'due_date' in adf.columns:
            adf['_due'] = pd.to_datetime(adf['due_date'], errors='coerce').dt.date
            adf['Status'] = adf.apply(
                lambda r: ('🔴 Overdue' if pd.notna(r['_due']) and r['_due'] < today
                           else '🟡 Due Soon' if pd.notna(r['_due']) and (r['_due'] - today).days <= 7
                           else '🟢 On Track'), axis=1)
        else:
            adf['Status'] = '🟢 Open'
        
        cols_to_show = ['Status', 'action_text', 'owner_name', 'due_date', 'discipline', 'source_phase']
        cols_existing = [c for c in cols_to_show if c in adf.columns]
        adf_show = adf[cols_existing].copy()
        adf_show.columns = ['Status', 'Action', 'Owner', 'Due', 'Discipline', 'Source'][:len(cols_existing)]
        st.dataframe(adf_show, use_container_width=True, hide_index=True)
        overdue_count = sum(1 for a in actions 
                            if a.get('due_date') and 
                            pd.to_datetime(a['due_date'], errors='coerce') < pd.Timestamp(today))
        st.caption(f"Total open: {len(actions)} · Overdue: {overdue_count}")
    else:
        st.info("No open action items. New actions can be captured in the MEETING tab (Delivery 3).")

    st.markdown("---")

    # ════════════════════════════════════════
    # SECTION 5: CRITICAL ITEMS & DECISIONS NEEDED (from PREP)
    # ════════════════════════════════════════
    st.markdown("## 5. Critical Items & Decisions Needed")
    st.caption("Aggregated from each discipline's PREP submissions")
    
    critical_compiled = []
    for inp in inputs:
        if inp.get('critical_items'):
            critical_compiled.append({
                'Discipline': inp.get('discipline', '-'),
                'Critical Items': inp['critical_items'],
                'Submitted by': inp.get('submitted_by', ''),
            })
    
    if critical_compiled:
        for c in critical_compiled:
            with st.expander(f"⚠ {c['Discipline']}", expanded=True):
                st.markdown(c['Critical Items'])
    else:
        st.info("No critical items submitted yet. Discipline leads will fill these in the PREP tab.")

    st.markdown("---")

    # ════════════════════════════════════════
    # SECTION 6: DATA QUALITY FLAGS (timesheet hygiene)
    # ════════════════════════════════════════
    st.markdown("## 6. Data Quality Flags")
    st.caption(f"Members with timesheet hygiene issues in {month_name}")
    
    role = get_user_role(user)
    is_admin = role in ('OWNER', 'SUPER_ADMIN')
    
    flags = []
    if len(df_eng):
        eng_members_for_flags = [m for m in members
                       if m.get('dept') == 'Engineering'
                       and m['id'] not in excluded_uids]
        for m in eng_members_for_flags:
            mid = m['id']
            sub = df_eng[df_eng['uid'] == mid]
            m_hrs = sub['Hours'].sum() if len(sub) else 0
            if m_hrs == 0:
                flags.append({
                    'Discipline': m.get('discipline', '-'),
                    'Member': m['name'],
                    'Issue': '🔴 0 hrs filled',
                    'severity': 3,
                })
                continue
            unclass_h = sub[sub['Category'] == 'UNCLASS']['Hours'].sum()
            unclass_pct = unclass_h / m_hrs * 100
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
    
    if not is_admin and role == 'DISCIPLINE_LEAD':
        my_disc = user.get('leads_discipline', '')
        flags = [f for f in flags if f['Discipline'] == my_disc]
    
    if flags:
        df_flags = pd.DataFrame(flags).sort_values('severity', ascending=False).drop(columns=['severity'])
        st.dataframe(df_flags, use_container_width=True, hide_index=True)
    else:
        st.success("✅ No data quality flags — clean reporting!")

    st.markdown("---")

    # ════════════════════════════════════════
    # SECTION 7: PREP SUBMISSION STATUS
    # ════════════════════════════════════════
    st.markdown("## 7. PREP Submission Status")
    
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
    deadline_str = meeting.get('prep_closes_at', 'TBD')[:10] if meeting.get('prep_closes_at') else 'TBD'
    st.caption(f"{n_submitted} submitted · {n_late} late · {n_pending} pending · Deadline: {deadline_str}")

    # Super Admin section (owner-only)
    if role == 'OWNER':
        st.markdown("---")
        with st.expander("🔒 Super Admin Permissions (owner only)", expanded=False):
            sb = db.get_client()
            try:
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
            except Exception as e:
                st.caption(f"(super admin list unavailable: {e})")

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
    """MEETING tab — live capture during the monthly meeting."""
    role = get_user_role(user)
    is_admin = role in ('OWNER', 'SUPER_ADMIN')

    if not is_admin:
        st.warning("🔒 The MEETING tab is for super admins only. You can view the final REPORT once published.")
        return

    st.markdown(f"### 🗓 Meeting #{meeting['meeting_no']:02d} — Live Capture")
    st.caption(
        f"Reviewing {meeting['review_month']} · "
        f"Scheduled: {meeting.get('scheduled_date', 'TBD')} · "
        f"Status: {STATE_LABEL.get(meeting['status'], meeting['status'])}"
    )

    # Quick state controls
    with st.expander("🎚 Meeting State Controls", expanded=False):
        st.write(f"Current state: **{meeting['status']}**")
        col1, col2, col3 = st.columns(3)
        sb = db.get_client()
        if col1.button("📝 Open PREP", disabled=meeting['status'] != 'DRAFT'):
            sb.table('ts_mer_meetings').update({'status': 'PREP_OPEN'}).eq('id', meeting['id']).execute()
            st.cache_data.clear()
            st.success("PREP opened. Notify discipline leads via WhatsApp/Email below.")
            st.rerun()
        if col2.button("🔒 Close PREP", disabled=meeting['status'] != 'PREP_OPEN'):
            sb.table('ts_mer_meetings').update({'status': 'PREP_CLOSED'}).eq('id', meeting['id']).execute()
            st.cache_data.clear()
            st.success("PREP closed.")
            st.rerun()
        if col3.button("✅ Mark Meeting Complete", disabled=meeting['status'] not in ('IN_MEETING', 'PREP_CLOSED')):
            sb.table('ts_mer_meetings').update({
                'status': 'COMPLETED',
                'meeting_completed_at': datetime.utcnow().isoformat()
            }).eq('id', meeting['id']).execute()
            st.cache_data.clear()
            st.success("Meeting marked complete. Generate the report in REPORT tab.")
            st.rerun()
        if meeting['status'] == 'PREP_CLOSED' and st.button("▶️ Start Meeting (move to IN_MEETING)"):
            sb.table('ts_mer_meetings').update({
                'status': 'IN_MEETING',
                'meeting_started_at': datetime.utcnow().isoformat()
            }).eq('id', meeting['id']).execute()
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # ── Section 1: Attendance ──
    st.markdown("#### ✅ Attendance")
    members = db.get_members()
    eng_members = [m for m in members
                   if m.get('dept') == 'Engineering'
                   or m.get('is_owner') or m.get('is_super_admin')]
    
    existing_attendance = {a['member_id']: a for a in load_attendance(meeting['id'])}
    
    sb = db.get_client()
    cols = st.columns(3)
    for idx, m in enumerate(eng_members):
        col = cols[idx % 3]
        mid = m['id']
        current = existing_attendance.get(mid, {}).get('status', 'INVITED')
        new_status = col.selectbox(
            m['name'],
            ['INVITED', 'PRESENT', 'ABSENT', 'APOLOGY'],
            index=['INVITED', 'PRESENT', 'ABSENT', 'APOLOGY'].index(current),
            key=f"att_{mid}",
            label_visibility='visible',
        )
        # Save on change
        if new_status != current:
            payload = {
                'meeting_id': meeting['id'],
                'member_id': mid,
                'member_name': m['name'],
                'status': new_status,
            }
            if mid in existing_attendance:
                sb.table('ts_mer_attendance').update(payload).eq('id', existing_attendance[mid]['id']).execute()
            else:
                sb.table('ts_mer_attendance').insert(payload).execute()

    st.markdown("---")

    # ── Section 2: Decisions Captured ──
    st.markdown("#### 📌 Decisions Captured")
    decisions = load_decisions(meeting['id'])
    if decisions:
        for d in decisions:
            with st.expander(f"📌 {d.get('topic', 'Untitled')}", expanded=False):
                st.write(d.get('decision_text', ''))
                st.caption(f"Captured: {d.get('captured_at', '')[:16]}")

    with st.form("add_decision_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        topic = col1.text_input("Topic", placeholder="e.g., HPP1 RFQ")
        decision_text = col2.text_area("Decision", placeholder="Decision text...", height=70)
        if st.form_submit_button("➕ Capture Decision") and topic and decision_text:
            sb.table('ts_mer_decisions').insert({
                'meeting_id': meeting['id'],
                'topic': topic,
                'decision_text': decision_text,
                'proposed_by': user['name'],
            }).execute()
            st.cache_data.clear()
            st.success(f"Captured: {topic}")
            st.rerun()

    st.markdown("---")

    # ── Section 3: Action Items ──
    st.markdown("#### 📝 Action Items")
    actions = load_open_actions()
    if actions:
        df_act = pd.DataFrame(actions)
        st.dataframe(
            df_act[['action_text', 'owner_name', 'due_date', 'status', 'discipline']],
            use_container_width=True, hide_index=True
        )
    else:
        st.caption("No open actions yet.")

    with st.form("add_action_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        action_text = col1.text_input("Action description", placeholder="e.g., Issue HPP1 RFQ draft")
        owner_name = col2.text_input("Owner", placeholder="HP / Piyush / etc.")
        due = col3.date_input("Due date", value=None)
        if st.form_submit_button("➕ Add Action") and action_text and owner_name:
            sb.table('ts_mer_actions').insert({
                'action_text': action_text,
                'owner_name': owner_name,
                'due_date': due.isoformat() if due else None,
                'raised_in_meeting_id': meeting['id'],
                'source_phase': 'MEETING',
                'status': 'OPEN',
            }).execute()
            st.cache_data.clear()
            st.success(f"Added: {action_text}")
            st.rerun()

    st.markdown("---")
    
    # ── Section 4: Notification message generators ──
    with st.expander("📨 Notification Messages (copy-paste to WhatsApp/Email)", expanded=False):
        render_notifications(meeting)


def render_report_tab(meeting, user):
    """REPORT tab — auto-generate the 6-page A4 monthly report DOCX."""
    role = get_user_role(user)
    is_admin = role in ('OWNER', 'SUPER_ADMIN')

    if not is_admin:
        st.warning("🔒 The REPORT tab is for super admins only.")
        return

    st.markdown(f"### 📄 Monthly Report — Meeting #{meeting['meeting_no']:02d}")
    st.caption(f"Reviewing {meeting['review_month']} · Auto-generated 6-page A4 minutes")

    # Show summary of what will be in the report
    inputs = load_inputs_for_meeting(meeting['id'])
    actions = load_open_actions()
    decisions_list = load_decisions(meeting['id'])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Disciplines submitted", f"{len([i for i in inputs if i.get('status') == 'SUBMITTED'])}")
    col2.metric("Open actions", len(actions))
    col3.metric("Decisions captured", len(decisions_list))
    col4.metric("Status", meeting['status'])

    st.markdown("---")
    st.markdown("##### Generate Report")
    st.caption(
        "Click below to generate the 6-page DOCX report from current data. "
        "Includes: meeting metadata, key highlights, project status, manhours, "
        "engineering strength, critical items, action items, coordination, "
        "software/training, decisions, closing notes."
    )

    if st.button("📄 Generate DOCX Report", type="primary"):
        with st.spinner("Generating report..."):
            try:
                from mer_report_generator import generate_report, generate_report_filename
                buf = generate_report(meeting['id'])
                filename = generate_report_filename(meeting)
                st.download_button(
                    "📥 Download " + filename,
                    data=buf.getvalue(),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                st.success(f"Report generated. Click Download above to save.")
            except Exception as e:
                st.error(f"Generation failed: {e}")
                import traceback
                st.code(traceback.format_exc())

    st.markdown("---")
    
    # Distribution status
    st.markdown("##### Distribution")
    if meeting['status'] == 'COMPLETED':
        col1, col2 = st.columns(2)
        if col1.button("📤 Mark as Published"):
            sb = db.get_client()
            sb.table('ts_mer_meetings').update({
                'status': 'PUBLISHED',
                'published_at': datetime.utcnow().isoformat()
            }).eq('id', meeting['id']).execute()
            st.cache_data.clear()
            st.rerun()
        col2.caption("Move to PUBLISHED state once report is reviewed by Sangeeta and distributed.")
    elif meeting['status'] == 'PUBLISHED':
        st.success(f"✅ Report published on {meeting.get('published_at', '')[:10]}")
    else:
        st.info(f"Mark meeting as COMPLETED first (from MEETING tab) to enable publishing.")


# ════════════════════════════════════════════════════
# MAIN ENTRY POINT — call from app.py
# ════════════════════════════════════════════════════


# ════════════════════════════════════════════════════
# DATA LOADERS FOR DELIVERY 3
# ════════════════════════════════════════════════════

def load_attendance(meeting_id):
    """Not cached — for live editing."""
    sb = db.get_client()
    r = sb.table('ts_mer_attendance').select('*').eq('meeting_id', meeting_id).execute()
    return r.data or []


def load_decisions(meeting_id):
    """Not cached — for live editing."""
    sb = db.get_client()
    r = sb.table('ts_mer_decisions').select('*').eq('meeting_id', meeting_id).order('captured_at', desc=True).execute()
    return r.data or []


# ════════════════════════════════════════════════════
# NOTIFICATIONS
# ════════════════════════════════════════════════════

def render_notifications(meeting):
    """Generate ready-to-paste notification messages for WhatsApp / email."""
    status = meeting['status']
    review_month = meeting['review_month']
    year, month = map(int, review_month.split('-'))
    month_name = date(year, month, 1).strftime('%B %Y')

    if status == 'PREP_OPEN':
        prep_close = meeting.get('prep_closes_at', '')[:10] if meeting.get('prep_closes_at') else 'TBD'
        msg = f"""📅 *Monthly Engineering Review #{meeting['meeting_no']:02d}*

Dear Discipline Leads,

PREP is now open for reviewing *{month_name}* data.

📝 *Action needed:* Log in to the GCC Timesheet App → MER tab → PREP
🔗 https://gcc-eet-timesheet.streamlit.app
⏰ *Deadline:* {prep_close}
🗓 *Meeting:* {meeting.get('scheduled_date', 'TBD')}

Each discipline lead, please fill your section:
- Key activities completed
- Project status updates
- Concerns & critical items
- Manpower / software needs
- Proposed action items

— HP (Dy Engineering Head, Chair of MER)"""

    elif status == 'PREP_CLOSED':
        msg = f"""📅 *MER #{meeting['meeting_no']:02d} — PREP Closed*

PREP submissions for {month_name} review are now closed.

Late submissions are still accepted but flagged.

🗓 Meeting on {meeting.get('scheduled_date', 'TBD')}.

— HP"""

    elif status == 'COMPLETED' or status == 'PUBLISHED':
        msg = f"""📅 *MER #{meeting['meeting_no']:02d} — Report Published*

The Monthly Engineering Review report for {month_name} is now available.

Download from app or check your email.

🔗 https://gcc-eet-timesheet.streamlit.app → MER → Report

— HP"""

    else:
        msg = f"Meeting is in {status} state — no automated message for this phase."

    st.markdown("###### WhatsApp / Email message")
    st.code(msg, language=None)
    st.caption("Copy the message above and send via WhatsApp / Email to the engineering group.")


# ════════════════════════════════════════════════════
# SUPER ADMIN GRANT / REVOKE UI
# ════════════════════════════════════════════════════

def render_super_admin_panel(user):
    """Visible only to OWNER (HP). Allows granting/revoking Super Admin status."""
    if not user.get('is_owner'):
        return

    sb = db.get_client()
    r = sb.table('ts_mer_super_admins').select('*').eq('is_active', True).execute()
    current_admins = r.data or []
    admin_member_ids = {a['member_id'] for a in current_admins}

    st.markdown("##### Current Permissions")
    members = db.get_members()
    mem_lookup = {m['id']: m for m in members}

    rows = []
    for sa in current_admins:
        mem = mem_lookup.get(sa['member_id'])
        if mem:
            rows.append({
                'Name': mem['name'],
                'Role': sa['role'],
                'Granted on': (sa.get('granted_at') or '')[:10],
            })
    
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    
    st.markdown("##### Grant Super Admin to a member")
    eligible = [m for m in members if m['id'] not in admin_member_ids]
    eligible_names = [m['name'] for m in eligible]
    
    if eligible_names:
        col1, col2 = st.columns([3, 1])
        selected_name = col1.selectbox(
            "Select a member to grant Super Admin",
            ['— Choose —'] + eligible_names,
            key='grant_member_pick'
        )
        
        if col2.button("➕ Grant", disabled=(selected_name == '— Choose —')):
            # Confirmation
            if not st.session_state.get('confirm_grant'):
                st.session_state.confirm_grant = selected_name
                st.warning(f"⚠ Are you sure you want to grant Super Admin to **{selected_name}**? Click 'Grant' again to confirm.")
            else:
                selected_member = next(m for m in members if m['name'] == st.session_state.confirm_grant)
                # Update flag on member
                sb.table('ts_members').update({'is_super_admin': True}).eq('id', selected_member['id']).execute()
                # Insert audit log
                sb.table('ts_mer_super_admins').insert({
                    'member_id': selected_member['id'],
                    'role': 'SUPER_ADMIN',
                    'granted_by_id': user['id'],
                    'is_active': True,
                    'notes': f'Granted via UI by {user["name"]}',
                }).execute()
                st.session_state.confirm_grant = None
                st.cache_data.clear()
                st.success(f"✅ {selected_member['name']} is now a Super Admin")
                st.rerun()
    else:
        st.caption("All eligible members are already Super Admins.")
    
    st.markdown("##### Revoke Super Admin")
    revocable = [sa for sa in current_admins if sa['role'] != 'OWNER']
    if revocable:
        revoke_names = [mem_lookup[sa['member_id']]['name'] for sa in revocable if sa['member_id'] in mem_lookup]
        col1, col2 = st.columns([3, 1])
        revoke_name = col1.selectbox(
            "Revoke from:",
            ['— Choose —'] + revoke_names,
            key='revoke_member_pick'
        )
        if col2.button("🗑 Revoke", disabled=(revoke_name == '— Choose —')):
            if not st.session_state.get('confirm_revoke'):
                st.session_state.confirm_revoke = revoke_name
                st.warning(f"⚠ Are you sure you want to revoke Super Admin from **{revoke_name}**? Click 'Revoke' again to confirm.")
            else:
                revoke_member = next(m for m in members if m['name'] == st.session_state.confirm_revoke)
                # Update flag
                sb.table('ts_members').update({'is_super_admin': False}).eq('id', revoke_member['id']).execute()
                # Mark audit log as revoked
                sb.table('ts_mer_super_admins').update({
                    'is_active': False,
                    'revoked_at': datetime.utcnow().isoformat(),
                    'revoked_by_id': user['id'],
                }).eq('member_id', revoke_member['id']).eq('is_active', True).execute()
                st.session_state.confirm_revoke = None
                st.cache_data.clear()
                st.success(f"✅ Super Admin revoked from {revoke_member['name']}")
                st.rerun()
    else:
        st.caption("No revocable Super Admins (Owner cannot be revoked).")


# ════════════════════════════════════════════════════
# OVERVIEW UPGRADE — 12 discipline tabs
# ════════════════════════════════════════════════════

CAT_COLORS_MAP = {
    'DESIGN':  '#0F6E56', 'REVIEW':  '#185FA5', 'COORD':   '#7F77DD',
    'DOC':     '#BA7517', 'ADMIN':   '#888880', 'LEAVE':   '#5DCAA5',
    'UNCLASS': '#A32D2D',
}

ACTIVITY_DESC_LOOKUP = {
    'PRS-01': 'PFD Preparation', 'PRS-02': 'P&ID Development',
    'PRS-04': 'Process Design Review', 'PRS-05': 'Heat & Material Balance Review',
    'PRS-07': 'Process Calculations & Sizing', 'PRS-08': 'Process Specification & Datasheet',
    'PRS-09': 'Equipment List & MR', 'PRS-10': 'Vendor Document Review',
    'PRS-11': 'Process Meeting & Coordination',
    'CIV-01': 'Civil Concept Design', 'CIV-02': 'Civil Drawing Review & Mark-up',
    'CIV-03': 'Foundation / Structural Calc', 'CIV-04': 'Structural Spec & Datasheet',
    'CIV-05': 'Civil Drawing Verification', 'CIV-06': 'Civil GA Review & Comments',
    'CIV-07': 'Civil Bulk MTO / BoQ Check', 'CIV-08': 'Civil Vendor Coordination',
    'CIV-09': 'Civil Documentation / MDR', 'CIV-10': 'Civil Engineering Meeting',
    'CIV-11': 'Civil Site Coordination',
    'ELEC-01': 'Single Line Diagram (SLD)', 'ELEC-02': 'Electrical Load List & Sizing',
    'ELEC-04': 'Cable Sizing & Calc', 'ELEC-05': 'Electrical Drawing Review',
    'ELEC-06': 'Electrical Specification Review', 'ELEC-07': 'Electrical Spec & Datasheet',
    'ELEC-08': 'Electrical MTO / BoQ Check', 'ELEC-09': 'Electrical Vendor Offer Review',
    'ELEC-10': 'Electrical Documentation / MDR', 'ELEC-11': 'Electrical Coordination Meeting',
    'INST-01': 'Instrument Index & Datasheet', 'INST-02': 'Control System Architecture',
    'INST-03': 'Instrument Sizing & Calc', 'INST-04': 'Instrument Drawing Review',
    'INST-05': 'Instrument Specification Review',
    'MS-01': 'Static Equipment Design', 'MS-02': 'Vessel / HX Sizing',
    'MS-03': 'Static Equipment Drawing Review', 'MS-04': 'Static Equipment Spec Review',
    'MECH-01': 'Mechanical Equipment Design', 'MECH-02': 'Mechanical Datasheet Preparation',
    'MECH-04': 'Mechanical Drawing Review', 'MECH-06': 'Mechanical Vendor Coordination',
    'MECH-07': 'Mechanical Calculation', 'MECH-08': 'Mechanical Specification Prep',
    'MECH-09': 'Mechanical MTO Extraction', 'MECH-10': 'Mechanical Drawing Verification',
    'MECH-11': 'Mechanical Documentation', 'MECH-12': 'Mechanical Coordination Meeting',
    'MR-01': 'Rotary Equipment Design / Datasheet', 'MR-02': 'Rotary Vendor Offer Review',
    'MR-03': 'Rotary Equipment Calc / Verification',
    'PIP-01': 'Piping Layout Design', 'PIP-02': 'Piping MTO Extraction',
    'PIP-03': 'Piping Isometric Preparation',
    'HSE-03': 'HSE Review & Risk Assessment',
    'DOC-01': 'Document Management & MDR',
    'LEAVE': 'Leave', 'HOL': 'Public Holiday', 'HOLIDAY': 'Public Holiday',
    'OTHERS': 'Other / Unspecified',
    'Tool Box meeting': 'Tool Box Meeting',
    'Idle Man Hours': 'Idle / Waiting',
}


def get_activity_description(activity_code):
    """Return human-readable description for an activity code."""
    a = str(activity_code or '').strip()
    return ACTIVITY_DESC_LOOKUP.get(a, a if a else 'Unspecified')


def render_discipline_dashboard(disc_name, members, entries_df, meeting):
    """Render a single discipline's deep-dive dashboard (used inside the per-discipline tab)."""
    # Filter to this discipline's data
    disc_member_ids = {m['id'] for m in members if m.get('discipline') == disc_name}
    excluded_uids = {m['id'] for m in members if m.get('excluded_from_productivity')}
    
    df_d = entries_df[entries_df['uid'].isin(disc_member_ids - excluded_uids)].copy()
    
    if len(df_d) == 0:
        st.info(f"No timesheet data for {disc_name} in {meeting['review_month']}.")
        return

    df_d['Description'] = df_d['description'].fillna('').astype(str)
    df_d['Category'] = df_d.apply(
        lambda r: classify_activity(r['act'], r['Description']), axis=1
    )

    # ── KPIs ──
    total_hrs = df_d['hrs'].sum()
    n_members = df_d['uid'].nunique()
    top_proj_g = df_d.groupby('proj')['hrs'].sum().sort_values(ascending=False)
    top_proj = top_proj_g.index[0] if len(top_proj_g) else '-'
    
    cat_tot = df_d.groupby('Category')['hrs'].sum()
    hv = sum(cat_tot.get(c, 0) for c in ['DESIGN', 'REVIEW', 'COORD'])
    hv_pct = hv / total_hrs * 100 if total_hrs else 0
    unclass = cat_tot.get('UNCLASS', 0)
    unclass_pct = unclass / total_hrs * 100 if total_hrs else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Hours", f"{total_hrs:,.0f}")
    c2.metric("Members", n_members)
    c3.metric("Top Project", top_proj, help=f"{top_proj_g.iloc[0]:.0f} hrs" if len(top_proj_g) else "")
    c4.metric("High-Value", f"{hv_pct:.0f}%", help="Design + Review + Coord")
    c5.metric("Visibility", f"{100-unclass_pct:.0f}%", help="100% - unclassified%",
              delta_color="normal" if (100 - unclass_pct) >= 70 else "inverse")

    # ── Category Mix Bar ──
    st.markdown("**Category Mix**")
    bar_html = '<div style="display:flex;height:24px;border-radius:4px;overflow:hidden;background:#eee;margin-bottom:12px;">'
    for c in CAT_ORDER:
        v = cat_tot.get(c, 0)
        if v > 0:
            pct = v / total_hrs * 100
            bar_html += (
                f'<div style="width:{pct:.0f}%;background:{CAT_COLORS_MAP[c]};'
                f'color:white;font-size:11px;display:flex;align-items:center;'
                f'justify-content:center;font-weight:500;" '
                f'title="{CAT_LABEL[c]}: {int(v)}h">{CAT_LABEL[c]} {pct:.0f}%</div>'
            )
    bar_html += '</div>'
    st.markdown(bar_html, unsafe_allow_html=True)

    # ── Top Projects + Top Activities (side by side) ──
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**Top Projects**")
        proj_table = top_proj_g.head(5).reset_index()
        proj_table.columns = ['Project', 'Hours']
        proj_table['% of Total'] = (proj_table['Hours'] / total_hrs * 100).round(0).astype(int).astype(str) + '%'
        proj_table['Hours'] = proj_table['Hours'].round(0).astype(int)
        st.dataframe(proj_table, use_container_width=True, hide_index=True)
    
    with col_b:
        st.markdown("**Top Activities** (descriptions, not codes)")
        df_d['ActivityDesc'] = df_d['act'].apply(get_activity_description)
        act_table = (df_d.groupby('ActivityDesc')
                          .agg(Hours=('hrs', 'sum'),
                               Category=('Category', 'first'),
                               Members=('uid', 'nunique'))
                          .reset_index()
                          .sort_values('Hours', ascending=False)
                          .head(5))
        act_table['Hours'] = act_table['Hours'].round(0).astype(int)
        st.dataframe(act_table, use_container_width=True, hide_index=True)

    # ── Anomalies (names visible since this is the live app for leads/HP) ──
    st.markdown("**Data Quality — Member Flags**")
    flag_rows = []
    for mid in disc_member_ids - excluded_uids:
        mem = next((m for m in members if m['id'] == mid), None)
        if not mem:
            continue
        sub = df_d[df_d['uid'] == mid]
        m_hrs = sub['hrs'].sum()
        if m_hrs == 0:
            flag_rows.append({'Member': mem['name'], 'Issue': '🔴 0 hrs filled', 'Severity': 3})
            continue
        unclass_h = sub[sub['Category'] == 'UNCLASS']['hrs'].sum()
        u_pct = unclass_h / m_hrs * 100
        if u_pct > 50:
            flag_rows.append({'Member': mem['name'], 'Issue': f'🔴 {u_pct:.0f}% on OTHERS', 'Severity': 3})
        elif u_pct > 25:
            flag_rows.append({'Member': mem['name'], 'Issue': f'🟡 {u_pct:.0f}% on OTHERS', 'Severity': 2})

    if flag_rows:
        df_flags = pd.DataFrame(flag_rows).sort_values('Severity', ascending=False).drop(columns=['Severity'])
        st.dataframe(df_flags, use_container_width=True, hide_index=True)
    else:
        st.success(f"✅ All {n_members} members reporting cleanly")

    # ── Commentary ──
    profile_bits = []
    design_pct = cat_tot.get('DESIGN', 0) / total_hrs * 100 if total_hrs else 0
    review_pct = cat_tot.get('REVIEW', 0) / total_hrs * 100 if total_hrs else 0
    coord_pct = cat_tot.get('COORD', 0) / total_hrs * 100 if total_hrs else 0
    if design_pct > 40: profile_bits.append(f"design-heavy ({design_pct:.0f}%)")
    if review_pct > 30: profile_bits.append(f"review-heavy ({review_pct:.0f}%)")
    if coord_pct > 30: profile_bits.append(f"coordination-heavy ({coord_pct:.0f}%)")
    if not profile_bits: profile_bits.append(f"balanced ({hv_pct:.0f}% high-value)")
    
    commentary = ', '.join(profile_bits)
    if unclass_pct > 40:
        commentary += f". ⚠ {unclass_pct:.0f}% unclassified — description nudge needed."
    elif unclass_pct > 20:
        commentary += f". {unclass_pct:.0f}% unclassified — description quality gap."
    elif unclass_pct < 10:
        commentary += f". Strong description discipline ({100-unclass_pct:.0f}% visibility)."

    st.info(f"✦ **Commentary**: {commentary}")


def render_overview_tab_v2(meeting, user):
    """OVERVIEW tab v2 — Team summary at top + 12 discipline tabs."""
    review_month = meeting['review_month']
    year, month = map(int, review_month.split('-'))
    month_name = date(year, month, 1).strftime('%B %Y')

    st.markdown(
        f"<div style='background:#F0F7FB;padding:10px 14px;border-radius:8px;"
        f"font-size:12px;color:#185FA5;margin-bottom:12px;'>"
        f"📅 <b>Reviewing:</b> {month_name} · "
        f"<b>Meeting:</b> {meeting.get('scheduled_date', 'TBD')} · "
        f"<b>Status:</b> {STATE_LABEL.get(meeting['status'], meeting['status'])}</div>",
        unsafe_allow_html=True
    )

    # Load data
    entries = load_entries_for_month(year, month)
    members = db.get_members()
    
    if not entries:
        st.warning(f"No timesheet data for {month_name} yet.")
        return

    df = pd.DataFrame(entries)
    df['hrs'] = df['hrs'].astype(float)
    df['description'] = df['description'].fillna('').astype(str)

    # ── Team summary KPIs ──
    excluded_uids = {m['id'] for m in members if m.get('excluded_from_productivity')}
    df_eng = df[~df['uid'].isin(excluded_uids)]
    
    total_hrs = df_eng['hrs'].sum()
    n_reporting = df_eng['uid'].nunique()
    eng_members_total = sum(1 for m in members
                            if m.get('dept') == 'Engineering' and m['id'] not in excluded_uids)
    n_projects = df_eng['proj'].nunique()

    df_eng = df_eng.copy()
    df_eng['Category'] = df_eng.apply(
        lambda r: classify_activity(r['act'], r['description']), axis=1
    )
    cat_totals = df_eng.groupby('Category')['hrs'].sum()
    hv_pct = sum(cat_totals.get(c, 0) for c in ['DESIGN', 'REVIEW', 'COORD']) / total_hrs * 100 if total_hrs else 0
    unclass_pct = cat_totals.get('UNCLASS', 0) / total_hrs * 100 if total_hrs else 0
    leave_pct = cat_totals.get('LEAVE', 0) / total_hrs * 100 if total_hrs else 0

    st.markdown("### 📊 Team Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total hours", f"{total_hrs:,.0f}")
    c2.metric("Reporting", f"{n_reporting} / {eng_members_total}")
    c3.metric("Projects", n_projects)
    c4.metric("High-value", f"{hv_pct:.0f}%")
    c5.metric("Unclassified", f"{unclass_pct:.0f}%", delta_color="inverse")
    c6.metric("Leave", f"{leave_pct:.0f}%")

    st.markdown("---")
    st.markdown("### 🏢 Discipline-wise Dashboards")
    st.caption("Click each tab to view that discipline's detailed dashboard")

    # Order disciplines by hours descending
    df_eng['discipline'] = df_eng['uid'].map(
        lambda u: next((m.get('discipline', '-') for m in members if m['id'] == u), '-')
    )
    disc_order = (df_eng.groupby('discipline')['hrs'].sum()
                       .sort_values(ascending=False)
                       .index.tolist())

    # Filter to disciplines with data (and exclude blank ones)
    disc_order = [d for d in disc_order if d and d != '-' and d != 'Engineering Management']

    if not disc_order:
        st.warning("No discipline-level data to display.")
        return

    # Build tabs
    disc_tabs = st.tabs([f"{d}" for d in disc_order])
    
    for tab, disc_name in zip(disc_tabs, disc_order):
        with tab:
            render_discipline_dashboard(disc_name, members, df, meeting)


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

    # Load all meetings (for selector)
    all_meetings = load_all_meetings()
    if not all_meetings:
        st.warning(
            "No meetings found in the database. Run schema setup (Delivery 1) first."
        )
        return

    # Meeting selector — dropdown to switch between meetings
    def meeting_label(m):
        status_emoji = {
            'DRAFT': '📋', 'PREP_OPEN': '📝', 'PREP_CLOSED': '🔒',
            'IN_MEETING': '🗓', 'COMPLETED': '✅', 'PUBLISHED': '📤', 'ARCHIVED': '🗄'
        }.get(m.get('status', ''), '•')
        return f"{status_emoji} Meeting #{m['meeting_no']:02d} — Reviewing {m['review_month']} — {m.get('status', '?')}"

    # Default to most recent active meeting (or first in list)
    default_idx = 0
    for i, m in enumerate(all_meetings):
        if m.get('status') in ('DRAFT', 'PREP_OPEN', 'PREP_CLOSED', 'IN_MEETING'):
            default_idx = i
            break

    col_sel, col_info = st.columns([3, 1])
    with col_sel:
        picked_idx = st.selectbox(
            "🗓 Select Meeting",
            range(len(all_meetings)),
            format_func=lambda i: meeting_label(all_meetings[i]),
            index=default_idx,
            key='mer_meeting_picker',
        )
    meeting = all_meetings[picked_idx]
    with col_info:
        if meeting.get('status') in ('PUBLISHED', 'ARCHIVED', 'COMPLETED'):
            st.caption(f"📚 Archive view — {meeting.get('status')}")
        else:
            st.caption(f"🔴 Active — {meeting.get('status')}")

    # Tab selector — based on permissions
    if can_access_admin_tabs(user):
        # Super admin / owner — all 4 tabs
        tab_overview, tab_prep, tab_meeting, tab_report = st.tabs(
            ["📊 Overview", "📝 PREP", "🗓 Meeting", "📄 Report"]
        )
        with tab_overview:
            render_overview_tab_v2(meeting, user)  # Upgraded for Delivery 3
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
