import azure.functions as func
import logging
import requests
import os
import json
from datetime import datetime

# Import your existing modules
from tuya_client import TuyaClient
from state_manager import StateManager
from scheduler import BackgroundScheduler

app = func.FunctionApp()

# Initialize components lazily to avoid import-time errors
tuya_client = None
state_manager = None
scheduler = None

def get_components():
    """Lazy initialization of components"""
    global tuya_client, state_manager, scheduler
    if tuya_client is None:
        tuya_client = TuyaClient()
        state_manager = StateManager()
        scheduler = BackgroundScheduler(tuya_client, state_manager)
    return tuya_client, state_manager, scheduler

@app.timer_trigger(schedule="0 * * * * *", arg_name="timer", run_on_startup=False)
def high_frequency_cron(timer: func.TimerRequest) -> None:
    """High-frequency timer: Every 1 minute - User state enforcement"""
    
    if timer.past_due:
        logging.info('High frequency timer is past due!')

    try:
        _, _, scheduler = get_components()
        result = scheduler.run_high_frequency_job()
        logging.info(f'High frequency job result: {result}')
        
        # Log important information for monitoring
        if result.get('enforcement_needed'):
            logging.warning(f"Device enforcement needed - Desired: {result.get('desired_state')}, Actual: {result.get('actual_device_state')}")
        
        if result.get('execution_time', 0) > 30:
            logging.warning(f"High execution time: {result.get('execution_time')}s")
            
    except Exception as e:
        logging.error(f'High frequency job failed: {str(e)}')

@app.timer_trigger(schedule="*/30 * * * * *", arg_name="timer", run_on_startup=False)
def device_verification_cron(timer: func.TimerRequest) -> None:
    """Device verification timer: Every 30 seconds - Real device state verification for accurate time counting"""
    
    if timer.past_due:
        logging.info('Device verification timer is past due!')

    try:
        # Only run if device should be ON (to minimize CPU usage)
        _, state_manager, scheduler = get_components()
        current_state = state_manager.get_current_state()
        
        if not current_state["desired_state"]:
            return  # Skip if device should be OFF
        
        # Verify actual device state for accurate time tracking
        actual_state = scheduler._verify_actual_device_state()
        
        # Update actual device state (this accumulates real ON time)
        state_manager.update_actual_device_state(actual_state)
        
        logging.info(f'Device verification result - Desired: {current_state["desired_state"]}, Actual: {actual_state}')
        
        if actual_state != current_state["desired_state"]:
            logging.warning(f"Device verification mismatch - Desired: {current_state['desired_state']}, Actual: {actual_state}")
            # Trigger immediate enforcement by running high-frequency job
            result = scheduler.run_high_frequency_job()
            logging.info(f"Triggered enforcement job result: {result}")
            
    except Exception as e:
        logging.error(f'Device verification job failed: {str(e)}')

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False) 
def low_frequency_cron(timer: func.TimerRequest) -> None:
    """Low-frequency timer: Every 5 minutes - Scheduled time ranges"""
    
    if timer.past_due:
        logging.info('Low frequency timer is past due!')

    try:
        _, _, scheduler = get_components()
        result = scheduler.run_low_frequency_job()
        logging.info(f'Low frequency job result: {result}')
        
        # Log schedule changes
        if result.get('status') == 'schedule_triggered':
            logging.info(f"Schedule triggered state change to: {result.get('new_desired_state')}")
            
    except Exception as e:
        logging.error(f'Low frequency job failed: {str(e)}')

@app.function_name("cron_status")
@app.route(route="cron-status", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def cron_status(req: func.HttpRequest) -> func.HttpResponse:
    """Status endpoint for monitoring cron job health"""
    
    try:
        _, state_manager, scheduler = get_components()
        current_state = state_manager.get_current_state()
        stats = scheduler.get_execution_stats()
        
        return func.HttpResponse(
            body=json.dumps({
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat(),
                "current_state": current_state,
                "stats": stats
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            body=json.dumps({"status": "error", "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )