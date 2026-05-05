# EET Fuels Team Timesheet — Streamlit App

A Python web application for tracking team timesheets, replacing the legacy GitHub Pages HTML.

## Features

- 📋 Weekly timesheet grid with day-by-day save
- 📝 Project + Activity + Hours + Description per entry
- 🔄 Pre-fill from last saved day
- 🔒 Monthly submit + lock with edit request workflow
- 👥 Team view (admin)
- 📊 Reports with Excel/CSV export
- ⚙️ Admin panel — manage members, projects, activity codes
- 📤 Bulk member upload (CSV/Excel)
- 📤 Historical timesheet data import
- 📧 Friday reminder emails
- 🎉 Auto-fills public holidays
- 🚫 Weekend protection (cannot edit Sat/Sun)

## Tech stack

- **Frontend + Backend:** Python + Streamlit
- **Database:** Supabase (PostgreSQL)
- **Hosting:** Streamlit Community Cloud (free)

## Deployment to Streamlit Cloud

### Prerequisites
- GitHub account
- Streamlit Cloud account ([share.streamlit.io](https://share.streamlit.io))
- Supabase project (already set up)

### Steps

1. **Create new GitHub repo** named `eet-timesheet-app`

2. **Upload all files** from this folder to the repo:
   - `app.py`
   - `db.py`
   - `constants.py`
   - `pages_app/` folder (all files)
   - `requirements.txt`
   - `.streamlit/config.toml`

3. **Go to Streamlit Cloud** → Sign in with GitHub

4. **Click "New app"**:
   - Repository: `your-username/eet-timesheet-app`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: choose `gcc-eet-timesheet` (or similar)

5. **Click "Advanced settings"** → **Secrets**:
   ```
   [supabase]
   url = "https://qienqtmfiytsuvuoovpw.supabase.co"
   key = "sb_publishable_yAvlRDj_-FydTvMLi5SNcQ_Uk1nOGUL"
   ```

6. **Click "Deploy"** — takes 2-3 minutes

7. **App URL** will be: `https://gcc-eet-timesheet.streamlit.app`

### Database setup (one-time)

Already done. Tables `ts_members`, `ts_projects`, `ts_entries`, `ts_submissions`, `ts_edit_requests` already exist in Supabase.

For custom activity codes (new feature), run this SQL in Supabase SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS ts_custom_acts (
  id BIGINT PRIMARY KEY,
  code TEXT NOT NULL,
  description TEXT,
  discipline TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE ts_custom_acts DISABLE ROW LEVEL SECURITY;
```

## Local development

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

App opens at http://localhost:8501

## File structure

```
eet-timesheet-app/
├── app.py                      # Main entry point
├── db.py                        # Supabase database operations
├── constants.py                 # Holidays, departments, disciplines, activity codes
├── pages_app/
│   ├── __init__.py
│   ├── timesheet_page.py        # My Timesheet (weekly grid)
│   ├── team_view.py             # Team View (admin)
│   ├── reports_page.py          # Reports + Excel export
│   ├── admin_page.py            # Admin panel
│   └── upload_page.py           # Bulk upload tools
├── requirements.txt
├── .streamlit/
│   ├── config.toml              # Streamlit theme + settings
│   └── secrets.toml.example     # Template for Supabase credentials
└── README.md
```
