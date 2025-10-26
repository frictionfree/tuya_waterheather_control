# Azure Deployment Guide - Water Heater Project

This guide documents the complete deployment process for the Water Heater project, which consists of two separate Azure services:
1. **Azure Functions** - Timer-triggered background jobs for device control
2. **Azure Web App** - Flask web interface for user interaction

## Prerequisites

- Azure CLI installed and logged in (`az login`)
- Azure Functions Core Tools installed (`npm install -g azure-functions-core-tools@4`)
- Python 3.12+ with virtual environment

## Project Architecture

```
Water Heater Project
├── Azure Functions (YourFunctionApp)
│   ├── Timer triggers (cron jobs)
│   ├── HTTP status endpoint
│   └── Background device management
└── Azure Web App (YourWebApp)
    ├── Flask web interface
    ├── User authentication
    └── Device control UI
```

## Part 1: Azure Functions Deployment

### Resource Details
- **Function App Name**: `attaswaterheater`
- **Resource Group**: `YourResourceGroup`
- **Runtime**: Python 3.12
- **Plan**: Consumption (serverless)
- **Region**: West Europe

### Step 1: Prepare Function App Configuration

Ensure these files are properly configured:

#### `function_app.py`
- Uses lazy initialization for components to avoid import-time environment variable issues
- Contains timer triggers and HTTP status endpoint
- Implements proper error handling

#### `requirements.txt`
```txt
Flask==3.0.0
requests==2.31.0
azure-data-tables==12.4.4
pytz==2023.3
gunicorn==21.2.0
azure-functions==1.18.0
```

**Critical Notes:**
- DO NOT include `azure-functions-worker` - causes grpcio compilation errors
- Pin exact versions with `==` to avoid build issues
- Avoid dependencies requiring native compilation

#### `host.json`
```json
{
  "version": "2.0",
  "functionTimeout": "00:02:00",
  "logging": {
    "logLevel": {
      "default": "Information"
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

### Step 2: Environment Variables

Configure these in Azure Functions App Settings:
```
PASSWORD=your_secure_password_here
FLASK_SECRET_KEY=your_flask_secret_key_here
CRON_SECRET=your_cron_secret_key_here
TUYA_ACCESS_ID=your_tuya_access_id
TUYA_ACCESS_SECRET=your_tuya_access_secret
TUYA_DEVICE_ID=your_tuya_device_id
TUYA_REGION_ENDPOINT=https://openapi.tuyaeu.com
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=your_storage_account;AccountKey=...
FLASK_ENV=development
PORT=8000
FUNCTIONS_WORKER_RUNTIME=python
```

### Step 3: Deploy Functions

```bash
# Navigate to project directory
cd /path/to/your-project

# Deploy to Azure Functions
func azure functionapp publish attaswaterheater --python

# Expected output should show:
# - Successful build with Python 3.12.12
# - All dependencies installed without compilation errors
# - Functions detected:
#   * cron_status [httpTrigger] - Status monitoring endpoint
#   * device_verification_cron [timerTrigger] - Every 30 seconds
#   * high_frequency_cron [timerTrigger] - Every 1 minute  
#   * low_frequency_cron [timerTrigger] - Every 5 minutes
```

### Step 4: Verify Functions Deployment

```bash
# List all functions in the app
func azure functionapp list-functions YourFunctionAppName --show-keys

# Check function app status
az functionapp show --name YourFunctionAppName --resource-group YourResourceGroup --query "state"

# Monitor logs (optional)
func azure functionapp logstream YourFunctionAppName --timeout 30
```

### Expected Endpoints
- **Status API**: `https://your-function-app.azurewebsites.net/api/cron-status`

---

## Part 2: Azure Web App Deployment

### Resource Details
- **Web App Name**: `YourWebApp`
- **Resource Group**: `YourResourceGroup` 
- **Runtime**: Python 3.12
- **Plan**: App Service Plan (created automatically)
- **Region**: Israel Central

### Step 1: Prepare Web App Files

#### Key Files Required:
- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `templates/` - HTML templates directory
- `.env` - Environment variables (excluded from deployment via .funcignore)

#### Flask App Structure:
```
├── app.py                 # Main Flask application with Application Insights
├── templates/
│   ├── base.html         # Base template
│   ├── login.html        # Login page
│   ├── control.html      # Device control interface
│   └── config.html       # Configuration page
├── requirements.txt      # Dependencies including OpenCensus for App Insights
├── tuya_client.py       # Tuya API client
├── state_manager.py     # State management
└── scheduler.py         # Background scheduler
```

### Step 2: Configure Requirements

Ensure `requirements.txt` includes all Flask dependencies:
```txt
Flask==3.0.0
requests==2.31.0
azure-data-tables==12.4.4
pytz==2023.3
gunicorn==21.2.0
azure-functions==1.18.0
opencensus-ext-azure==1.1.13
opencensus-ext-flask==0.8.0
opencensus-ext-requests==0.8.2
```

**Application Insights Integration:**
The Flask app includes full Application Insights integration via OpenCensus extensions:
- **Automatic request tracking** - All HTTP requests traced
- **Custom logging** - Structured logs with custom dimensions
- **Performance monitoring** - Request durations and dependencies
- **Error tracking** - Automatic exception capture

### Step 3: Deploy Web App

```bash
# Deploy using Azure CLI (from project root directory)
az webapp up --name YourWebApp --resource-group YourResourceGroup --runtime "PYTHON|3.12"

# The command will:
# 1. Create App Service Plan if needed
# 2. Package and upload your code
# 3. Install dependencies via pip
# 4. Start the web application
```

### Step 4: Configure Environment Variables

Set environment variables including Application Insights (via Azure Portal or CLI):

```bash
# Set core environment variables for web app
az webapp config appsettings set --name YourAppName --resource-group YourResourceGroup --settings \
  PASSWORD="your_secure_password" \
  FLASK_SECRET_KEY="your_flask_secret_key" \
  CRON_SECRET="your_cron_secret_key" \
  TUYA_ACCESS_ID="your_tuya_access_id" \
  TUYA_ACCESS_SECRET="your_tuya_access_secret" \
  TUYA_DEVICE_ID="your_tuya_device_id" \
  TUYA_REGION_ENDPOINT="https://openapi.tuyaeu.com" \
  AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=waterheater;AccountKey=..." \
  FLASK_ENV="production"

# Configure Application Insights (replace with your connection string)
az webapp config appsettings set --name YourWebApp --resource-group YourResourceGroup --settings \
  APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=ce6295d5-657e-486f-8913-f95526ef2392;IngestionEndpoint=https://israelcentral-0.in.applicationinsights.azure.com/;LiveEndpoint=https://israelcentral.livediagnostics.monitor.azure.com/;ApplicationId=f4a71de3-fd3a-4fa0-bf4f-3086caf8977f"
```

### Step 4b: Configure Application Logging

Enable comprehensive logging for the web app:

```bash
# Enable application and HTTP logging
az webapp log config --application-logging filesystem --level information --name YourWebApp --resource-group YourResourceGroup
```

### Step 5: Verify Web App Deployment

```bash
# Check web app status
az webapp show --name YourWebApp --resource-group YourResourceGroup --query "state" --output table

# Get web app URL
az webapp show --name YourWebApp --resource-group YourResourceGroup --query "defaultHostName" --output table

# Check deployment logs
az webapp log tail --name YourWebApp --resource-group YourResourceGroup
```

### Expected Endpoints
- **Web Interface**: `https://your-web-app.azurewebsites.net`

### Application Insights Monitoring

Once deployed, the Flask app will automatically send telemetry to Application Insights:

**What's Tracked:**
- **HTTP Requests**: All incoming requests with response times and status codes
- **Custom Events**: User logins, heater toggles, configuration changes
- **Exceptions**: Automatic capture of Python exceptions with stack traces
- **Dependencies**: External API calls (Tuya, Azure Storage)
- **Performance**: Request durations, memory usage, server metrics

**Key Custom Dimensions:**
- `event`: Type of user action (login_success, heater_toggle, etc.)
- `client_ip`: User IP addresses for security monitoring
- `service`: "water-heater-web-app" 
- `component`: "flask-app"

**Viewing Data:**
- Azure Portal → Application Insights → your-app-insights-resource
- Live Metrics Stream for real-time monitoring
- Logs (KQL queries) for detailed analysis
- Performance for request analysis

---

## Common Issues and Solutions

### Azure Functions Issues

**1. "No HTTP triggers found" Error**
- **Cause**: Function definitions not properly detected
- **Solution**: Ensure `@app.function_name()` decorator is used for HTTP functions
- **Fix**: Add explicit function name decorators

**2. grpcio Compilation Errors**
- **Cause**: `azure-functions-worker` dependency pulls in native compilation requirements
- **Solution**: Remove `azure-functions-worker` from requirements.txt
- **Note**: Azure Functions runtime provides this automatically

**3. Import Time Environment Variable Errors**
- **Cause**: Components initialized at module import time
- **Solution**: Use lazy initialization pattern with `get_components()` function

### Web App Issues

**1. Deployment Timeout**
- **Cause**: Large dependency installation or slow build process
- **Solution**: Deploy will continue in background, check status with `az webapp show`

**2. Application Not Starting**
- **Cause**: Missing dependencies or configuration errors
- **Solution**: Check logs with `az webapp log tail`

**3. Environment Variables Not Set**
- **Cause**: Variables not configured in Azure
- **Solution**: Set via Azure Portal or `az webapp config appsettings set`

---

## Monitoring and Maintenance

### Health Checks
```bash
# Check Functions status
curl "https://your-function-app.azurewebsites.net/api/cron-status"

# Check Web App status
curl "https://your-web-app.azurewebsites.net/"
```

### Log Monitoring
```bash
# Functions logs
func azure functionapp logstream YourFunctionAppName

# Web App logs  
az webapp log tail --name YourWebApp --resource-group YourResourceGroup
```

### Update Deployments

For Functions:
```bash
func azure functionapp publish YourFunctionAppName --python
```

For Web App:
```bash
az webapp up --name YourWebApp --resource-group YourResourceGroup --runtime "PYTHON|3.12"
```

---

## Resource Configuration Summary

### Shared Resources
- **Resource Group**: `YourResourceGroup`
- **Storage Account**: `yourstorageaccount` (for Azure Table Storage)
- **Location**: Multiple regions (Functions: West Europe, Web App: Israel Central)

### Security Notes
- All environment variables contain sensitive data
- Function App uses `AuthLevel.FUNCTION` for HTTP endpoints
- Web App includes session-based authentication
- Storage connection strings should be rotated regularly

### Cost Optimization
- Functions use Consumption plan (pay-per-execution)
- Web App uses shared App Service Plan
- Consider scaling down or stopping resources during development

---

## Future Upgrade Checklist

When upgrading this project:

1. **Pre-deployment**:
   - [ ] Update Python dependencies in requirements.txt
   - [ ] Test locally with `python -c "import function_app"`
   - [ ] Verify environment variables are current
   - [ ] Check Azure CLI login status

2. **Functions Deployment**:
   - [ ] Deploy functions first: `func azure functionapp publish attaswaterheater --python`
   - [ ] Verify all 4 functions are detected
   - [ ] Test status endpoint response

3. **Web App Deployment**:
   - [ ] Deploy web app: `az webapp up --name YourWebApp --resource-group YourResourceGroup --runtime "PYTHON|3.12"`
   - [ ] Verify web interface loads
   - [ ] Test user authentication flow

4. **Post-deployment**:
   - [ ] Monitor logs for any errors
   - [ ] Verify both services can access shared storage
   - [ ] Test end-to-end functionality