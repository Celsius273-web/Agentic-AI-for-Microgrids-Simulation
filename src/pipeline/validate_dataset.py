"""
src/pipeline/validate_dataset.py
Verifies dataset integrity, schema conformity, physical limits, and zero nulls.
Uses explicit exception raising rather than asserts to support optimized Python execution (-O).
"""
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

def validate_parquet(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")
    
    df = pd.read_parquet(file_path)
    print(f"[Validate] Validating {file_path.name} ({len(df):,} records)...")

    # 1. Required schema check (including chilled water temperature)
    required_cols = [
        "timestamp", "solar_mw", "wind_mw", "load_mw", 
        "fuel_cell_mw", "battery_power_kw", "battery_soc", 
        "voltage_v", "frequency_hz", "chilled_water_temp_c"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required column(s) in {file_path.name}: {missing}")

    # 2. Null checks
    null_counts = int(df[required_cols].isnull().sum().sum())
    if null_counts != 0:
        raise ValueError(f"Found {null_counts} null values in {file_path.name}!")

    # 3. Physical range checks (aligned with processing bounds)
    if not (df["solar_mw"] >= 0.0).all():
        raise ValueError(f"Negative solar generation detected in {file_path.name}")
    if not (df["load_mw"] >= 0.0).all():
        raise ValueError(f"Negative load consumption detected in {file_path.name}")
    if not ((df["battery_soc"] >= 10.0) & (df["battery_soc"] <= 95.0)).all():
        raise ValueError(f"Battery SOC out of bounds [10.0, 95.0] in {file_path.name}")
    if not ((df["frequency_hz"] >= 55.0) & (df["frequency_hz"] <= 65.0)).all():
        raise ValueError(f"Frequency out of realistic microgrid bounds [55.0, 65.0] in {file_path.name}")
    if not ((df["voltage_v"] >= 300.0) & (df["voltage_v"] <= 600.0)).all():
        raise ValueError(f"Voltage out of realistic bounds [300.0, 600.0] in {file_path.name}")
    if not ((df["chilled_water_temp_c"] >= 0.0) & (df["chilled_water_temp_c"] <= 60.0)).all():
        raise ValueError(f"Chilled water temperature out of realistic bounds [0.0, 60.0] in {file_path.name}")
    if not (df["wind_mw"] == 0.0).all():
        raise ValueError(f"wind_mw must be initialized to 0.0 in {file_path.name}")

    print(f"  -> [PASS] Schema, nulls, and physical bounds verified for {file_path.name}")

if __name__ == "__main__":
    for filename in ["mesa_del_sol_10s.parquet", "mesa_del_sol_1m.parquet", "mesa_del_sol_5m.parquet"]:
        validate_parquet(PROCESSED_DIR / filename)
    print("[Validate] All dataset files successfully validated!")
