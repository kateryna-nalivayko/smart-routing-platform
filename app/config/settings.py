from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"
GEOCODING_CACHE_PATH = DATA_DIR / "geocoding_cache.json"

EXCEL_FILE_PATH = DATA_DIR / "Routing_pilot_data_input_FINAL.xlsx"
