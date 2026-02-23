import requests
import subprocess
import sys
import os

from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE", "https://app.southwind.ai/api")
API_KEY = os.getenv("API_KEY", "")


def get_project_root():
    """Get the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_all_data_sources():
    """Fetch all data sources from the API."""
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    response = requests.get(
        f"{API_BASE}/v1/data-sources/",
        headers=headers,
    )
    
    if response.status_code != 200:
        error_msg = f"Failed to fetch data sources (status {response.status_code}): {response.text}"
        print(error_msg)
        raise Exception(error_msg)
    
    return response.json()


def delete_data_sources(data_source_ids):
    """Delete data sources by IDs."""
    if not data_source_ids:
        print("No data sources to delete")
        return
    
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    response = requests.delete(
        f"{API_BASE}/v1/data-sources/",
        headers=headers,
        json={"ids": data_source_ids},
    )
    
    if response.status_code != 200:
        error_msg = f"Failed to delete data sources (status {response.status_code}): {response.text}"
        print(error_msg)
        raise Exception(error_msg)
    
    result = response.json()
    print(f"Deleted {result['deleted_count']} data sources")
    if result.get('failed_sources'):
        print(f"Failed to delete: {result['failed_sources']}")
    
    return result


def cleanup_datasets_from_repo():
    """Remove all CSV files from the datasets folder in git."""
    project_root = get_project_root()
    datasets_path = os.path.join(project_root, "datasets")
    
    # Check if datasets folder exists
    if not os.path.exists(datasets_path):
        print("No datasets folder found locally")
        return
    
    # List all CSV files in datasets folder
    csv_files = [f for f in os.listdir(datasets_path) if f.endswith('.csv')]
    
    if not csv_files:
        print("No CSV files to clean up in datasets folder")
        return
    
    print(f"Found {len(csv_files)} CSV files to clean up")
    
    try:
        # Remove all CSV files from git
        for csv_file in csv_files:
            file_path = f"datasets/{csv_file}"
            print(f"Removing {file_path}...")
            subprocess.run(["git", "rm", "-f", file_path], cwd=project_root, check=True)
        
        # Commit the cleanup
        subprocess.run(
            ["git", "commit", "-m", "chore: weekly cleanup of datasets folder"],
            cwd=project_root,
            check=True
        )
        
        # Push to remote
        subprocess.run(["git", "push"], cwd=project_root, check=True)
        
        print(f"Successfully cleaned up {len(csv_files)} files from repository")
    except subprocess.CalledProcessError as e:
        print(f"Git cleanup failed: {e}")
        raise


def main():
    """Main cleanup function."""
    print("=" * 60)
    print("Starting weekly cleanup...")
    print("=" * 60)
    
    print("\n[1/2] Cleaning up data sources via API...")
    try:
        data_sources_response = get_all_data_sources()
        data_origins = data_sources_response.get("data_origins", [])
        
        # Collect all data source IDs from all data origins
        all_data_source_ids = []
        for origin in data_origins:
            for ds in origin.get("data_sources", []):
                all_data_source_ids.append(ds["id"])
        
        print(f"Found {len(all_data_source_ids)} data sources to delete")
        
        if all_data_source_ids:
            delete_data_sources(all_data_source_ids)
        else:
            print("No data sources found to delete")
    except Exception as e:
        print(f"Error cleaning up data sources: {e}")
        sys.exit(1)
    
    print("\n[2/2] Cleaning up datasets from repository...")
    try:
        cleanup_datasets_from_repo()
    except Exception as e:
        print(f"Error cleaning up datasets: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Weekly cleanup completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

