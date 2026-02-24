import csv
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN", "")

ENDPOINT = os.getenv("ENDPOINT", "https://www.dati.lombardia.it/resource/78vt-im2v.json")
LIMIT = 1000

MAX_RETRIES = 5
BACKOFF_FACTOR = 2  # waits 2, 4, 8, 16... seconds between retries


def _build_session():
    """Build a requests Session with automatic retry on transient errors."""
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def parse_date(date_str):
    """Parse a date string in YYYY-MM-DD format and return the Socrata timestamp."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"Error: invalid date '{date_str}'. Use YYYY-MM-DD format (e.g. 2026-02-09)")
        sys.exit(1)
    return dt.strftime("%Y-%m-%dT00:00:00.000"), dt.strftime("%Y-%m-%d")
_drop = os.getenv("DROP_COLUMNS", "ora,giorno_della_settimana,modello,ultima_modifica_data")
DROP_COLUMNS = {c.strip() for c in _drop.split(",") if c.strip()}

_rename = os.getenv("RENAME_COLUMNS", "")  # format: old1:new1,old2:new2
RENAME_COLUMNS = {}
for pair in _rename.split(","):
    if ":" in pair:
        old, new = pair.split(":", 1)
        RENAME_COLUMNS[old.strip()] = new.strip()


def fetch_all_records(date_ts):
    headers = {}
    if APP_TOKEN:
        headers["X-App-Token"] = APP_TOKEN
    params_base = {
        "$where": f"pag_data='{date_ts}'",
        "$order": ":id",
        "$limit": LIMIT,
    }

    session = _build_session()
    all_records = []
    offset = 0

    while True:
        params = {**params_base, "$offset": offset}
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = session.get(ENDPOINT, headers=headers, params=params, timeout=60)
                resp.raise_for_status()
                break
            except requests.exceptions.ConnectionError as e:
                if attempt == MAX_RETRIES:
                    raise
                wait = BACKOFF_FACTOR ** attempt
                print(f"Connection error at offset {offset} (attempt {attempt}/{MAX_RETRIES}), retrying in {wait}s: {e}")
                time.sleep(wait)
        batch = resp.json()
        if not batch:
            break
        all_records.extend(batch)
        print(f"Fetched {len(all_records)} records so far...")
        if len(batch) < LIMIT:
            break
        offset += LIMIT

    return all_records


def fetch_data(date:str|None=None):
    date_input = os.getenv("DATE", "")
    if date is not None:
        date_input = date
    if not date_input:
        print("Usage: python query.py YYYY-MM-DD")
        print("   or: set DATE=YYYY-MM-DD in .env")
        sys.exit(1)

    date_ts, date_short = parse_date(date_input)
    output_template = os.getenv("OUTPUT_FILE", "pagamenti_{date}.csv")
    output_filename = output_template.replace("{date}", date_short)
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    datasets_dir = os.path.join(project_root, "datasets")
    os.makedirs(datasets_dir, exist_ok=True)
    output_file = os.path.join(datasets_dir, output_filename)
    # Relative path for git operations
    output_file_relative = os.path.join("datasets", output_filename)

    records = fetch_all_records(date_ts)
    for r in records:
        ora = r.get("ora", "0")
        r["pag_data"] = f"{date_short}T{int(ora):02d}:00:00.000"
        for col in DROP_COLUMNS:
            r.pop(col, None)
        for old, new in RENAME_COLUMNS.items():
            if old in r:
                r[new] = r.pop(old)
    fieldnames = list(records[0].keys()) if records else []
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Saved {len(records)} records to {output_file}")
    return output_file_relative