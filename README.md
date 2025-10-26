# Tuya Water Heater Control System

**A complete demonstration of building a cloud-hosted, mobile-friendly smart home control system optimized for free-tier Azure hosting.**

This Flask-based web application showcases:
- **IoT device control** via Tuya API integration for smart water heater management
- **Azure cloud architecture** with Web Apps, Functions, and Table Storage
- **Cost optimization techniques** designed to stay under Azure Free Tier limits
- **Mobile-responsive interface** with session-based authentication and time tracking
- **Intelligent scheduling system** with temporary manual override capabilities

## 🚀 Features

### Core Functionality
- **Web-based Control Interface**: Simple mobile-friendly button to turn water heater ON/OFF
- **Smart Scheduling**: Configure time ranges for automatic operation
- **Manual Override**: Temporary manual control until next scheduled period
- **Session-based Time Tracking**: Accurate runtime tracking that resets per session
- **State Enforcement**: Continuously enforces desired state against external interference

### Intelligent Override Logic
- Manual clicks override current state **temporarily only**
- Overrides **automatically expire** when scheduled periods start/end
- Schedule **always takes control** at transition boundaries
- 30-minute protection within same period prevents rapid state changes

### Azure-Optimized Design
- **Free Tier Compatible**: Designed for Azure Web App Free Tier
- **CPU Optimized**: Smart execution to stay within 1-hour daily CPU limit
- **Dual Cron Architecture**: Separate high/low frequency jobs for efficiency
- **Background Functions**: Azure Functions handle state enforcement

## 🏗️ Architecture & Technical Demonstrations

This project demonstrates several key patterns for cloud-based IoT applications:

### **Azure Integration Patterns**
- **Web App + Functions hybrid architecture** for cost-effective scaling
- **Table Storage** for persistent state management without database costs
- **Application Insights** integration for comprehensive monitoring
- **Free Tier optimization** with CPU-conscious background job design

### **IoT Integration Techniques**
- **Tuya IoT API** integration for smart device control
- **State enforcement** against external device interference
- **Device verification loops** with configurable retry logic
- **Connection pooling** and error handling for reliable API communication

### Core Components
- `app.py` - Flask web interface with mobile-responsive design
- `tuya_client.py` - Tuya IoT API client with robust error handling
- `state_manager.py` - Azure Table Storage state persistence
- `function_app.py` - Azure Functions for background state enforcement
- `templates/` - Mobile-optimized HTML templates

### Background Job Architecture
1. **High Frequency** (1 min): Manual override enforcement and device verification
2. **Low Frequency** (5 min): Scheduled time range processing and state transitions
3. **Device Verification** (30 sec): Continuous monitoring with early exit optimization

## 📋 Requirements

### Hardware
- Tuya-compatible smart switch/relay connected to water heater
- Tuya Developer Account with device access

### Azure Services (Free Tier)
- Azure Web App (Python 3.12)
- Azure Functions (Consumption Plan)
- Azure Table Storage
- Azure Application Insights (optional)

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/tuya_waterheather_control.git
cd tuya_waterheather_control
```

### 2. Environment Setup

Create `.env` file with your credentials:
```bash
# Authentication
PASSWORD=your_secure_password
FLASK_SECRET_KEY=your_flask_secret_key

# Tuya API Credentials
TUYA_ACCESS_ID=your_tuya_access_id
TUYA_ACCESS_SECRET=your_tuya_access_secret
TUYA_DEVICE_ID=your_device_id
TUYA_REGION_ENDPOINT=https://openapi.tuyaeu.com

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=your_azure_storage_connection_string

# Optional
APPLICATIONINSIGHTS_CONNECTION_STRING=your_app_insights_connection_string
```

### 3. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
```

### 4. Azure Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed Azure deployment instructions.

## 📱 Usage

### Web Interface
1. **Login**: Access the web app and authenticate with your password
2. **Control**: Click the main button to toggle water heater state
   - Green = OFF, Red = ON
3. **Schedule**: Configure time ranges in the Config page
4. **Monitor**: View actual runtime counter when device is ON

### Manual Override Behavior

**Example Timeline:**
```
Scheduled Period: 18:00-20:00
- 17:30: User clicks ON → Device ON (manual override)
- 18:00: Schedule starts → Device stays ON (schedule takes control)
- 18:30: User clicks OFF → Device OFF (manual override within period)
- 20:00: Schedule ends → Device OFF (automatic)
```

## 🔧 Configuration

### Time Ranges
Configure in the web interface:
- Start Time: HH:MM format (24-hour)
- End Time: HH:MM format (24-hour)
- Timezone: All times in Israel Standard Time (Asia/Jerusalem)

### Override Protection
- Manual overrides last until next scheduled period boundary
- Within same period: 30-minute protection against automatic changes
- Schedule transitions always take precedence

## 📊 Monitoring

### Built-in Endpoints
- `/status`: Health check with current state
- `/debug/current-state`: Detailed state information (requires login)
- `/cron-status`: Azure Functions job health

### Application Insights
Optional Azure Application Insights integration for:
- Request tracing
- Performance monitoring
- Error tracking
- Custom telemetry

## 🔒 Security Features

- Single password authentication with persistent sessions
- Environment variable protection for credentials
- Input validation and sanitization
- HTTPS enforcement in production
- No sensitive data logging

## 💰 Cost Optimization

### Azure Free Tier Compatibility
- Web App: Free tier (1 GB storage, 1 hour CPU/day)
- Functions: 1M requests/month, 400,000 GB-seconds
- Storage: 5 GB with 20,000 transactions
- Application Insights: 1 GB telemetry/month

### CPU Budget Management
- Smart early exit patterns
- Conditional execution logic
- Connection pooling
- Estimated usage: <1 hour total daily CPU

## 🧪 Testing

### Local Testing
```bash
# Run development server
python app.py

# Test Tuya connection
python -c "from tuya_client import TuyaClient; client = TuyaClient(); print(client.get_device_status())"
```

### Deployment Testing
```bash
# Test Azure Functions locally
func start

# Test web app endpoints
curl https://yourapp.azurewebsites.net/status
```

## 📚 Documentation

- [Mission Document](water_heater.md): Detailed requirements and behavior
- [Deployment Guide](DEPLOYMENT_GUIDE.md): Step-by-step Azure deployment
- [API Documentation](heather_api.py): Device communication interface

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🚨 Disclaimer

This project controls electrical appliances. Ensure proper electrical safety measures and compliance with local regulations. Users assume all responsibility for safe operation.

## 🆘 Support

For questions or issues:
- Open a GitHub Issue
- Check the [Mission Document](water_heater.md) for detailed behavior
- Review [Deployment Guide](DEPLOYMENT_GUIDE.md) for setup help

---

**Built with ❤️ for reliable, cost-effective home automation**