"""
mer_report_generator.py
=======================
Auto-generates the Monthly Engineering Review (MER) DOCX report.

Structure mirrors the canonical Meeting #04 Word document.
Only includes sections that have content - empty sections are skipped.
"""
from io import BytesIO
from datetime import date, datetime
import pandas as pd

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

import db


NAVY = RGBColor(0x1F, 0x4E, 0x78)
ACCENT = RGBColor(0x2E, 0x75, 0xB6)
LIGHT_BG = "F2F7FB"
HEADER_BG = "1F4E78"
ROW_ALT = "F8F9FB"
RED = RGBColor(0xC0, 0x00, 0x00)
AMBER = RGBColor(0xBF, 0x8F, 0x00)
GREEN = RGBColor(0x0F, 0x6E, 0x56)
GREY = RGBColor(0x59, 0x59, 0x59)


def _shade_cell(cell, color_hex):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex)
    tc_pr.append(shd)


def _run(para, text, size=11, bold=False, color=None, italic=False):
    r = para.add_run(text or '')
    r.font.name = 'Calibri'
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    if color:
        r.font.color.rgb = color
    return r


def _h1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(8)
    _run(p, text, size=15, bold=True, color=NAVY)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:color'), '2E75B6')
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def _para(doc, text='', size=10, bold=False, color=None, italic=False):
    p = doc.add_paragraph()
    if text:
        _run(p, text, size=size, bold=bold, color=color, italic=italic)
    return p


def _bullet(doc, text, size=10):
    p = doc.add_paragraph(style='List Bullet')
    _run(p, text, size=size)
    return p


def _header_cell(cell, text):
    _shade_cell(cell, HEADER_BG)
    p = cell.paragraphs[0]
    _run(p, text, size=10, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def _data_cell(cell, text, bold=False, color=None, align=None, size=10, fill=None, italic=False):
    if fill:
        _shade_cell(cell, fill)
    p = cell.paragraphs[0]
    if align == 'right':
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == 'center':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, text or '', size=size, bold=bold, color=color, italic=italic)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


# ── Loaders ──
def _load_meeting(meeting_id):
    sb = db.get_client()
    r = sb.table('ts_mer_meetings').select('*').eq('id', meeting_id).execute()
    return r.data[0] if r.data else None


def _load_inputs(meeting_id):
    sb = db.get_client()
    r = sb.table('ts_mer_inputs').select('*').eq('meeting_id', meeting_id).execute()
    return r.data or []


def _load_actions():
    sb = db.get_client()
    r = sb.table('ts_mer_actions').select('*').in_('status', ['OPEN', 'IN_PROGRESS']).order('due_date').execute()
    return r.data or []


def _load_entries_for_month(year, month):
    sb = db.get_client()
    start = date(year, month, 1).isoformat()
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1).isoformat()
    out = []
    offset = 0
    while True:
        r = (sb.table('ts_entries').select('*')
               .gte('entry_date', start).lt('entry_date', end)
               .order('entry_date').order('id')
               .range(offset, offset + 999).execute())
        batch = r.data or []
        out.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return out


def _narrative(meeting, key, default=None):
    n = meeting.get('meeting_narrative')
    if isinstance(n, dict):
        v = n.get(key)
        return v if v is not None else default
    return default


# ── Cover ──
def _build_cover(doc, meeting):
    year, month = map(int, meeting['review_month'].split('-'))
    month_name = date(year, month, 1).strftime('%B %Y')
    end_of_month = (date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1) - pd.Timedelta(days=1))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    _run(p, "GCC ENGINEERING", size=22, bold=True, color=NAVY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "Monthly Engineering Review — Meeting Minutes", size=13, color=GREY, italic=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    _run(p, f"Meeting #{meeting['meeting_no']:02d}  ·  Reviewing {month_name}",
         size=16, bold=True, color=ACCENT)

    table = doc.add_table(rows=4, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    end_str = end_of_month.strftime('%d-%b-%Y') if hasattr(end_of_month, 'strftime') else str(end_of_month)[:10]
    rows = [
        ("Meeting", "GCC Engineering Monthly Meeting",
         "Meeting No", f"{meeting['meeting_no']:02d}"),
        ("Date (data as of)", end_str,
         "Held on", str(meeting.get('scheduled_date') or '—')[:10]),
        ("Location", "GCC Arioli, Mumbai",
         "Status", meeting.get('status', '—')),
        ("Chaired by", meeting.get('reviewer') or 'Sangeeta Salvi',
         "Prepared by", meeting.get('chair') or 'Hariprakash Pandey'),
    ]
    for i, (k1, v1, k2, v2) in enumerate(rows):
        row = table.rows[i]
        _data_cell(row.cells[0], k1, bold=True, fill=LIGHT_BG)
        _data_cell(row.cells[1], v1)
        _data_cell(row.cells[2], k2, bold=True, fill=LIGHT_BG)
        _data_cell(row.cells[3], v2)
    _para(doc)
    _para(doc, "Attendees: All Engineering Team (EOUK_FE)", italic=True)


# ── Section builders ──
def _build_project_status(doc, meeting, entries_df, num):
    project_table = _narrative(meeting, 'project_status_table')

    _h1(doc, f"{num}. Project Status — Key Updates from Each Project")

    if project_table and isinstance(project_table, list) and len(project_table) > 0:
        table = doc.add_table(rows=len(project_table) + 1, cols=5)
        for i, h in enumerate(['Sl.', 'Project Name', 'Project Status (Phase)', 'Present Status', 'Activities / Concerns']):
            _header_cell(table.rows[0].cells[i], h)
        for idx, p in enumerate(project_table, 1):
            row = table.rows[idx]
            fill = ROW_ALT if idx % 2 == 0 else None
            _data_cell(row.cells[0], str(p.get('sl', idx)), align='center', fill=fill)
            _data_cell(row.cells[1], p.get('project', ''), bold=True, fill=fill)
            _data_cell(row.cells[2], p.get('phase', ''), fill=fill)
            _data_cell(row.cells[3], p.get('present_status', ''), fill=fill)
            _data_cell(row.cells[4], p.get('activities', ''), fill=fill)
        return

    if len(entries_df) == 0:
        _para(doc, "No project activity recorded.", italic=True, color=GREY)
        return

    # Fallback: just project + hours
    proj_hours = entries_df.groupby('proj')['hrs'].sum().sort_values(ascending=False)
    table = doc.add_table(rows=len(proj_hours) + 1, cols=3)
    for i, h in enumerate(['Sl.', 'Project', 'Hours']):
        _header_cell(table.rows[0].cells[i], h)
    for idx, (pname, hrs) in enumerate(proj_hours.items(), 1):
        row = table.rows[idx]
        fill = ROW_ALT if idx % 2 == 0 else None
        _data_cell(row.cells[0], str(idx), align='center', fill=fill)
        _data_cell(row.cells[1], pname, bold=True, fill=fill)
        _data_cell(row.cells[2], f"{hrs:.0f}", align='right', fill=fill)


def _build_misc(doc, meeting, num):
    items = _narrative(meeting, 'misc_activities')
    if not items:
        return False
    _h1(doc, f"{num}. Miscellaneous Activities")
    for it in items:
        _bullet(doc, it)
    return True


def _build_coordination(doc, meeting, inputs, num):
    points = _narrative(meeting, 'coordination_points')
    if not points:
        concerns = [(i.get('discipline', '?'), i.get('concerns', '')) for i in inputs if i.get('concerns')]
        if not concerns:
            return False
        _h1(doc, f"{num}. Major Issues & Interdisciplinary Coordination Points")
        for disc, txt in concerns:
            p = doc.add_paragraph()
            _run(p, f"{disc}: ", size=10, bold=True, color=NAVY)
            _run(p, txt, size=10)
        return True
    _h1(doc, f"{num}. Major Issues & Interdisciplinary Coordination Points")
    for p in points:
        _bullet(doc, p)
    return True


def _build_future(doc, meeting, num):
    points = _narrative(meeting, 'future_projection')
    if not points:
        return False
    _h1(doc, f"{num}. Future Projection of Projects Status")
    for p in points:
        _bullet(doc, p)
    return True


def _build_manhours(doc, meeting, entries_df, members, num):
    _h1(doc, f"{num}. Manhours Booking — Discipline-wise")

    narr = _narrative(meeting, 'manhours_narrative',
                      "Manhours must be recorded diligently. Accurate booking is essential for project claims, "
                      "and ensures the value contributed by the GCC Team is clearly demonstrated. "
                      "Workhours analysis can be extracted from Timesheet.")
    _para(doc, narr)
    _para(doc)

    if len(entries_df) == 0:
        _para(doc, "No timesheet data for this period.", italic=True, color=GREY)
        return

    mem_lookup = {m['id']: m for m in members}
    entries_df = entries_df.copy()
    entries_df['discipline'] = entries_df['uid'].map(lambda u: mem_lookup.get(u, {}).get('discipline', '-'))

    excluded_uids = {m['id'] for m in members if m.get('excluded_from_productivity')}
    df_eng = entries_df[~entries_df['uid'].isin(excluded_uids)]
    df_mgmt = entries_df[entries_df['uid'].isin(excluded_uids)]

    disc = (df_eng.groupby('discipline')
                  .agg(Hours=('hrs', 'sum'), Members=('uid', 'nunique'))
                  .reset_index()
                  .sort_values('Hours', ascending=False))

    grand_total = df_eng['hrs'].sum() + df_mgmt['hrs'].sum()

    table = doc.add_table(rows=len(disc) + 3, cols=4)
    for i, h in enumerate(['Discipline', 'Members', 'Hours', '% of Total']):
        _header_cell(table.rows[0].cells[i], h)

    for idx, (_, r) in enumerate(disc.iterrows(), 1):
        row = table.rows[idx]
        pct = r['Hours'] / grand_total * 100 if grand_total else 0
        fill = ROW_ALT if idx % 2 == 0 else None
        _data_cell(row.cells[0], r['discipline'], bold=True, fill=fill)
        _data_cell(row.cells[1], str(int(r['Members'])), align='center', fill=fill)
        _data_cell(row.cells[2], f"{r['Hours']:.0f}", align='right', bold=True, fill=fill)
        _data_cell(row.cells[3], f"{pct:.0f}%", align='right', fill=fill)

    mgmt_row = table.rows[len(disc) + 1]
    _data_cell(mgmt_row.cells[0], "Engineering Management (HP + Sangeeta)", bold=True, fill=LIGHT_BG)
    _data_cell(mgmt_row.cells[1], str(df_mgmt['uid'].nunique()), align='center', fill=LIGHT_BG)
    _data_cell(mgmt_row.cells[2], f"{df_mgmt['hrs'].sum():.0f}", align='right', bold=True, fill=LIGHT_BG)
    _data_cell(mgmt_row.cells[3], "Excluded", italic=True, fill=LIGHT_BG)

    total_row = table.rows[-1]
    for i in range(4):
        _shade_cell(total_row.cells[i], "1F4E78")
    _data_cell(total_row.cells[0], "TOTAL", bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    _data_cell(total_row.cells[1], str(df_eng['uid'].nunique() + df_mgmt['uid'].nunique()),
               align='center', bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    _data_cell(total_row.cells[2], f"{grand_total:.0f}", align='right', bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    _data_cell(total_row.cells[3], "100%", align='right', bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))


def _build_strength(doc, members, num):
    """Engineering Strength matching Word doc: Head/Dy Head separate, disciplines below.
    Excludes admins not assigned to disciplines."""
    _h1(doc, f"{num}. Engineering Strength — Discipline-wise")

    # Identify HP and Sangeeta (id=2, id=1)
    head = next((m for m in members if m['id'] == 1), None)
    dy = next((m for m in members if m['id'] == 2), None)
    head_id = head['id'] if head else None
    dy_id = dy['id'] if dy else None

    # Exclude HP, Sangeeta, and admin-only members (super_admin but not discipline lead) from discipline counts
    disc_members = []
    for m in members:
        if m.get('dept') != 'Engineering':
            continue
        if m['id'] in (head_id, dy_id):
            continue
        if m.get('discipline') == 'Engineering Management':
            continue  # admins like Prachi/Pradeep/Aarti or stragglers
        if m.get('is_super_admin') and not m.get('is_discipline_lead'):
            continue
        disc_members.append(m)

    # Group by discipline
    disc_counts = {}
    disc_leads = {}
    for m in disc_members:
        d = (m.get('discipline') or 'Unspecified').strip()
        disc_counts[d] = disc_counts.get(d, 0) + 1
        if m.get('is_discipline_lead') and (m.get('leads_discipline') or '').strip() == d:
            disc_leads[d] = m['name']

    rows = []
    if head:
        rows.append(('Engineering Head', 1, head['name']))
    if dy:
        rows.append(('Dy Engineering Head', 1, dy['name']))
    for d, count in sorted(disc_counts.items(), key=lambda x: -x[1]):
        rows.append((d, count, disc_leads.get(d, '—')))

    total = sum(r[1] for r in rows)

    table = doc.add_table(rows=len(rows) + 2, cols=3)
    for i, h in enumerate(['Discipline', 'Strength', 'Discipline Lead']):
        _header_cell(table.rows[0].cells[i], h)

    for idx, (d, count, lead) in enumerate(rows, 1):
        row = table.rows[idx]
        fill = ROW_ALT if idx % 2 == 0 else None
        _data_cell(row.cells[0], d, bold=(idx <= 2), fill=fill)
        _data_cell(row.cells[1], str(count), align='center', bold=True, fill=fill)
        _data_cell(row.cells[2], lead, fill=fill)

    total_row = table.rows[-1]
    for i in range(3):
        _shade_cell(total_row.cells[i], "1F4E78")
    _data_cell(total_row.cells[0], "TOTAL", bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    _data_cell(total_row.cells[1], str(total), align='center', bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    _data_cell(total_row.cells[2], "All disciplines have nominated leads", bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))


def _build_assurance(doc, meeting, num):
    a = _narrative(meeting, 'assurance_status')
    if not a:
        return False
    _h1(doc, f"{num}. Assurance")
    if isinstance(a, dict):
        if a.get('paragraph_1'):
            _para(doc, a['paragraph_1'])
        if a.get('paragraph_2'):
            _para(doc, a['paragraph_2'])
        if a.get('status'):
            p = doc.add_paragraph()
            _run(p, "Status: ", size=10, bold=True, color=NAVY)
            _run(p, a['status'], size=10)
    else:
        _para(doc, str(a))
    return True


def _build_critical(doc, meeting, inputs, num):
    points = _narrative(meeting, 'critical_decisions')
    if not points:
        prep_items = [(i.get('discipline', '?'), i.get('critical_items', ''))
                      for i in inputs if i.get('critical_items')]
        if not prep_items:
            return False
        _h1(doc, f"{num}. Risks, Changes & Critical Decisions Needed")
        for disc, txt in prep_items:
            p = doc.add_paragraph()
            _run(p, f"{disc}: ", size=10, bold=True, color=NAVY)
            _run(p, txt, size=10)
        return True
    _h1(doc, f"{num}. Risks, Changes & Critical Decisions Needed")
    for p in points:
        _bullet(doc, p)
    return True


def _build_suggestions(doc, meeting, num):
    points = _narrative(meeting, 'suggestions')
    if not points:
        return False
    _h1(doc, f"{num}. Suggestions")
    for p in points:
        _bullet(doc, p)
    return True


def _build_software_training(doc, meeting, num):
    st = _narrative(meeting, 'software_training')
    if not st or not isinstance(st, dict):
        return False
    _h1(doc, f"{num}. Software Training Sessions")

    if st.get('narrative_points'):
        for n in st['narrative_points']:
            _bullet(doc, n)

    tt = st.get('training_table')
    if tt:
        _para(doc)
        _para(doc, "Training Status:", bold=True)
        table = doc.add_table(rows=len(tt) + 1, cols=4)
        for i, h in enumerate(['Sl.', 'Training Description', 'Participants', 'Status']):
            _header_cell(table.rows[0].cells[i], h)
        for idx, t in enumerate(tt, 1):
            row = table.rows[idx]
            fill = ROW_ALT if idx % 2 == 0 else None
            _data_cell(row.cells[0], str(t.get('sl', idx)), align='center', fill=fill)
            _data_cell(row.cells[1], t.get('training', ''), bold=True, fill=fill)
            _data_cell(row.cells[2], t.get('participants', ''), align='center', fill=fill)
            status = t.get('status', '')
            color = GREEN if status == 'Conducted' else (AMBER if status == 'Under progress' else GREY)
            _data_cell(row.cells[3], status, color=color, bold=True, fill=fill)
    return True


def _build_quality(doc, meeting, num):
    items = _narrative(meeting, 'what_we_can_do_further')
    if not items:
        return False
    _h1(doc, f"{num}. What We Can Do Further — Quality Framework")
    for it in items:
        if isinstance(it, dict):
            p = doc.add_paragraph(style='List Bullet')
            _run(p, it.get('point', ''), size=10)
            if it.get('update'):
                up = doc.add_paragraph()
                up.paragraph_format.left_indent = Inches(0.5)
                _run(up, "Update: ", size=9, bold=True, color=ACCENT, italic=True)
                _run(up, it['update'], size=9, italic=True)
        else:
            _bullet(doc, str(it))
    return True


def _build_actions(doc, actions, num):
    if not actions:
        return False
    _h1(doc, f"{num}. Open Action Items")
    table = doc.add_table(rows=len(actions) + 1, cols=5)
    for i, h in enumerate(['Sl.', 'Action', 'Owner', 'Due', 'Status']):
        _header_cell(table.rows[0].cells[i], h)
    for idx, a in enumerate(actions, 1):
        row = table.rows[idx]
        fill = ROW_ALT if idx % 2 == 0 else None
        _data_cell(row.cells[0], str(idx), align='center', fill=fill)
        _data_cell(row.cells[1], a.get('action_text', ''), fill=fill)
        _data_cell(row.cells[2], a.get('owner_name', '—'), fill=fill)
        _data_cell(row.cells[3], str(a.get('due_date') or '—'), align='center', fill=fill)
        status = a.get('status', 'OPEN')
        color = GREEN if status == 'CLOSED' else (AMBER if status == 'IN_PROGRESS' else None)
        _data_cell(row.cells[4], status, color=color, bold=True, fill=fill)
    return True


# ── Main ──
def generate_report(meeting_id):
    """Generate the MER DOCX. Returns BytesIO."""
    meeting = _load_meeting(meeting_id)
    if not meeting:
        raise ValueError(f"Meeting {meeting_id} not found")

    year, month = map(int, meeting['review_month'].split('-'))
    entries = _load_entries_for_month(year, month)
    members = db.get_members()
    inputs = _load_inputs(meeting_id)
    actions = _load_actions()

    df = pd.DataFrame(entries) if entries else pd.DataFrame(columns=['uid', 'proj', 'hrs', 'description', 'act'])
    if len(df):
        df['hrs'] = df['hrs'].astype(float)

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Header & footer
    h = doc.sections[0].header.paragraphs[0]
    h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(h, f"GCC Engineering Monthly Review · Meeting #{meeting['meeting_no']:02d}",
         size=9, color=GREY, italic=True)

    f = doc.sections[0].footer.paragraphs[0]
    f.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(f, f"Prepared by {meeting.get('chair') or 'Hariprakash Pandey'} · "
            f"Chaired by {meeting.get('reviewer') or 'Sangeeta Salvi'} · "
            f"Generated {datetime.utcnow().strftime('%d-%b-%Y')}",
         size=9, color=GREY, italic=True)

    # ── Build sections — only include if has content; auto-numbered ──
    _build_cover(doc, meeting)

    n = 1
    _build_project_status(doc, meeting, df, n); n += 1
    if _build_misc(doc, meeting, n): n += 1
    if _build_coordination(doc, meeting, inputs, n): n += 1
    if _build_future(doc, meeting, n): n += 1
    _build_manhours(doc, meeting, df, members, n); n += 1
    _build_strength(doc, members, n); n += 1
    if _build_assurance(doc, meeting, n): n += 1
    if _build_critical(doc, meeting, inputs, n): n += 1
    if _build_suggestions(doc, meeting, n): n += 1
    if _build_software_training(doc, meeting, n): n += 1
    if _build_quality(doc, meeting, n): n += 1
    if _build_actions(doc, actions, n): n += 1

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def generate_report_filename(meeting):
    return (f"GCC_MER_Meeting_{meeting['meeting_no']:02d}_"
            f"{meeting['review_month'].replace('-', '_')}.docx")
