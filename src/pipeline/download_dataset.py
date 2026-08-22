"""
src/pipeline/download_dataset.py
Downloads the Mesa Del Sol Microgrid Power Dataset from Kaggle to data/raw/.
"""
import os
import shutil
import glob
from pathlib import Path
import kagglehub

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"

def download_dataset():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Dataset Download] Downloading dataset via kagglehub...")
    download_path = kagglehub.dataset_download("yekenot/power-data-from-mesa-del-sol-microgrid")
    print(f"[Dataset Download] Downloaded to cache: {download_path}")

    # Copy CSV files to data/raw/
    csv_files = glob.glob(os.path.join(download_path, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in kagglehub cache directory: {download_path}")

    print(f"[Dataset Download] Copying {len(csv_files)} monthly CSV files to {RAW_DIR}...")
    for f in csv_files:
        dest_file = RAW_DIR / os.path.basename(f)
        shutil.copy2(f, dest_file)
        print(f"  -> Copied {dest_file.name}")

    print(f"[Dataset Download] Complete! Raw files ready in {RAW_DIR}")

if __name__ == "__main__":
    download_dataset()
