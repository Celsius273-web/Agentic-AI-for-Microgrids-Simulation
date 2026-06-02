# Microgrid Past Decisions and Lessons Learned

## Decision Log

### 2024-03-15: Battery Sizing Decision
**Decision**: Installed 500 kWh lithium-ion battery system instead of 750 kWh
**Rationale**: Cost-benefit analysis showed diminishing returns above 500 kWh
**Outcome**: Sufficient for daily peak shaving but limited backup duration
**Lesson**: Should have considered extreme weather events lasting >8 hours
**Recommendation**: Plan for 750 kWh in next expansion phase

### 2024-05-22: Solar Curtailment Strategy
**Decision**: Implemented curtailment when battery SOC >85% and load <50% capacity
**Rationale**: Prevent battery overcharging and extend system life
**Outcome**: Lost 120 kWh of renewable generation in first month
**Lesson**: Curtailment thresholds were too conservative
**Recommendation**: Raised threshold to 95% SOC, added export capability

### 2024-07-10: Load Shedding Priority
**Decision**: HVAC systems have higher priority than EV charging
**Rationale**: Occupant comfort affects productivity more than charging convenience
**Outcome**: Summer peak demand successfully managed without complaints
**Lesson**: Clear communication with building occupants essential
**Recommendation**: Implement automated notification system for load events

### 2024-09-05: Grid Connection Mode
**Decision**: Remain grid-connected during normal operations
**Rationale**: Access to grid services and backup power reduces system stress
**Outcome**: 99.8% system availability, reduced battery cycling
**Lesson**: Islanding only necessary during grid outages or power quality issues
**Recommendation**: Develop smart islanding triggers based on grid conditions

### 2024-11-12: Demand Response Participation  
**Decision**: Enrolled in utility demand response program
**Rationale**: Additional revenue stream of $15,000 annually
**Outcome**: Successfully curtailed load during 8 events, earned full payments
**Lesson**: Automated response systems essential for reliable participation
**Recommendation**: Expand participation to frequency regulation services

## Technical Lessons Learned

### Battery Management
- Lithium-ion batteries perform better with shallow cycling (20-80% SOC)
- Temperature management critical - 5°C increase reduces life by 20%
- Calendar aging significant factor - even unused batteries degrade 2-3% annually
- State estimation accuracy improves with regular full charge/discharge cycles

### Renewable Integration Challenges
- Solar PV output can drop 80% in 30 seconds due to cloud cover
- Wind generation patterns change seasonally - summer lulls common
- Inverter ramping rates limit response to generation/load mismatches
- Power quality issues more common with high renewable penetration

### Communication and Control
- Ethernet-based communication more reliable than wireless for critical systems
- SCADA system response time must be <500ms for effective control
- Cybersecurity measures cannot interfere with real-time operations
- Manual override capabilities essential for emergency situations

### Economic Performance
- Demand charge reduction most significant cost savings (60% of benefits)
- Time-of-use arbitrage limited by battery efficiency losses (8-12%)
- Grid service revenues highly dependent on market rules and participation
- Maintenance costs higher than predicted - budget 3% of capital annually

## Operational Insights

### Weather Dependencies
- Heating degree days strongly correlate with winter load profiles
- Solar generation reduces 15-25% during wildfire season due to smoke
- Wind turbine performance degrades in icing conditions
- Extreme weather events stress all system components simultaneously

### Human Factors
- Training requirements higher than expected - quarterly refreshers needed
- User interface design critical for operator decision-making
- Alarm fatigue real problem - limit to truly actionable alerts only
- Stakeholder communication plan essential for system acceptance

### Regulatory Compliance
- Interconnection standards evolve - stay engaged with working groups
- Environmental permits require detailed emissions monitoring
- Fire department coordination essential for emergency response
- Insurance requirements include specific safety system testing protocols