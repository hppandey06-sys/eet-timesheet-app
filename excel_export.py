"""
Excel export — generates per-member, per-project, per-month timesheet
in the DC Power format.
"""

from io import BytesIO
from datetime import date, timedelta, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import calendar


def export_member_timesheet(member, project_name, project_acts, entries,
                            from_date, to_date, company=None):
    """
    Generate Excel timesheet matching the DC Power format.

    Args:
        member: dict with 'name', 'company', 'discipline'
        project_name: e.g., 'DC Power'
        project_acts: list of dicts with 'code', 'description'
        entries: list of entries for this member + project + date range
        from_date, to_date: date range
        company: org name (optional, defaults to member's company)
    """
    wb = Workbook()
    wb.remove(wb.active)

    # Group dates by month
    months = {}
    cur = date.fromisoformat(from_date) if isinstance(from_date, str) else from_date
    end = date.fromisoformat(to_date) if isinstance(to_date, str) else to_date

    while cur <= end:
        ym = cur.strftime("%Y-%m")
        if ym not in months:
            months[ym] = []
        months[ym].append(cur)
        cur += timedelta(days=1)

    org_name = company or member.get("company", "GCC")
    member_name = member.get("name", "Unknown")

    # Borders and styles
    thin = Side(border_style="thin", color="000000")
    border = Border(top=thin, left=thin, right=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="4472C4")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    title_font = Font(bold=True, size=14, color="1F4E79")
    weekend_fill = PatternFill("solid", fgColor="F2F2F2")
    total_fill = PatternFill("solid", fgColor="FFE699")
    total_font = Font(bold=True, size=11)

    for ym, dates in months.items():
        month_label = dates[0].strftime("%b %y")
        ws = wb.create_sheet(month_label)

        # Title
        ws["A1"] = f"Timesheet for {project_name}"
        ws["A1"].font = title_font
        ws.merge_cells(f"A1:{get_column_letter(len(dates) + 1)}1")

        ws["A2"] = f"Timesheet - {member_name}."
        ws["A2"].font = Font(bold=True, size=12)
        ws.merge_cells(f"A2:{get_column_letter(len(dates) + 1)}2")

        ws["A3"] = "Month:"
        ws["A3"].font = Font(bold=True)
        ws["B3"] = dates[0].replace(day=1)
        ws["B3"].number_format = "mmm-yy"

        ws["A4"] = "Org. Name"
        ws["A4"].font = Font(bold=True)
        ws["B4"] = org_name

        # Headers row
        ws["A6"] = "Hours Worked (max. 8hrs per day)"
        ws["A6"].font = Font(italic=True, size=10, color="606060")
        ws.merge_cells(f"A6:{get_column_letter(len(dates) + 1)}6")

        # Date row
        ws["A7"] = "Date:"
        ws["A7"].font = Font(bold=True)
        ws["A7"].fill = header_fill
        ws["A7"].font = header_font
        ws["A7"].border = border
        ws["A7"].alignment = Alignment(horizontal="center", vertical="center")

        for i, d in enumerate(dates):
            cell = ws.cell(row=7, column=i + 2)
            cell.value = d
            cell.number_format = "dd-mmm"
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[get_column_letter(i + 2)].width = 9

        # Day name row
        ws["A8"] = ""
        ws["A8"].fill = header_fill
        ws["A8"].border = border
        for i, d in enumerate(dates):
            cell = ws.cell(row=8, column=i + 2)
            cell.value = d.strftime("%a")
            cell.font = Font(italic=True, size=9, color="606060")
            cell.alignment = Alignment(horizontal="center")
            cell.border = border
            if d.weekday() >= 5:
                cell.fill = weekend_fill

        # Workstream/Activity heading
        ws["A9"] = "Activity Codes"
        ws["A9"].font = Font(bold=True, color="1F4E79")
        ws["A9"].fill = PatternFill("solid", fgColor="D9E1F2")

        # Activity rows
        row_num = 10
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]

        # Filter entries to this project & date range
        proj_entries = [e for e in entries if e.get("proj") == project_name and e.get("entry_date") in date_strs]

        if not project_acts:
            # No project-specific codes — list activity codes used
            used_acts = sorted(set((e.get("act"), "") for e in proj_entries))
            project_acts = [{"code": code, "description": desc} for code, desc in used_acts] or [{"code": "OTHERS", "description": "Other"}]

        for act_info in project_acts:
            code = act_info["code"]
            desc = act_info.get("description", "")
            label = f"{code} - {desc}" if desc else code

            cell = ws.cell(row=row_num, column=1)
            cell.value = label
            cell.font = Font(bold=True, size=10)
            cell.border = border
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            ws.column_dimensions["A"].width = 32

            # Fill hours per day
            for i, d in enumerate(dates):
                ds = d.strftime("%Y-%m-%d")
                hrs_for_day = sum(
                    float(e.get("hrs", 0)) for e in proj_entries
                    if e.get("entry_date") == ds and e.get("act") == code
                )
                cell = ws.cell(row=row_num, column=i + 2)
                cell.value = hrs_for_day if hrs_for_day > 0 else None
                cell.alignment = Alignment(horizontal="center")
                cell.border = border
                if d.weekday() >= 5:
                    cell.fill = weekend_fill

            row_num += 1

        # Totals row
        total_row = row_num
        ws.cell(row=total_row, column=1).value = "Totals Hour"
        ws.cell(row=total_row, column=1).font = total_font
        ws.cell(row=total_row, column=1).fill = total_fill
        ws.cell(row=total_row, column=1).border = border

        for i, d in enumerate(dates):
            col_letter = get_column_letter(i + 2)
            cell = ws.cell(row=total_row, column=i + 2)
            cell.value = f"=SUM({col_letter}10:{col_letter}{total_row - 1})"
            cell.font = total_font
            cell.fill = total_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center")

        # Grand total
        total_label_col = get_column_letter(len(dates) + 2)
        ws.cell(row=total_row, column=len(dates) + 2).value = f"=SUM(B{total_row}:{get_column_letter(len(dates) + 1)}{total_row})"
        ws.cell(row=total_row, column=len(dates) + 2).font = Font(bold=True, size=11, color="1F4E79")
        ws.cell(row=total_row, column=len(dates) + 2).fill = total_fill
        ws.cell(row=total_row, column=len(dates) + 2).border = border

        # Freeze panes
        ws.freeze_panes = "B9"

    # Output buffer
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
