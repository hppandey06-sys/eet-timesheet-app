"""
Constants and helpers — pulled from the original HTML app.
"""
from datetime import date, timedelta

APP_TITLE = "EET Fuels Team Timesheet"
MAX_DAY_HRS = 10

# Public holidays
HOLIDAYS_2026 = {
    "2026-01-01": "New Year's Day",
    "2026-01-26": "Republic Day",
    "2026-03-04": "Holi",
    "2026-04-03": "Good Friday",
    "2026-05-01": "Maharashtra Day",
    "2026-05-25": "Spring Bank Holiday",
    "2026-09-14": "Ganesh Chaturthi",
    "2026-10-02": "Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-12-25": "Christmas",
}

# Companies in the EET group
COMPANIES = ["GCC", "EETH", "EETF", "EET", "STL"]

# Departments and their disciplines
DEPT_DISCIPLINES = {
    "Engineering": [
        "Engineering Management", "Process", "HSE + Process Safety", "Firefighting",
        "Electrical", "Mech-Rotary & Package", "Mech-Rotary", "Mech-Static", "Mech-Heater",
        "Instrumentation", "Piping & layout", "CAD", "Piping Stress", "Piping Materials",
        "Civil & Structural", "Assurance", "ESG"
    ],
    "Project": ["Project Management", "Project control", "Document Control"],
    "Procurement": ["Procurement", "Expediting", "Logistics"],
    "Legal": ["Legal"],
    "Business Development": ["Business Development"],
    "Environmental": ["Environmental"],
    "Safety": ["Safety"],
    "Admin": ["Admin"],
    "Finance": ["Finance Operations", "Finance"],
    "Communications": ["Communications"],
    "Stanlow Terminal": ["Stanlow Operations"],
}

# Built-in activity codes per discipline
DISCIPLINE_ACTIVITIES = {
    "Process": [
        ("PRS-01", "PFD/P&ID Development"),
        ("PRS-02", "P&ID Review"),
        ("PRS-03", "Heat & Material Balance"),
        ("PRS-04", "Equipment Sizing"),
        ("PRS-05", "HAZOP Participation"),
        ("PRS-06", "Process Datasheet Preparation"),
        ("PRS-07", "Vendor Document Review"),
        ("PRS-08", "Technical Bid Evaluation"),
        ("OTHERS", "Others"),
    ],
    "Electrical": [
        ("ELEC-01", "Single Line Diagram"),
        ("ELEC-02", "Cable Schedule"),
        ("ELEC-03", "Equipment Datasheet"),
        ("ELEC-04", "Vendor Document Review"),
        ("ELEC-05", "Site Inspection"),
        ("OTHERS", "Others"),
    ],
    "Instrumentation": [
        ("INS-01", "Instrument Index"),
        ("INS-02", "Loop Diagrams"),
        ("INS-03", "Datasheet Preparation"),
        ("INS-04", "Cable Routing"),
        ("INS-05", "DCS Configuration"),
        ("OTHERS", "Others"),
    ],
    "Piping & layout": [
        ("PIP-01", "3D Modeling"),
        ("PIP-02", "Piping Layout"),
        ("PIP-03", "MTO Generation"),
        ("PIP-04", "Isometric Drawings"),
        ("PIP-05", "Stress Analysis Coordination"),
        ("OTHERS", "Others"),
    ],
    "Civil & Structural": [
        ("CIV-01", "Foundation Design"),
        ("CIV-02", "Steel Structure"),
        ("CIV-03", "Building Design"),
        ("CIV-04", "Site Survey"),
        ("OTHERS", "Others"),
    ],
    "Mech-Static": [
        ("MS-01", "Vessel Design"),
        ("MS-02", "Heat Exchanger"),
        ("MS-03", "Tank Design"),
        ("MS-04", "Datasheet Preparation"),
        ("OTHERS", "Others"),
    ],
    "Mech-Rotary & Package": [
        ("MR-01", "Pump Specification"),
        ("MR-02", "Compressor Package"),
        ("MR-03", "Vendor Coordination"),
        ("OTHERS", "Others"),
    ],
    "Mech-Rotary": [
        ("MR-01", "Pump Specification"),
        ("MR-02", "Compressor Package"),
        ("MR-03", "Vendor Coordination"),
        ("OTHERS", "Others"),
    ],
    "CAD": [
        ("CAD-01", "Drafting"),
        ("CAD-02", "3D Modeling Support"),
        ("CAD-03", "Drawing Review"),
        ("OTHERS", "Others"),
    ],
    "HSE + Process Safety": [
        ("HSE-01", "Risk Assessment"),
        ("HSE-02", "HAZOP/SIL"),
        ("HSE-03", "Safety Documentation"),
        ("HSE-04", "QRA"),
        ("OTHERS", "Others"),
    ],
    "ESG": [
        ("ESG-01", "Sustainability Reporting"),
        ("ESG-02", "Carbon Footprint Analysis"),
        ("ESG-03", "ESG Documentation"),
        ("OTHERS", "Others"),
    ],
    "Engineering Management": [
        ("EM-01", "Project Coordination"),
        ("EM-02", "Schedule Management"),
        ("EM-03", "Discipline Coordination"),
        ("EM-04", "Client Coordination"),
        ("OTHERS", "Others"),
    ],
    "Document Control": [
        ("DC-01", "Document Management"),
        ("DC-02", "Transmittal Preparation"),
        ("DC-03", "Filing & Archiving"),
        ("OTHERS", "Others"),
    ],
    "Project Management": [
        ("PM-01", "Schedule Tracking"),
        ("PM-02", "Risk Management"),
        ("PM-03", "Stakeholder Communication"),
        ("PM-04", "Reporting"),
        ("OTHERS", "Others"),
    ],
    "Project control": [
        ("PC-01", "Cost Control"),
        ("PC-02", "Schedule Control"),
        ("PC-03", "Change Management"),
        ("OTHERS", "Others"),
    ],
}


# ── Productivity categories (8 segments) ──
# Background classification of activity codes for productivity reporting.
# Visible to admins / discipline leads only; members never see these.
ACTIVITY_CATEGORIES = {
    "1": ("Production of deliverables", "Direct"),
    "2": ("Checking & review", "Direct"),
    "3": ("Studies & analysis", "Direct"),
    "4": ("Meetings & coordination", "Direct"),
    "5": ("Site & construction support", "Direct"),
    "6": ("Engg. standards & QMS development", "Indirect"),
    "7": ("Training & development", "Indirect"),
    "8": ("Admin, leave & others", "Indirect"),
}


def category_label(cat_no):
    """'1' -> '1. Production of deliverables'"""
    c = ACTIVITY_CATEGORIES.get(str(cat_no))
    return f"{cat_no}. {c[0]}" if c else f"{cat_no}. Unknown"


CATEGORY_OPTIONS = [category_label(k) for k in ACTIVITY_CATEGORIES]


# Category of each BUILT-IN code, per discipline (custom codes carry their
# category in the ts_custom_acts.category column instead).
BUILTIN_ACT_CATEGORIES = {
    "Process": {"PRS-01": "1", "PRS-02": "2", "PRS-03": "3", "PRS-04": "3",
                "PRS-05": "3", "PRS-06": "1", "PRS-07": "2", "PRS-08": "2"},
    "Electrical": {"ELEC-01": "1", "ELEC-02": "1", "ELEC-03": "1",
                   "ELEC-04": "2", "ELEC-05": "5"},
    "Instrumentation": {"INS-01": "1", "INS-02": "1", "INS-03": "1",
                        "INS-04": "1", "INS-05": "1"},
    "Piping & layout": {"PIP-01": "1", "PIP-02": "1", "PIP-03": "1",
                        "PIP-04": "1", "PIP-05": "4"},
    "Civil & Structural": {"CIV-01": "1", "CIV-02": "1", "CIV-03": "1", "CIV-04": "5"},
    "Mech-Static": {"MS-01": "1", "MS-02": "1", "MS-03": "1", "MS-04": "1"},
    "Mech-Rotary & Package": {"MR-01": "1", "MR-02": "1", "MR-03": "4"},
    "Mech-Rotary": {"MR-01": "1", "MR-02": "1", "MR-03": "4"},
    "CAD": {"CAD-01": "1", "CAD-02": "1", "CAD-03": "2"},
    "HSE + Process Safety": {"HSE-01": "3", "HSE-02": "3", "HSE-03": "1", "HSE-04": "3"},
    "ESG": {"ESG-01": "1", "ESG-02": "3", "ESG-03": "1"},
    "Engineering Management": {"EM-01": "4", "EM-02": "4", "EM-03": "4", "EM-04": "4"},
    "Document Control": {"DC-01": "1", "DC-02": "1", "DC-03": "8"},
    "Project Management": {"PM-01": "4", "PM-02": "3", "PM-03": "4", "PM-04": "1"},
    "Project control": {"PC-01": "3", "PC-02": "3", "PC-03": "4"},
}


def get_act_category(code, discipline, custom_acts=None):
    """Resolve a code to its category number ('1'..'8').

    Order: custom code category column -> built-in mapping -> '8' (default).
    """
    code = (code or "").upper()
    if custom_acts:
        for c in custom_acts:
            if c.get("code", "").upper() == code and c.get("discipline") == discipline:
                return str(c.get("category") or "8")
    return BUILTIN_ACT_CATEGORIES.get(discipline, {}).get(code, "8")


def todayIST():
    """Today's date in YYYY-MM-DD format (server-side)."""
    return date.today().strftime("%Y-%m-%d")


def format_date_short(d):
    """Format YYYY-MM-DD to '12 Apr' style."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime("%d %b")


def format_date_full(d):
    """Format to '12 Apr 2026'."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime("%d %b %Y")


def get_month_label(ym):
    """Convert '2026-04' to 'April 2026'."""
    y, m = ym.split("-")
    return date(int(y), int(m), 1).strftime("%B %Y")


def get_working_days(year, month):
    """Get list of working days for given month (Mon-Fri, excluding holidays)."""
    days = []
    d = date(year, month, 1)
    while d.month == month:
        ds = d.strftime("%Y-%m-%d")
        if d.weekday() < 5 and ds not in HOLIDAYS_2026:
            days.append(ds)
        d += timedelta(days=1)
    return days


def get_week_dates(week_offset=0):
    """Get list of 7 dates (Mon-Sun) for given week offset from today."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    monday += timedelta(weeks=week_offset)
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def get_day_name(date_str):
    """Get day name e.g. 'Monday' from YYYY-MM-DD."""
    d = date.fromisoformat(date_str)
    return d.strftime("%A")


def is_weekend(date_str):
    """Check if date is Saturday or Sunday."""
    d = date.fromisoformat(date_str)
    return d.weekday() >= 5


def is_holiday(date_str):
    """Check if date is a public holiday."""
    return date_str in HOLIDAYS_2026


def get_holiday_name(date_str):
    """Get holiday name if date is a holiday, else None."""
    return HOLIDAYS_2026.get(date_str)


def get_activities_for_discipline(discipline, custom_acts=None):
    """Get all activities for a discipline.

    After the Delivery 4A2 migration, ALL codes live in the ts_custom_acts
    table (passed in as custom_acts) and are fully editable in the admin
    panel. DISCIPLINE_ACTIVITIES above is retained as SEED/FALLBACK data
    only — used if the database has no codes for a discipline, so time
    booking can never break.

    OTHERS is always appended if not present.
    """
    result = []
    if custom_acts:
        result = [(c["code"], c["description"])
                  for c in custom_acts if c.get("discipline") == discipline]
    if not result:
        result = [(c, d) for c, d in DISCIPLINE_ACTIVITIES.get(discipline, [])
                  if c != "OTHERS"]
    if "OTHERS" not in [c for c, _ in result]:
        result.append(("OTHERS", "Others"))
    return result


def get_all_disciplines():
    """Flat list of all disciplines across all departments."""
    result = []
    for dept, discs in DEPT_DISCIPLINES.items():
        result.extend(discs)
    return sorted(set(result))
