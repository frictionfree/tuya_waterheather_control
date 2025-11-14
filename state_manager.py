import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from azure.data.tables import TableServiceClient, TableEntity
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self):
        connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable required")
        
        self.table_service = TableServiceClient.from_connection_string(connection_string)
        self.table_name = "WaterHeaterState"
        
        # Ensure table exists
        self.table_client = self.table_service.get_table_client(self.table_name)
        self._ensure_table_exists()
        logger.info("Initialized StateManager for table %s", self.table_name)

    def _ensure_table_exists(self):
        """Ensure the Azure Table exists, create if it doesn't"""
        try:
            # Try a simple operation to check if table exists
            list(self.table_client.query_entities(query_filter="PartitionKey eq 'test'", results_per_page=1))
        except ResourceNotFoundError:
            # Table doesn't exist, create it
            try:
                self.table_service.create_table(self.table_name)
                logger.info("Created Azure Table %s", self.table_name)
            except Exception as e:
                logger.warning("Could not create table %s: %s", self.table_name, e)
                # Continue anyway, might be a permissions issue
        except Exception:
            # Table exists or other error, continue
            logger.debug("Azure Table %s already exists or could not be verified, continuing", self.table_name)

    def get_current_state(self) -> Dict[str, Any]:
        """Get current water heater state"""
        try:
            entity = self.table_client.get_entity(
                partition_key="config", 
                row_key="current"
            )
            
            state = {
                "desired_state": entity.get("desired_state", False),
                "actual_device_state": entity.get("actual_device_state", False),
                "manual_override": entity.get("manual_override", False),
                "current_session_start": entity.get("current_session_start"),
                "last_verified_on_time": entity.get("last_verified_on_time"),
                "accumulated_seconds": entity.get("accumulated_seconds", 0),
                "last_successful_command": entity.get("last_successful_command"),
                "last_state_change": entity.get("last_state_change"),
                "last_schedule_check": entity.get("last_schedule_check")
            }
            logger.info("Fetched current state: desired=%s actual=%s last_verified_on_time=%s manual_override=%s accum=%s",
                         state["desired_state"], state["actual_device_state"],
                         state["last_verified_on_time"], state["manual_override"], state["accumulated_seconds"])
            return state
        except ResourceNotFoundError:
            # Initialize default state
            default_state = {
                "PartitionKey": "config",
                "RowKey": "current",
                "desired_state": False,
                "actual_device_state": False,
                "manual_override": False,
                "current_session_start": None,
                "last_verified_on_time": None,
                "accumulated_seconds": 0,
                "last_successful_command": None,
                "last_state_change": None,
                "last_schedule_check": None
            }
            self.table_client.create_entity(default_state)
            logger.info("Created default state row in %s", self.table_name)
            return {k: v for k, v in default_state.items() if not k.startswith(('PartitionKey', 'RowKey'))}

    def set_desired_state(self, desired_state: bool, manual_override: bool = False) -> None:
        """Set desired water heater state"""
        current_state = self.get_current_state()
        now = datetime.utcnow()
        
        # Time accumulation resets on each OFF->ON transition for per-session tracking  
        # Actual time accumulation happens in update_actual_device_state() based on real device state
        accumulated_seconds = current_state["accumulated_seconds"]
        
        # Prepare update entity
        update_entity = {
            "PartitionKey": "config",
            "RowKey": "current", 
            "desired_state": desired_state,
            "manual_override": manual_override,
            "last_state_change": now.isoformat()
        }
        
        # Handle accumulated time and session start
        if desired_state and not current_state["desired_state"]:
            # Starting new ON session - reset accumulated time for new session
            update_entity["accumulated_seconds"] = 0  # Reset counter for new session
            update_entity["current_session_start"] = now.isoformat()
            update_entity["last_verified_on_time"] = None  # Reset verification time
        elif not desired_state:
            # Turning OFF - finalize accumulated time
            update_entity["accumulated_seconds"] = accumulated_seconds
            update_entity["current_session_start"] = None
            update_entity["last_verified_on_time"] = None
        else:
            # No state change, preserve values
            update_entity["accumulated_seconds"] = current_state["accumulated_seconds"]
            update_entity["current_session_start"] = current_state["current_session_start"]
            update_entity["last_verified_on_time"] = current_state.get("last_verified_on_time")
        
        # Preserve other fields
        update_entity.update({
            "last_successful_command": current_state["last_successful_command"],
            "last_schedule_check": current_state["last_schedule_check"]
        })
        
        self.table_client.upsert_entity(update_entity)
        logger.info("Desired state updated from %s to %s (manual_override=%s)",
                    current_state["desired_state"], desired_state, manual_override)

    def update_actual_device_state(self, actual_state: bool, timestamp: Optional[datetime] = None) -> None:
        """Update actual device state and accumulate real ON time"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        current_state = self.get_current_state()
        
        # Calculate accumulated time if device was actually ON
        accumulated_seconds = current_state["accumulated_seconds"]
        if current_state.get("actual_device_state") and current_state.get("last_verified_on_time"):
            # Device was ON, add the time it was actually on
            last_verified = datetime.fromisoformat(current_state["last_verified_on_time"])
            additional_seconds = int((timestamp - last_verified).total_seconds())
            if additional_seconds > 0:
                accumulated_seconds += additional_seconds
        
        # Set new verification time only if device is actually ON, clear if OFF
        last_verified_on_time = timestamp.isoformat() if actual_state else None
        
        update_entity = {
            "PartitionKey": "config",
            "RowKey": "current",
            "desired_state": current_state["desired_state"],
            "actual_device_state": actual_state,
            "manual_override": current_state["manual_override"],
            "current_session_start": current_state["current_session_start"],
            "last_verified_on_time": last_verified_on_time,
            "accumulated_seconds": accumulated_seconds,
            "last_successful_command": current_state["last_successful_command"],
            "last_state_change": current_state["last_state_change"],
            "last_schedule_check": current_state["last_schedule_check"]
        }
        
        self.table_client.upsert_entity(update_entity)
        if current_state.get("actual_device_state") != actual_state:
            logger.info("Actual device state updated from %s to %s (accumulated=%s)",
                        current_state.get("actual_device_state"), actual_state, accumulated_seconds)
        else:
            logger.debug("Actual device state re-verified as %s", actual_state)

    def update_last_successful_command(self, timestamp: Optional[datetime] = None) -> None:
        """Update timestamp of last successful command"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        current_state = self.get_current_state()
        update_entity = {
            "PartitionKey": "config",
            "RowKey": "current",
            "desired_state": current_state["desired_state"],
            "manual_override": current_state["manual_override"],
            "current_session_start": current_state["current_session_start"],
            "accumulated_seconds": current_state["accumulated_seconds"],
            "last_successful_command": timestamp.isoformat(),
            "last_state_change": current_state["last_state_change"],
            "last_schedule_check": current_state["last_schedule_check"]
        }
        
        self.table_client.upsert_entity(update_entity)
        logger.info("Recorded last successful command at %s", timestamp.isoformat())

    def update_accumulated_time(self, additional_seconds: int) -> None:
        """Update accumulated ON time"""
        current_state = self.get_current_state()
        
        update_entity = {
            "PartitionKey": "config",
            "RowKey": "current",
            "desired_state": current_state["desired_state"],
            "manual_override": current_state["manual_override"],
            "current_session_start": current_state["current_session_start"],
            "accumulated_seconds": current_state["accumulated_seconds"] + additional_seconds,
            "last_successful_command": current_state["last_successful_command"],
            "last_state_change": current_state["last_state_change"],
            "last_schedule_check": current_state["last_schedule_check"]
        }
        
        self.table_client.upsert_entity(update_entity)
        logger.debug("Accumulated time increased by %s seconds (total=%s)",
                     additional_seconds, update_entity["accumulated_seconds"])

    def update_last_schedule_check(self, timestamp: Optional[datetime] = None) -> None:
        """Update timestamp of last schedule check"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        current_state = self.get_current_state()
        update_entity = {
            "PartitionKey": "config",
            "RowKey": "current",
            "desired_state": current_state["desired_state"],
            "manual_override": current_state["manual_override"],
            "current_session_start": current_state["current_session_start"],
            "accumulated_seconds": current_state["accumulated_seconds"],
            "last_successful_command": current_state["last_successful_command"],
            "last_state_change": current_state["last_state_change"],
            "last_schedule_check": timestamp.isoformat()
        }
        
        self.table_client.upsert_entity(update_entity)
        logger.debug("Updated last schedule check to %s", timestamp.isoformat())

    def clear_manual_override(self) -> None:
        """Clear manual override flag"""
        current_state = self.get_current_state()
        
        update_entity = {
            "PartitionKey": "config",
            "RowKey": "current",
            "desired_state": current_state["desired_state"],
            "manual_override": False,
            "current_session_start": current_state["current_session_start"],
            "accumulated_seconds": current_state["accumulated_seconds"],
            "last_successful_command": current_state["last_successful_command"],
            "last_state_change": current_state["last_state_change"],
            "last_schedule_check": current_state["last_schedule_check"]
        }
        
        self.table_client.upsert_entity(update_entity)
        logger.info("Cleared manual override flag")

    def get_time_ranges(self) -> List[Dict[str, Any]]:
        """Get all configured time ranges"""
        try:
            entities = self.table_client.query_entities(
                query_filter="PartitionKey eq 'schedule'"
            )
            
            ranges = []
            for entity in entities:
                ranges.append({
                    "id": entity["RowKey"],
                    "start_time": entity.get("start_time", ""),
                    "end_time": entity.get("end_time", ""),
                    "enabled": entity.get("enabled", True)
                })
            
            ranges = sorted(ranges, key=lambda x: x["start_time"])
            logger.debug("Fetched %s time ranges", len(ranges))
            return ranges
            
        except Exception:
            logger.exception("Failed to fetch time ranges")
            return []

    def add_time_range(self, start_time: str, end_time: str) -> str:
        """Add new time range"""
        range_id = str(uuid.uuid4())[:8]  # Short UUID
        
        entity = {
            "PartitionKey": "schedule",
            "RowKey": range_id,
            "start_time": start_time,
            "end_time": end_time,
            "enabled": True
        }
        
        self.table_client.create_entity(entity)
        logger.info("Added time range %s from %s to %s", range_id, start_time, end_time)
        return range_id

    def delete_time_range(self, range_id: str) -> None:
        """Delete time range"""
        try:
            self.table_client.delete_entity(
                partition_key="schedule",
                row_key=range_id
            )
            logger.info("Deleted time range %s", range_id)
        except ResourceNotFoundError:
            logger.warning("Attempted to delete missing time range %s", range_id)

    def toggle_time_range(self, range_id: str) -> None:
        """Toggle time range enabled/disabled"""
        try:
            entity = self.table_client.get_entity(
                partition_key="schedule",
                row_key=range_id
            )
            
            entity["enabled"] = not entity.get("enabled", True)
            self.table_client.update_entity(entity)
            logger.info("Toggled time range %s to enabled=%s", range_id, entity["enabled"])
            
        except ResourceNotFoundError:
            logger.warning("Attempted to toggle missing time range %s", range_id)

    def is_in_scheduled_time(self, current_time: datetime) -> bool:
        """Check if current time falls within any scheduled range"""
        time_ranges = self.get_time_ranges()
        current_time_str = current_time.strftime("%H:%M")
        in_range = False
        
        for time_range in time_ranges:
            if not time_range.get("enabled", True):
                continue
                
            start_time = time_range["start_time"]
            end_time = time_range["end_time"]
            
            if start_time <= end_time:
                # Same day range (e.g., 09:00 to 17:00)
                if start_time <= current_time_str <= end_time:
                    in_range = True
                    break
            else:
                # Overnight range (e.g., 23:00 to 06:00)
                if current_time_str >= start_time or current_time_str <= end_time:
                    in_range = True
                    break
        
        logger.info("Checked scheduled time for %s -> %s", current_time_str, in_range)
        return in_range

    def should_state_change_for_schedule(self, israel_time: datetime) -> Optional[bool]:
        """Determine if state should change based on schedule - NEW LOGIC: 
        Manual override only lasts until next scheduled period transition"""
        current_state = self.get_current_state()
        
        # Check if we're in scheduled time
        should_be_on = self.is_in_scheduled_time(israel_time)
        current_desired_state = current_state["desired_state"]
        
        # NEW LOGIC: Always honor schedule transitions, clearing manual override
        # Manual override only prevents changes WITHIN the same scheduled period
        
        # Get previous scheduled state (5 minutes ago) to detect transitions
        five_minutes_ago = israel_time - timedelta(minutes=5)
        was_in_scheduled_time = self.is_in_scheduled_time(five_minutes_ago)
        
        # Detect scheduled period transitions
        schedule_transition_detected = should_be_on != was_in_scheduled_time
        
        if schedule_transition_detected:
            # Clear manual override on any scheduled period transition
            # This allows scheduled periods to always take effect
            if should_be_on != current_desired_state:
                logger.info(
                    "Schedule transition detected (%s -> %s). Desired state will be set to %s",
                    was_in_scheduled_time, should_be_on, should_be_on
                )
                return should_be_on  # Transition: follow the schedule
        else:
            # Within same scheduled period - check for manual override protection
            if current_state["manual_override"] and current_state["last_state_change"]:
                last_change = datetime.fromisoformat(current_state["last_state_change"])
                # Only protect manual override if it was recent (within current period)
                # and we're not at a schedule boundary
                if datetime.utcnow() - last_change < timedelta(minutes=30):  # Reduced from 24 hours
                    logger.info("Manual override still active (last_change=%s). Keeping desired state %s",
                                current_state["last_state_change"], current_desired_state)
                    return None  # Keep current state due to recent manual override
        
        # Normal case: set state if different from what schedule requires
        if should_be_on != current_desired_state:
            logger.info("Schedule recommends changing desired state from %s to %s", current_desired_state, should_be_on)
            return should_be_on
        
        logger.info("Schedule check resulted in no change (should_be_on=%s current=%s)", should_be_on, current_desired_state)
        return None  # No change needed
