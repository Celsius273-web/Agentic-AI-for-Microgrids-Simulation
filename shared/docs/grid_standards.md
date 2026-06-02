# Microgrid Operational Standards

## Voltage Standards
- Nominal voltage: 120V/240V AC single-phase, 208V/480V AC three-phase
- Acceptable voltage range: ±5% of nominal (114V-126V for 120V systems)
- Voltage regulation tolerance: ±2% under normal conditions
- Maximum voltage deviation during transients: ±10% for <1 second

## Frequency Standards
- Nominal frequency: 60 Hz ±0.1 Hz under normal conditions
- Acceptable frequency range: 59.5 Hz to 60.5 Hz
- Rate of change of frequency (RoCoF): Maximum 1 Hz/second during disturbances
- Frequency restoration time: Return to ±0.1 Hz within 10 minutes after disturbance

## Power Quality Requirements
- Total harmonic distortion (THD): <5% for voltage, <8% for current
- Power factor: Maintain between 0.95 leading and 0.95 lagging
- Flicker severity: <0.8 for short-term (Pst) and <0.6 for long-term (Plt)
- Voltage unbalance: <2% under normal conditions

## Battery Management
- State of charge (SOC) operating range: 20% to 90% for daily cycling
- Emergency reserve: Maintain minimum 10% SOC for critical loads
- Depth of discharge (DoD): Limit to 80% maximum for lithium-ion systems
- Charging rate: Maximum 0.5C continuous, 1C for 15 minutes peak
- Temperature management: Maintain 15°C to 35°C for optimal performance

## Load Management
- Critical loads: Hospital, emergency services, communication systems
- Controllable loads: HVAC, water heating, electric vehicle charging
- Load shedding priority: Non-critical loads first, then comfort loads
- Automatic load restoration: After 5 minutes of stable generation

## Safety Systems
- Ground fault protection: Trip within 0.1 seconds for faults >5mA
- Arc fault protection: Required for all branch circuits
- Isolation requirements: Ability to isolate from utility grid in <2 cycles
- Protective relay coordination: Time-current curves must not overlap