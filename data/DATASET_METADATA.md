# Mesa Del Sol Microgrid Power Dataset Metadata

## Overview
- **Source**: Kaggle (`yekenot/power-data-from-mesa-del-sol-microgrid`)
- **Original Research DOI**: [https://doi.org/10.5061/dryad.fqz612jzb](https://doi.org/10.5061/dryad.fqz612jzb)
- **Location**: Albuquerque, New Mexico (Mesa Del Sol Microgrid)
- **Time Range**: May 1, 2022 – July 31, 2023 (15 months)
- **Raw Sampling Resolution**: 10 seconds (~3.9 million timesteps)

## Processed Parquet Datasets
The ingestion pipeline (`src/pipeline/process_dataset.py`) converts the 15 monthly CSV files into optimized Apache Parquet tables under `data/processed/`:

1. **`mesa_del_sol_10s.parquet`**: Full 10-second resolution (3,887,242 rows, ~30.9 MB). Used for high-frequency control simulations and transient fault testing.
2. **`mesa_del_sol_1m.parquet`**: 1-minute resampled averages (647,874 rows, ~7.5 MB). Used for standard Control Agent operational loops.
3. **`mesa_del_sol_5m.parquet`**: 5-minute resampled averages (129,577 rows, ~2.2 MB). Used for Microgrid Agent strategic planning and high-level summaries.

## Target Schema & Feature Mapping

| Target Field | Type | Description | Source CSV Column | Unit Conversion / Imputation |
| :--- | :--- | :--- | :--- | :--- |
| `timestamp` | `string` (ISO UTC) | Timestamp in UTC format (`YYYY-MM-DDTHH:MM:SSZ`) | `Timestamp` | Datetime parse |
| `solar_mw` | `float64` | Photovoltaic generation in MW | `PVPCS_Active_Power` | `kW / 1000.0` (clipped >=0) |
| `wind_mw` | `float64` | Wind power generation in MW | *(None)* | Constant `0.0` (for compatibility) |
| `load_mw` | `float64` | Total microgrid load demand in MW | `GE_Active_Power` | `kW / 1000.0` (clipped >=0) |
| `fuel_cell_mw` | `float64` | Fuel cell generation in MW | `FC_Active_Power` | `kW / 1000.0` (clipped >=0) |
| `battery_power_kw` | `float64` | Battery power in kW (>0 discharge, <0 charge) | `Battery_Active_Power` | Direct kW |
| `battery_soc` | `float64` | Battery state of charge (10% - 95%) | *(Calculated)* | Bounded integration (delta SOC = -(P * delta t)/(C) * 100) |
| `voltage_v` | `float64` | Switchboard AC bus voltage (V) | `MG-LV-MSB_AC_Voltage` | Direct Volts (~480V nominal) |
| `frequency_hz` | `float64` | Microgrid electrical frequency (Hz) | `MG-LV-MSB_Frequency` | Direct Hertz (~60.0 Hz nominal) |
| `chilled_water_temp_c` | `float64` | Chilled water inlet temperature (°C) | `Inlet_Temperature_of_Chilled_Water` | Direct °C |

## Preprocessing & Data Cleaning
- **Dropout Code Filtering**: Raw sensor dropout / error codes (`-999999.0`) are converted to `NaN`.
- **Interpolation**: Short missing intervals ($\le 1\text{ minute}$) are linearly interpolated; extended gaps are forward/backward filled.
- **Physical Bounds**: Values outside realistic operating ranges are masked to `NaN` and then interpolated (short gaps) or forward/backward filled (extended gaps) to avoid corrupted grid states in simulation.
