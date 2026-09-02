"""
src/pipeline/validate_dataset.py
Verifies dataset integrity, schema conformity, physical limits, and zero nulls.
"""
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

def validate_parquet(file_path: Path):
    assert file_path.exists(), f"File does not exist: {file_path}"
    df = pd.read_parquet(file_path)
    print(f"[Validate] Validating {file_path.name} ({len(df):,} records)...")

    # 1. Required schema check
    required_cols = [
        "timestamp", "solar_mw", "wind_mw", "load_mw", 
        "fuel_cell_mw", "battery_power_kw", "battery_soc", 
        "voltage_v", "frequency_hz"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"

    # 2. Null checks
    null_counts = df[required_cols].isnull().sum().sum()
    assert null_counts == 0, f"Found {null_counts} null values in dataset!"

    # 3. Physical range checks
    assert (df['solar_mw'] >= 0.0).all(), "Negative solar generation detected"
    assert (df['load_mw'] >= 0.0).all(), "Negative load consumption detected"
    assert ((df['battery_soc'] >= 0.0) & (df['battery_soc'] <= 100.0)).all(), "Battery SOC out of bounds [0, 100]"
    assert ((df['frequency_hz'] >= 50.0) & (df['frequency_hz'] <= 70.0)).all(), "Frequency out of realistic grid bounds"
    assert ((df['voltage_v'] >= 80.0) & (df['voltage_v'] <= 600.0)).all(), "Voltage out of realistic bounds"
    assert (df['wind_mw'] == 0.0).all(), "wind_mw must be initialized to 0.0"

    print(f"  -> [PASS] Schema, nulls, and physical bounds verified for {file_path.name}")

if __name__ == "__main__":
    for filename in ["mesa_del_sol_10s.parquet", "mesa_del_sol_1m.parquet", "mesa_del_sol_5m.parquet"]:
        validate_parquet(PROCESSED_DIR / filename)
    print("[Validate] All dataset files successfully validated!")
