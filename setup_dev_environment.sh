#!/bin/bash
# Development Environment Setup Script for Water Heater Control App

set -e

echo "🚀 Setting up Water Heater Control App development environment"
echo "=" * 60

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    echo "Install Python 3.8+ and try again"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv-3.13" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv-3.13
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo "📦 Installing Python dependencies..."
source venv-3.13/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✓ Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "🔧 IMPORTANT: Edit .env file with your credentials:"
    echo "   - PASSWORD: Your secure password"
    echo "   - TUYA_* variables: From Tuya IoT Platform"
    echo "   - AZURE_STORAGE_CONNECTION_STRING: From Azure Storage Account"
    echo ""
else
    echo "✓ .env file already exists"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials"
echo "2. Open VS Code: code ."
echo "3. Run 'Test Tuya Integration' debug configuration"
echo "4. Run 'Water Heater App - Local Debug' to start the app"
echo ""
echo "Available debug configurations:"
echo "  - Water Heater App - Local Debug (Main application)"
echo "  - Flask Development Server (Alternative startup)"
echo "  - Test Tuya Integration (Test device connection)"
echo "  - Run Pre-Deployment Tests (Full test suite)"
echo ""
echo "💡 The app will run at http://localhost:8000"