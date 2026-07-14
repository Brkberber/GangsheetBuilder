# ============================================================
# config.py — Central configuration for GangsheetBuilder
# ============================================================

# Print settings
DPI = 300
PADDING_INCH = 0.2   # border on every side of each design (inches)

# Default sheet dimensions (inches)
DEFAULT_SHEET_WIDTH_INCH = 22
DEFAULT_MAX_SHEET_HEIGHT_INCH = 250

# File cleanup
MAX_FILE_AGE_SECONDS = 30 * 60   # 30 minutes
CLEANUP_INTERVAL_SECONDS = 10 * 60  # run every 10 minutes

# Flask folder names
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'