"""
src/pipeline/process_dataset.py
Processes raw monthly CSVs into memory-efficient, multi-resolution Parquet datasets.
Handles sensor dropout sentinels (-999999.0), missing data imputation, and accurate physics.
"""
import os
import glob
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

BATTERY_CAPACITY_KWH = 500.0  # 500 kWh simulated BESS capacity
DEFAULT_INITIAL_SOC = 60.0    # Baseline SOC percentage

def extract_and_sanitize(df: pd.DataFrame, candidates: list[str], 
                         min_valid: float, max_valid: float, default_val: float) -> pd.Series:
    """
    Extracts a column matching candidate names, strips sentinel error codes (-999999.0),
    and interpolates missing intervals.
    """
    series = None
    for c in candidates:
        if c in df.columns:
            series = pd.to_numeric(df[c], errors='coerce')
            break
    
    if series is None:
        return pd.Series(default_val, index=df.index, dtype=float)

    # Convert sensor dropout sentinel codes (e.g. -999999.0) and out-of-range values to NaN
    series = series.mask((series < min_valid) | (series > max_valid), np.nan)

    # Time-series interpolation for short dropouts (up to 1 minute / 6 steps)
    series = series.interpolate(method='linear', limit=12)
    # Forward-fill and backward-fill remaining gaps, with fallback default
    series = series.ffill().bfill().fillna(default_val)
    return series

def process_monthly_file(file_path: str, initial_soc: float = DEFAULT_INITIAL_SOC) -> tuple[pd.DataFrame, float]:
    """Process a single monthly CSV with accurate physics, sentinel filtering, and NaN handling."""
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()

    # Parse timestamps and sort
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.dropna(subset=['Timestamp']).sort_values('Timestamp').reset_index(drop=True)

    # Extract and sanitize columns with realistic physical bounds (sentinel code filtering)
    # 1. Solar PV (0 to 100 kW)
    pv_power = extract_and_sanitize(df, ['PVPCS_Active_Power', 'PVPCS Active Power'], 
                                    min_valid=-10.0, max_valid=500.0, default_val=0.0).clip(lower=0.0)
    
    # 2. Total Grid Load (0 to 1000 kW)
    ge_power = extract_and_sanitize(df, ['GE_Active_Power', 'GE Active Power'], 
                                    min_valid=-10.0, max_valid=2000.0, default_val=0.0).clip(lower=0.0)
    
    # 3. Battery Active Power (-500 kW charge to +500 kW discharge)
    battery_power = extract_and_sanitize(df, ['Battery_Active_Power', 'Battery Active Power'], 
                                         min_valid=-500.0, max_valid=500.0, default_val=0.0)
    
    # 4. Fuel Cell (0 to 200 kW)
    fc_power = extract_and_sanitize(df, ['FC_Active_Power', 'FC Active Power'], 
                                    min_valid=-10.0, max_valid=500.0, default_val=0.0).clip(lower=0.0)
    
    # 5. Voltage (300V to 600V for 480V 3-phase microgrid bus)
    voltage = extract_and_sanitize(df, ['MG-LV-MSB_AC_Voltage', 'MG-LV-MSB AC Voltage', 'Receiving_Point_AC_Voltage'], 
                                    min_valid=300.0, max_valid=600.0, default_val=480.0)
    
    # 6. Frequency (55.0 to 65.0 Hz for 60Hz microgrid)
    frequency = extract_and_sanitize(df, ['MG-LV-MSB_Frequency', 'MG-LV-MSB Frequency', 'Island_mode_MCCB_Frequency'], 
                                      min_valid=55.0, max_valid=65.0, default_val=60.0)
    
    # 7. Chilled water temperature (0 to 50 C)
    inlet_temp = extract_and_sanitize(df, ['Inlet_Temperature_of_Chilled_Water', 'Inlet Temperature of Chilled Water'], 
                                      min_valid=0.0, max_valid=60.0, default_val=20.0)

    # Unit conversions (kW -> MW)
    processed = pd.DataFrame()
    processed['timestamp'] = df['Timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    processed['datetime'] = df['Timestamp']
    processed['solar_mw'] = pv_power / 1000.0
    processed['wind_mw'] = 0.0  # Compatibility field required by grid state server
    processed['load_mw'] = ge_power / 1000.0
    processed['fuel_cell_mw'] = fc_power / 1000.0
    processed['battery_power_kw'] = battery_power
    processed['voltage_v'] = voltage
    processed['frequency_hz'] = frequency
    processed['chilled_water_temp_c'] = inlet_temp

    # Battery State of Charge (SOC) Integration
    # Delta time in hours (10 seconds / 3600 seconds)
    dt_hours = 10.0 / 3600.0
    # Positive battery_power_kw = discharging (SOC decreases)
    energy_delta_kwh = -processed['battery_power_kw'] * dt_hours
    soc_series = [initial_soc]
    
    current_soc = initial_soc
    for delta_e in energy_delta_kwh:
        current_soc = max(10.0, min(95.0, current_soc + (delta_e / BATTERY_CAPACITY_KWH * 100.0)))
        soc_series.append(current_soc)
    
    processed['battery_soc'] = soc_series[:-1]
    final_soc = soc_series[-1]

    return processed, final_soc

def run_pipeline():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(glob.glob(str(RAW_DIR / "*.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {RAW_DIR}. Run download_dataset.py first!")

    print(f"[Pipeline] Found {len(csv_files)} monthly files. Ingesting incrementally...")
    monthly_dfs = []
    current_soc = DEFAULT_INITIAL_SOC

    for file_path in csv_files:
        print(f"  -> Ingesting {os.path.basename(file_path)}...")
        df_month, current_soc = process_monthly_file(file_path, initial_soc=current_soc)
        monthly_dfs.append(df_month)

    print("[Pipeline] Concatenating full time-series...")
    full_df = pd.concat(monthly_dfs, ignore_index=True)
    full_df = full_df.sort_values('datetime').reset_index(drop=True)

    # 1. Export Full 10-Second Parquet
    out_10s = PROCESSED_DIR / "mesa_del_sol_10s.parquet"
    export_df_10s = full_df.drop(columns=['datetime'])
    export_df_10s.to_parquet(out_10s, compression='snappy', index=False)
    print(f"[Pipeline] Saved 10-second dataset to {out_10s} ({out_10s.stat().st_size / 1e6:.2f} MB, {len(export_df_10s):,} rows)")

    # 2. Export 1-Minute Downsampled Parquet
    print("[Pipeline] Computing 1-minute aggregation...")
    full_df.set_index('datetime', inplace=True)
    df_1m = full_df.resample('1min').agg({
        'solar_mw': 'mean',
        'wind_mw': 'mean',
        'load_mw': 'mean',
        'fuel_cell_mw': 'mean',
        'battery_power_kw': 'mean',
        'battery_soc': 'last',
        'voltage_v': 'mean',
        'frequency_hz': 'mean',
        'chilled_water_temp_c': 'mean'
    }).dropna().reset_index()
    df_1m['timestamp'] = df_1m['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    df_1m = df_1m.drop(columns=['datetime'])
    out_1m = PROCESSED_DIR / "mesa_del_sol_1m.parquet"
    df_1m.to_parquet(out_1m, compression='snappy', index=False)
    print(f"[Pipeline] Saved 1-minute dataset to {out_1m} ({out_1m.stat().st_size / 1e6:.2f} MB, {len(df_1m):,} rows)")

    # 3. Export 5-Minute Downsampled Parquet
    print("[Pipeline] Computing 5-minute aggregation...")
    df_5m = df_1m.copy()
    df_5m['datetime'] = pd.to_datetime(df_5m['timestamp'])
    df_5m.set_index('datetime', inplace=True)
    df_5m = df_5m.resample('5min').agg({
        'solar_mw': 'mean',
        'wind_mw': 'mean',
        'load_mw': 'mean',
        'fuel_cell_mw': 'mean',
        'battery_power_kw': 'mean',
        'battery_soc': 'last',
        'voltage_v': 'mean',
        'frequency_hz': 'mean',
        'chilled_water_temp_c': 'mean'
    }).dropna().reset_index()
    df_5m['timestamp'] = df_5m['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    df_5m = df_5m.drop(columns=['datetime'])
    out_5m = PROCESSED_DIR / "mesa_del_sol_5m.parquet"
    df_5m.to_parquet(out_5m, compression='snappy', index=False)
    print(f"[Pipeline] Saved 5-minute dataset to {out_5m} ({out_5m.stat().st_size / 1e6:.2f} MB, {len(df_5m):,} rows)")

    print("[Pipeline] Pipeline execution successfully completed!")

if __name__ == "__main__":
    run_pipeline()
