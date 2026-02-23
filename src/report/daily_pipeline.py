import requests
import subprocess
import datetime
import sys
import os
import time

from dotenv import load_dotenv
from query import fetch_data

load_dotenv()

API_BASE = "http://localhost:8000/api"
API_KEY = os.getenv("API_KEY", "")

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/southwind-ai/studio-regione-lombardia/refs/heads/main/"


def wait_for_file_availability(file_url, max_attempts=20, delay=5):
    """Wait for a file to be accessible via URL before proceeding."""
    print(f"Waiting for file to be available at: {file_url}")
    for attempt in range(1, max_attempts + 1):
        try:
            # Use GET with stream=True (doesn't download full file, just checks availability)
            response = requests.get(file_url, timeout=10, stream=True)
            if response.status_code == 200:
                print(f"✓ File is now accessible (attempt {attempt})")
                response.close()
                return True
            else:
                print(f"Attempt {attempt}/{max_attempts}: Status {response.status_code}, waiting {delay}s...")
        except requests.RequestException as e:
            print(f"Attempt {attempt}/{max_attempts}: {type(e).__name__}, waiting {delay}s...")
        
        if attempt < max_attempts:
            time.sleep(delay)
    
    raise Exception(f"File not accessible after {max_attempts * delay}s (GitHub CDN propagation timeout)")

def get_project_root():
    """Get the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def push_to_github(file_path):
    """Push a file to GitHub. file_path should be relative to repo root."""
    project_root = get_project_root()
    try:
        # Use -f flag to force-add files from ignored directories
        subprocess.run(["git", "add", "-f", file_path], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-m", f"Daily dataset {file_path}"], cwd=project_root, check=True)
        subprocess.run(["git", "push"], cwd=project_root, check=True)
    except subprocess.CalledProcessError:
        print("Git push failed")
        sys.exit(1)


def delete_file_from_repo(file_path):
    """Delete a file from the repo and push the deletion."""
    project_root = get_project_root()
    try:
        print(f"Deleting {file_path} from repository due to error...")
        subprocess.run(["git", "rm", "-f", file_path], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-m", f"Remove {file_path} due to pipeline error"], cwd=project_root, check=True)
        subprocess.run(["git", "push"], cwd=project_root, check=True)
        print(f"Successfully removed {file_path} from repository")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to delete file from repo: {e}")


def create_data_source(file_url):
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    response = requests.post(
        f"{API_BASE}/v1/data-sources/file/",
        headers=headers,
        json={
            "files": [
                {
                    "name": file_url.split("/")[-1],
                    "url": file_url,
                }
            ]
        },
    )

    if response.status_code != 201:
        error_msg = f"Data source creation failed (status {response.status_code}): {response.text}"
        print(error_msg)
        raise Exception(error_msg)

    response_data = response.json()
    print(f"Data source response: {response_data}")
    
    # Check if the expected structure exists
    if "created_data_origins" not in response_data or not response_data["created_data_origins"]:
        error_msg = f"Unexpected API response structure: {response_data}"
        print(error_msg)
        raise Exception(error_msg)
    
    data_origin = response_data["created_data_origins"][0]
    if "data_sources" not in data_origin or not data_origin["data_sources"]:
        error_msg = f"No data sources in response: {response_data}"
        print(error_msg)
        raise Exception(error_msg)
    
    # Return the data source ID
    return data_origin["data_sources"][0]["id"]


def create_report(data_source_id):
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    response = requests.post(
        f"{API_BASE}/v1/reports/",
        headers=headers,
        json={
            "data_sources_ids": [data_source_id],
            "params": {
                "language": "italian",
                "currency": "EUR",
                "prompt": "Analizza i dati dei pagamenti effettuati tramite il portale pagamentinlombardia.servizirl.it per il sistema pagoPA nella data odierna.",
                "dataset_info": "",
                "data_provenance": False,
            },
            "improve_prompt": False,
        },
    )

    if response.status_code != 201:
        error_msg = f"Report creation failed: {response.text}"
        print(error_msg)
        raise Exception(error_msg)

    return response.json()["id"]


def main():
    today = datetime.date.today().isoformat()
    ## Date must be in format YYYY-MM-DD
    today = today.split("-")
    today = today[0] + "-" + today[1] + "-" + today[2]

    print("Fetching data...")
    csv_file = fetch_data(today)

    print("Pushing to GitHub...")
    push_to_github(csv_file)

    file_url = GITHUB_RAW_BASE + csv_file
    
    # Wait for GitHub to make the file accessible via raw URL
    if not wait_for_file_availability(file_url):
        print("Warning: Proceeding anyway, but file may not be accessible yet")

    try:
        print("Creating data source...")
        data_source_id = create_data_source(file_url)

        print("Creating report...")
        report_id = create_report(data_source_id)

        print("Report queued with ID:", report_id)
    except Exception as e:
        print(f"Error occurred: {e}")
        delete_file_from_repo(csv_file)
        sys.exit(1)


if __name__ == "__main__":
    main()