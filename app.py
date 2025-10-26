import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps

import pytz

# Application Insights imports
try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from opencensus.ext.azure.trace_exporter import AzureExporter
    from opencensus.ext.flask.flask_middleware import FlaskMiddleware
    from opencensus.trace.samplers import ProbabilitySampler
    print("Application Insights imports successful")
except ImportError as e:
    print(f"Application Insights imports failed: {e}")
    # Set dummy classes to avoid errors
    class AzureLogHandler:
        def __init__(self, *args, **kwargs): 
            self.level = logging.INFO
        def setLevel(self, level): 
            self.level = level
        def add_telemetry_processor(self, *args): pass
        def handle(self, record): pass  # Required by logging system
        def emit(self, record): pass    # Required by logging system
    class AzureExporter:
        def __init__(self, *args, **kwargs): pass
    class FlaskMiddleware:
        def __init__(self, *args, **kwargs): pass
    class ProbabilitySampler:
        def __init__(self, *args, **kwargs): pass

# Try importing business logic modules
try:
    from state_manager import StateManager
    print("Business modules imported successfully")
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Business modules not available: {e}")
    # Create dummy class for testing
    class StateManager:
        def get_current_state(self): return {"desired_state": False, "accumulated_seconds": 0}
        def set_desired_state(self, *args, **kwargs): pass
        def get_time_ranges(self): return []
        def add_time_range(self, *args): pass
        def delete_time_range(self, *args): pass
    MODULES_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure Application Insights
APPINSIGHTS_CONNECTION_STRING = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
azure_handler = None

if APPINSIGHTS_CONNECTION_STRING:
    try:
        # Configure Application Insights tracing
        middleware = FlaskMiddleware(
            app,
            exporter=AzureExporter(connection_string=APPINSIGHTS_CONNECTION_STRING),
            sampler=ProbabilitySampler(rate=1.0)  # Sample 100% of requests
        )
        
        # Configure Application Insights logging
        azure_handler = AzureLogHandler(connection_string=APPINSIGHTS_CONNECTION_STRING)
        azure_handler.setLevel(logging.INFO)
        
        # Add custom properties to all logs
        azure_handler.add_telemetry_processor(
            lambda envelope: setattr(envelope.data.baseData, 'properties', 
                                     envelope.data.baseData.properties.update({
                                         'service': 'water-heater-web-app',
                                         'component': 'flask-app'
                                     }) or envelope.data.baseData.properties)
        )
    except Exception as e:
        print(f"Failed to configure Application Insights: {e}")
        azure_handler = None

# Configure logging for Azure Web App
if not app.debug:
    # Production logging configuration for Azure
    handlers = [logging.StreamHandler()]  # Azure Web App captures stdout/stderr
    
    # Add Application Insights handler if available and properly configured
    if azure_handler is not None:
        handlers.append(azure_handler)
        print('Application Insights logging configured successfully')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
        handlers=handlers
    )
    
    # Set Flask app logger level
    app.logger.setLevel(logging.INFO)
    
    # Add Application Insights handler to Flask logger if available
    if azure_handler is not None:
        app.logger.addHandler(azure_handler)
    
    # Configure werkzeug (Flask's WSGI server) logging
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    
    # Reduce noise from other libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
else:
    # Development logging
    logging.basicConfig(level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)

# Initialize components
state_manager = StateManager()

# Israel timezone
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        
        if password == os.environ.get('PASSWORD'):
            session['authenticated'] = True
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=60)  # 2 months
            app.logger.info(f'Successful login from IP: {client_ip}', extra={'custom_dimensions': {'event': 'user_login_success', 'client_ip': client_ip}})
            return redirect(url_for('control'))
        else:
            app.logger.warning(f'Failed login attempt from IP: {client_ip}', extra={'custom_dimensions': {'event': 'user_login_failed', 'client_ip': client_ip}})
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    app.logger.info(f'User logged out from IP: {client_ip}')
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def control():
    try:
        state = state_manager.get_current_state()
        app.logger.info(f'Control page accessed - Desired state: {state["desired_state"]}, Accumulated time: {state["accumulated_seconds"]}s')
        
        # Show ONLY accumulated time that reflects actual verified device ON time
        # Do NOT add any speculative time based on desired state
        accumulated_time = state['accumulated_seconds']
        
        # The accumulated_seconds field is updated by the background jobs based on 
        # actual device state verification, so it's the most accurate representation
        
        return render_template('control.html', 
                             desired_state=state['desired_state'],
                             actual_device_state=state.get('actual_device_state', False),
                             accumulated_time=accumulated_time,
                             enforcement_active=state.get('manual_override', False))
    except Exception as e:
        app.logger.error(f'Error accessing control page: {str(e)}')
        return 'Error loading control page', 500

@app.route('/toggle', methods=['POST'])
@login_required
def toggle_heater():
    try:
        current_state = state_manager.get_current_state()
        new_state = not current_state['desired_state']
        
        app.logger.info(f'Manual toggle requested - Changing from {current_state["desired_state"]} to {new_state}', 
                        extra={'custom_dimensions': {'event': 'heater_toggle_request', 'old_state': current_state["desired_state"], 'new_state': new_state}})
        
        state_manager.set_desired_state(new_state, manual_override=True)
        
        # Get updated state after change
        updated_state = state_manager.get_current_state()
        
        app.logger.info(f'State toggled successfully - New desired state: {new_state}, Manual override: True',
                       extra={'custom_dimensions': {'event': 'heater_toggle_success', 'desired_state': new_state, 'manual_override': True}})
        
        return jsonify({
            'success': True, 
            'new_state': new_state,
            'accumulated_seconds': updated_state['accumulated_seconds'],
            'actual_device_state': updated_state.get('actual_device_state', False)
        })
    except Exception as e:
        app.logger.error(f'Error toggling heater state: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/config')
@login_required
def config():
    time_ranges = state_manager.get_time_ranges()
    return render_template('config.html', time_ranges=time_ranges)

@app.route('/config/add', methods=['POST'])
@login_required
def add_time_range():
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    
    if start_time and end_time:
        try:
            state_manager.add_time_range(start_time, end_time)
            app.logger.info(f'Time range added: {start_time} - {end_time}')
        except Exception as e:
            app.logger.error(f'Error adding time range {start_time}-{end_time}: {str(e)}')
    else:
        app.logger.warning(f'Invalid time range submission - Start: {start_time}, End: {end_time}')
    
    return redirect(url_for('config'))

@app.route('/config/delete/<range_id>', methods=['POST'])
@login_required
def delete_time_range(range_id):
    try:
        state_manager.delete_time_range(range_id)
        app.logger.info(f'Time range deleted: {range_id}')
    except Exception as e:
        app.logger.error(f'Error deleting time range {range_id}: {str(e)}')
    return redirect(url_for('config'))

# NOTE: Scheduler/cron endpoints removed - these belong in Azure Functions
# Azure Functions will handle:
# - High-frequency job (1 minute): User state enforcement
# - Low-frequency job (5 minutes): Scheduled time ranges

@app.route('/status')
def status():
    """Health check endpoint"""
    state = state_manager.get_current_state()
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'israel_time': datetime.now(ISRAEL_TZ).isoformat(),
        'current_state': state
    })

@app.route('/debug/current-state')
@login_required
def debug_current_state():
    """Debug endpoint to view current state (web app only)"""
    return jsonify({
        'debug': True,
        'current_state': state_manager.get_current_state(),
        'time_ranges': state_manager.get_time_ranges()
    })

if __name__ == '__main__':
    app.logger.info('Starting Water Heater Flask application')
    app.logger.info(f'Environment: {"production" if not app.debug else "development"}')
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))