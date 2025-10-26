# Contributing to Tuya Water Heater Control System

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/tuya_waterheather_control.git
   cd tuya_waterheather_control
   ```
3. **Set up development environment**:
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Copy environment template
   cp .env.example .env
   # Edit .env with your actual values
   ```

## 🔧 Development Setup

### Prerequisites
- Python 3.12+
- Tuya IoT Developer Account
- Azure Account (for cloud deployment testing)

### Local Testing
```bash
# Run the Flask application
python app.py

# Test Tuya connectivity
python -c "from tuya_client import TuyaClient; client = TuyaClient(); print(client.get_device_status())"

# Run Azure Functions locally (requires Azure Functions Core Tools)
func start
```

## 📋 Contribution Guidelines

### Code Style
- Follow PEP 8 Python style guidelines
- Use meaningful variable and function names
- Add docstrings for functions and classes
- Keep line length under 100 characters

### Commit Messages
Use conventional commit format:
```
type(scope): description

Examples:
feat(scheduler): add manual override expiration logic
fix(web): resolve button state display issue
docs(readme): update installation instructions
test(tuya): add device communication tests
```

### Branch Naming
- `feature/description-of-feature`
- `fix/description-of-fix`
- `docs/description-of-documentation`

## 🧪 Testing

### Before Submitting
1. **Test locally**: Ensure your changes work in development
2. **Check logs**: No errors in console output
3. **Test UI**: Verify web interface works on mobile
4. **Document changes**: Update README/docs if needed

### Areas that need testing:
- Web interface responsiveness
- Tuya device communication
- Azure deployment process
- Manual override logic
- Time zone handling (Israel timezone)
- State persistence across restarts

## 🐛 Bug Reports

When reporting bugs, include:
- **Environment**: OS, Python version, Azure setup
- **Steps to reproduce**: Detailed steps
- **Expected vs actual behavior**
- **Logs**: Relevant error messages
- **Screenshots**: For UI issues

Use the bug report template:
```markdown
**Bug Description:**
Brief description of the bug

**Environment:**
- OS: [e.g., Windows 10, macOS 12, Ubuntu 20.04]
- Python: [e.g., 3.12.1]
- Browser: [e.g., Chrome 118, Safari 16]

**Steps to Reproduce:**
1. Go to...
2. Click on...
3. See error...

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Logs:**
```
Paste relevant logs here
```

**Screenshots:**
If applicable, add screenshots
```

## 💡 Feature Requests

For new features:
- Check existing issues first
- Explain the use case
- Consider impact on existing functionality
- Suggest implementation approach if possible

## 🏗️ Architecture Notes

### Key Components
- **Flask Web App**: User interface and authentication
- **Azure Functions**: Background state enforcement
- **Tuya Client**: IoT device communication
- **State Manager**: Data persistence with Azure Tables
- **Scheduler**: Time-based automation logic

### Important Concepts
- **Manual Override**: Temporary until next scheduled period
- **State Enforcement**: Continuous verification against external changes
- **CPU Optimization**: Designed for Azure Free Tier limits
- **Session-based Tracking**: Time counter resets on OFF→ON transitions

## 🔒 Security Considerations

- **Never commit credentials** (use .env files)
- **Validate all user inputs**
- **Use environment variables** for secrets
- **Test authentication flows**
- **Consider rate limiting** for API endpoints

## 📝 Documentation

### When to update documentation:
- Adding new features
- Changing configuration options
- Modifying deployment process
- Updating environment variables
- Changing API endpoints

### Documentation files:
- `README.md`: Main project documentation
- `water_heater.md`: Detailed requirements and behavior
- `DEPLOYMENT_GUIDE.md`: Azure deployment instructions
- Code comments: For complex logic

## 🚦 Pull Request Process

1. **Create feature branch** from main
2. **Make your changes** with proper commits
3. **Update documentation** if needed
4. **Test thoroughly** in your environment
5. **Submit pull request** with description

### PR Checklist
- [ ] Code follows project style guidelines
- [ ] Changes are tested locally
- [ ] Documentation is updated
- [ ] Commit messages are clear
- [ ] No sensitive information is committed
- [ ] PR description explains the changes

### PR Description Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] Tested locally
- [ ] Works with Tuya devices
- [ ] UI tested on mobile
- [ ] Azure deployment tested (if applicable)

## Screenshots
If applicable, add screenshots of UI changes
```

## 🏷️ Release Process

Releases follow semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes, backwards compatible

## ❓ Questions?

- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For general questions and ideas
- **Documentation**: Check water_heater.md for detailed behavior

## 🙏 Recognition

Contributors will be recognized in:
- GitHub contributors list
- Release notes for significant contributions
- README acknowledgments section

Thank you for contributing to making home automation more accessible! 🏡⚡