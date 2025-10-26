#!/bin/bash
echo "Starting Water Heater Web App deployment..."

# Set default PORT if not provided
export PORT=${PORT:-8000}

# Ensure we're using the right Python version
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "PORT: $PORT"

# Install dependencies explicitly
echo "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Verify critical packages are installed
echo "Verifying critical packages..."
python -c "import pytz; print(f'pytz version: {pytz.__version__}')" || echo "ERROR: pytz not installed"
python -c "import flask; print(f'Flask version: {flask.__version__}')" || echo "ERROR: Flask not installed"

# List all installed packages for debugging
echo "All installed packages:"
python -m pip list

# Start the application
echo "Starting Gunicorn server on port $PORT..."
exec gunicorn --bind=0.0.0.0:$PORT --timeout 600 --workers 1 --log-level debug app:app