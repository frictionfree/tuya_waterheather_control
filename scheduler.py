import pytz
from datetime import datetime, timedelta
from typing import Dict, Any
import time

class BackgroundScheduler:
    def __init__(self, tuya_client, state_manager):
        self.tuya_client = tuya_client
        self.state_manager = state_manager
        self.israel_tz = pytz.timezone('Asia/Jerusalem')

    def run_high_frequency_job(self) -> Dict[str, Any]:
        """
        High-frequency job (1 minute intervals)
        Purpose: Enforce user-triggered state changes with eventual consistency
        CPU Optimization: Early exit if no manual override active
        """
        start_time = time.time()
        
        try:
            # Get current state - single Azure Table query
            current_state = self.state_manager.get_current_state()
            
            # State enforcement: Always verify actual device state matches desired state
            desired_state = current_state["desired_state"]
            actual_device_state = self._verify_actual_device_state()
            
            # Early exit optimization: Skip if actual state already matches desired state
            if actual_device_state == desired_state:
                # Persist verification so state table reflects the latest device status
                self.state_manager.update_actual_device_state(actual_device_state)
                return {
                    "status": "skipped",
                    "reason": "Actual device state matches desired state", 
                    "execution_time": round(time.time() - start_time, 3),
                    "cpu_optimized": True,
                    "desired_state": desired_state,
                    "actual_device_state": actual_device_state
                }
            
            # Execute state enforcement to match desired state
            if desired_state:
                # For ON state: Continuous enforcement with verification
                result = self.tuya_client.ensure_state_with_retries(True, max_attempts=7)
            else:
                # For OFF state: Single attempt 
                result = self.tuya_client.set_device_state(False, max_attempts=1)
                
            # Re-verify device state after command execution
            actual_device_state_after = self._verify_actual_device_state()
            
            # Update actual device state in storage
            self.state_manager.update_actual_device_state(actual_device_state_after)
            
            if result.get("success") or result.get("skipped"):
                self.state_manager.update_last_successful_command()
            
            return {
                "status": f"enforced_{'on' if desired_state else 'off'}",
                "desired_state": desired_state,
                "actual_device_state_before": actual_device_state,
                "actual_device_state_after": actual_device_state_after,
                "tuya_result": result,
                "execution_time": round(time.time() - start_time, 3),
                "enforcement_needed": True,
                "enforcement_successful": actual_device_state_after == desired_state
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "execution_time": round(time.time() - start_time, 3)
            }

    def run_low_frequency_job(self) -> Dict[str, Any]:
        """
        Low-frequency job (5 minute intervals)
        Purpose: Handle scheduled time ranges
        CPU Optimization: Only runs if scheduled state differs from current
        """
        start_time = time.time()
        
        try:
            # Get Israel time
            israel_time = datetime.now(self.israel_tz)
            current_state = self.state_manager.get_current_state()
            
            # Early exit optimization: Skip if last schedule check was recent (< 4 minutes)
            if current_state.get("last_schedule_check"):
                last_check = datetime.fromisoformat(current_state["last_schedule_check"])
                if datetime.utcnow() - last_check < timedelta(minutes=4):
                    return {
                        "status": "skipped",
                        "reason": "Schedule checked recently",
                        "execution_time": round(time.time() - start_time, 3),
                        "cpu_optimized": True
                    }
            
            # Update schedule check timestamp
            self.state_manager.update_last_schedule_check()
            
            # Determine if state should change based on schedule
            should_change_to = self.state_manager.should_state_change_for_schedule(israel_time)
            
            if should_change_to is None:
                return {
                    "status": "no_change_needed",
                    "current_state": current_state["desired_state"],
                    "israel_time": israel_time.strftime("%H:%M"),
                    "execution_time": round(time.time() - start_time, 3)
                }
            
            # Set new desired state (this will trigger high-frequency job to enforce)
            self.state_manager.set_desired_state(should_change_to, manual_override=False)
            
            return {
                "status": "schedule_triggered",
                "new_desired_state": should_change_to,
                "israel_time": israel_time.strftime("%H:%M"),
                "execution_time": round(time.time() - start_time, 3),
                "note": "High-frequency job will enforce this state"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "execution_time": round(time.time() - start_time, 3)
            }

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics for monitoring"""
        current_state = self.state_manager.get_current_state()
        israel_time = datetime.now(self.israel_tz)
        
        stats = {
            "current_desired_state": current_state["desired_state"],
            "manual_override_active": current_state.get("manual_override", False),
            "israel_time": israel_time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_in_scheduled_time": self.state_manager.is_in_scheduled_time(israel_time),
            "last_successful_command": current_state.get("last_successful_command"),
            "last_schedule_check": current_state.get("last_schedule_check"),
            "accumulated_time_seconds": current_state.get("accumulated_seconds", 0)
        }
        
        # Calculate current session time if ON
        if current_state["desired_state"] and current_state.get("current_session_start"):
            session_start = datetime.fromisoformat(current_state["current_session_start"])
            current_session_seconds = int((datetime.utcnow() - session_start).total_seconds())
            stats["current_session_seconds"] = current_session_seconds
            stats["total_display_seconds"] = stats["accumulated_time_seconds"] + current_session_seconds
        
        return stats

    def _verify_actual_device_state(self) -> bool:
        """Verify the actual device state by querying Tuya API"""
        try:
            # Get device status with a short timeout to avoid CPU overhead
            status_list = self.tuya_client.get_device_status()
            access_token = self.tuya_client._get_access_token()
            switch_code, actual_state = self.tuya_client._find_switch_code(status_list, access_token)
            
            return actual_state if actual_state is not None else False
            
        except Exception as e:
            # If verification fails, assume device is not responding (OFF)
            # This handles flaky connectivity gracefully
            return False
