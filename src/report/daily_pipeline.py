import requests
import subprocess
import datetime
import sys
import os

from query import fetch_data


API_BASE = "http://localhost:8000/api"

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/southwind-ai/lombardia-pagamenti/main/"

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
    response = requests.post(
        f"{API_BASE}/v1/data-sources/file/",
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
        error_msg = f"Data source creation failed: {response.text}"
        print(error_msg)
        raise Exception(error_msg)

    return response.json()["created_data_origins"][0]["id"]


def create_report(data_source_id):
    response = requests.post(
        f"{API_BASE}/v1/reports/",
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