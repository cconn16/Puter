from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  
WORKBOOK_PATH = BASE_DIR / "workout.xlsx"  
BACKUP_DIR = BASE_DIR / "backups"

SHEET_LOG = "Historical Log"  
SHEET_PRS = "PRs"  
SHEET_PROGRAM = "Training Program"  
SHEET_ALIASES = "Aliases"

LOG_HEADERS = ["Date", "Time", "Exercise", "Sets", "Reps",  
               "Weight", "Unit", "Weight Type", "Notes"]  
PR_HEADERS = ["Exercise", "Sets", "Reps", "Weight", "Unit", "Date Set", "Previous PR"]  
PROGRAM_HEADERS = ["Day", "Order", "Exercise", "Sets", "Reps", "Prescription", "Notes"]  
ALIAS_HEADERS = ["Alias", "Canonical Exercise"]

DEFAULT_UNIT = "lb"

HOST = "0.0.0.0"  
PORT = 80 