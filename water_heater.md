# Tuya Water Heater Control System - Mission Document

## Project Overview
A Flask-based web application hosted on Azure Web App (Python 3.12) that enables users to control water heaters through Tuya IoT devices via mobile browsers and automated scheduling.

## Core Requirements

### User Experience
1. **Authentication**
   - Single password authentication (no user management)
   - Persistent cookie with 2+ month expiration
   - Password stored as `PASSWORD` environment variable

2. **Main Control Page**
   - Single button interface showing desired heater state
   - Green button = OFF state, Red button = ON state
   - Click toggles state instantly (no confirmation dialogs)
   - When ON: Display accumulated ACTUAL ON time (verified device state only)
   - **Manual Override Logic**:
     - Manual button clicks override current state **temporarily only**
     - Override **automatically expires** when scheduled periods start or end
     - Schedule **always takes control** at transition times (18:00 start, 20:00 end)
     - Within same period: manual override prevents automatic changes for 30 minutes
     - **Key principle**: Schedule boundaries clear all manual overrides
   - **Time Counter Requirements**:
     - Only counts time when device is actually verified ON
     - Does NOT count time based on desired state if device is physically OFF
     - **Resets to 0:00 on each OFF→ON transition** (session-based tracking)
     - Shows actual runtime for current session only
     - Updates reflect real device state, not user intentions

3. **Configuration Page**
   - Define time ranges in Israel timezone (HH:MM to HH:MM format)
   - Multiple time ranges supported
   - Simple form-based interface

### Technical Architecture

#### IoT Integration (Based on sample2.py)
- **Platform**: Tuya Cloud API with HMAC-SHA256 authentication
- **Device Control**: Smart switch/relay with boolean commands
- **Environment Variables**:
  - `TUYA_ACCESS_ID`: Client ID for API access
  - `TUYA_ACCESS_SECRET`: Secret for HMAC signing
  - `TUYA_DEVICE_ID`: Target device identifier
  - `TUYA_REGION_ENDPOINT`: Regional API endpoint

#### State Management & Persistence
- **Storage**: Azure Table Storage (free tier) for volatility-resistant persistence
- **State Tracking**:
  - Desired state (ON/OFF) - what the user wants
  - Actual device state (ON/OFF) - verified real device state  
  - Scheduled time ranges
  - Current session accumulated ON time (resets on OFF→ON transitions)
  - Last successful command timestamp
  - Last device state verification timestamp
- **Time Tracking Requirements**:
  - Time accumulation based solely on verified actual device state
  - No speculation or estimation based on desired state
  - **Session-based tracking**: Counter resets to zero on each OFF→ON transition
  - Shows runtime for current session only, not cumulative across sessions

#### Background Processing (Dual Cron Strategy)

**CRITICAL**: Azure Web App Free Tier limits CPU to 1 hour/day total

**High-Frequency Job (1 minute intervals)**:
- **Purpose**: Enforce desired state against external interference (continuous state enforcement)
- **Logic**: 
  1. Always verify actual device state vs desired state
  2. If mismatch detected: Execute command to enforce desired state
  3. Re-verify device state after command execution
  4. Update accumulated ON time based on ACTUAL device state only
- **CPU Optimization**: Early exit only if actual state already matches desired state
- **Critical Requirement**: Must enforce state regardless of manual overrides, external switches, or physical device interference

**Low-Frequency Job (5 minute intervals)**:
- **Purpose**: Handle scheduled time ranges (less time-sensitive)
- **Logic**:
  1. Check current Israel time against configured ranges
  2. Set desired state based on schedule (if no manual override)
  3. Minimal state changes to trigger high-frequency job
- **CPU Optimization**: Only runs if scheduled state differs from current

#### Error Handling Strategy
- **Eventual Consistency Model**: Continuous retry for desired state enforcement
- **Retry Intervals**: ~6 second delays between attempts for individual commands
- **State Enforcement**: Every 30 seconds verification with immediate correction
- **No User Error Display**: Silent failure handling
- **Flaky IoT Assumption**: Built-in resilience for network/device issues
- **External Interference Handling**: System must override manual switches, power cycles, or any external state changes

### Application Structure

#### Flask Application Components
1. **Main Module** (`app.py`)
   - Flask app initialization
   - Route definitions
   - Session management

2. **Tuya Integration Module** (`tuya_client.py`)
   - Abstracted version of sample2.py functionality
   - Token management
   - Device command execution
   - Status verification

3. **State Manager Module** (`state_manager.py`)
   - Azure Table Storage interface
   - State persistence/retrieval
   - Time tracking logic

4. **Background Worker** (`scheduler.py`)
   - Cron job implementation
   - Israel timezone handling
   - Continuous state enforcement logic

5. **Templates**
   - `login.html`: Authentication page
   - `control.html`: Main heater control interface
   - `config.html`: Time range configuration

### Data Models

#### State Storage (Azure Table Storage)
```
WaterHeaterState:
- PartitionKey: "config"
- RowKey: "current"
- desired_state: bool
- manual_override: bool
- current_session_start: datetime (when turned ON)
- accumulated_seconds: int (current session only, resets on OFF→ON)
- last_successful_command: datetime

TimeRange:
- PartitionKey: "schedule" 
- RowKey: "{index}"
- start_time: "HH:MM"
- end_time: "HH:MM"
- enabled: bool
```

### CPU Optimization Strategy (Free Tier Constraint)

**Daily CPU Budget**: Maximum 1 hour (3600 seconds) total execution time

**Critical Optimizations**:
1. **Conditional Execution**:
   - Early exit patterns in cron jobs
   - Only execute expensive operations when state change required
   - Cache last known states to avoid unnecessary checks

2. **Efficient State Management**:
   - Single Azure Table Storage query per cron cycle
   - In-memory state caching between operations
   - Connection pooling for HTTP requests

3. **Smart Scheduling**:
   - High-frequency job: Only runs if manual override active
   - Low-frequency job: Only runs if within scheduled time windows
   - Sleep/idle time doesn't consume CPU quota

4. **Minimized Tuya API Calls**:
   - Avoid redundant status checks
   - Batch operations where possible  
   - Use connection keep-alive for HTTP efficiency

**Estimated CPU Usage**:
- User interaction: ~2-3 seconds per day
- High-freq cron (when active): ~5-10 seconds per hour ON time
- Low-freq cron: ~1-2 seconds per day
- **Total**: Well under 1-hour daily limit with smart execution

### Security Considerations
- Session management with secure cookies
- Environment variable protection for credentials
- No sensitive data logging
- Input validation for time ranges

### Deployment Requirements
- **Platform**: Azure Web App (Free Tier)
- **Runtime**: Python 3.12
- **Dependencies**: Flask, requests, azure-data-tables, pytz
- **Environment Variables**: PASSWORD, TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, TUYA_DEVICE_ID, TUYA_REGION_ENDPOINT, AZURE_STORAGE_CONNECTION_STRING

### Mobile Responsiveness
- Simple, touch-friendly button design
- Minimal UI optimized for phone browsers
- Fast loading with minimal JavaScript

### Implementation Phases
1. **Phase 1**: Basic Flask app with manual control
2. **Phase 2**: Azure Table Storage integration
3. **Phase 3**: Background scheduling system
4. **Phase 4**: Time range configuration UI
5. **Phase 5**: Mobile optimization and testing

### Critical Behavioral Requirements

#### State Enforcement (Primary Requirement)
The system must maintain control over the device state based on user intent and scheduling:

**Scenario 1**: User clicks button to turn device ON, then physically uses manual switch to turn device OFF
**Expected Behavior**: System detects the mismatch within 30 seconds and automatically turns device back ON

**Scenario 2**: Manual override vs. Scheduled periods
**Expected Behavior**: Manual override only lasts until the next scheduled period transition. When a scheduled period starts/ends, it automatically takes precedence over any previous manual override

**Implementation**: Continuous state verification and enforcement with time-aware manual override logic

### Manual Override Detailed Scenarios

#### Scenario A: Manual Override Before Schedule
```
Scheduled Period: 18:00-20:00
Timeline:
- 17:30: User clicks ON → Device ON (manual override)
- 18:00: Schedule starts → Device stays ON (schedule now takes control)
- 18:30: User clicks OFF → Device OFF (manual override within period)
- 20:00: Schedule ends → Device OFF (automatic schedule end)
```

#### Scenario B: Manual Override During Schedule  
```
Scheduled Period: 18:00-20:00
Timeline:
- 18:30: Device ON (following 18:00-20:00 schedule)
- 19:00: User clicks OFF → Device OFF (manual override)
- 19:15: Device stays OFF (manual override protection for 30 minutes)
- 20:00: Schedule ends → Device OFF (automatic schedule end)
```

#### Scenario C: Schedule Transitions Clear Override
```
Scheduled Period: 18:00-20:00
Timeline:
- 17:00: User clicks ON → Device ON (manual override)
- 18:00: Schedule starts → Device stays ON (schedule takes control, clearing override)
- 20:00: Schedule ends → Device OFF (automatic schedule end)
```

#### Accurate Time Tracking (Secondary Requirement)  
The displayed time counter must reflect actual device operation for the current session:

**Scenario 1**: User turns device ON via app, device gets physically turned OFF, user refreshes page
**Expected Behavior**: Time counter shows only the actual verified ON time, stops progressing when device is physically OFF

**Scenario 2**: User turns device OFF then ON again (new session)
**Expected Behavior**: Time counter resets to 0:00 and begins tracking the new session

**Implementation**: 
- Time accumulation based solely on verified device state, never on desired state
- Counter resets to zero on each OFF→ON transition for session-based tracking

### Success Criteria
- Family members can easily control water heater from mobile phones
- **State enforcement works against all external interference (manual switches, power cycles, etc.)**
- **Manual override is temporary: only lasts until next scheduled period transition**
- **Scheduled periods automatically take control when they start/end**
- **Manual override within scheduled periods protects against automatic changes for 30 minutes**
- **Time tracking accurately reflects actual device operation for current session (resets on OFF→ON)**
- Automated scheduling works reliably in Israel timezone
- System handles IoT connectivity issues gracefully
- Zero ongoing hosting costs beyond Azure free tier limits
- 99%+ uptime for the web interface (IoT eventual consistency acceptable)