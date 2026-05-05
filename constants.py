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

# Departments and their disciplines
DEPT_DISCIPLINES = {
    "Engineering": [
        "Engineering Management", "Process", "HSE + Process Safety", "Firefighting",
        "Electrical", "Mech-Rotary & Package", "Mech-Rotary", "Mech-Static", "Mech-Heater",
        "Instrumentation", "Piping & layout", "CAD", "Piping Stress", "Piping Materials",
        "Civil & Structural", "Assurance", "ESG"
    ],
    "Project": ["Project Management", "Project control", "Document Control"],
    "Procurement": ["Procurement", "Expediting", "Logistics"]
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
    """Get all activities (built-in + custom) for a discipline."""
    builtin = DISCIPLINE_ACTIVITIES.get(discipline, [("OTHERS", "Others")])
    if custom_acts:
        custom_for_disc = [(c["code"], c["description"])
                           for c in custom_acts if c.get("discipline") == discipline]
        return builtin + custom_for_disc
    return builtin


def get_all_disciplines():
    """Flat list of all disciplines across all departments."""
    result = []
    for dept, discs in DEPT_DISCIPLINES.items():
        result.extend(discs)
    return sorted(set(result))
