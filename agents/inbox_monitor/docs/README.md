# Inbox Monitor Documentation Hub

Welcome to the Inbox Monitor focused documentation guides. This directory contains task-oriented guides designed to help you quickly accomplish specific objectives with the AI-powered email classification system.

## Quick Navigation

### 🚀 Getting Started
- **[Setup Guide](SETUP.md)** - Quick guide to get the Inbox Monitor running locally with all service integrations
- **[Configuration Guide](CONFIGURATION.md)** - Complete multi-service authentication and environment setup reference

### 🧠 Understanding the AI System
- **[Scenarios Guide](SCENARIOS.md)** - Detailed explanation of 6 AI email classification scenarios and automated business actions
- **[User Guide](USER_GUIDE.md)** - Complete user reference and operational workflows

### 🧪 Testing & Validation
- **[Testing Guide](TESTING.md)** - Complete test execution guide with advanced test runner CLI

### 🔧 Problem Solving
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Service-specific debugging and multi-service integration issues

### 🎭 Demonstrations & Training
- **[Demo Playbook](DEMO_PLAYBOOK.md)** - Demo scenarios and presentation guide
- **[UI Components Overview](UI_COMPONENTS_OVERVIEW.md)** - User interface system guide

### 🏗️ Technical References
- **[Services Overview](SERVICES-OVERVIEW.md)** - Complete services architecture documentation
- **[Utilities Reference](UTILS.md)** - Comprehensive utilities and scripts documentation
- **[Logging Migration Guide](LOGGING-MIGRATION-GUIDE.md)** - Updated logging system guide

### 📚 Complete Reference
- **[Main README](../README.md)** - Comprehensive system documentation and architecture overview

## Documentation Purpose

Each guide is focused on specific workflows and user needs:

| Guide | Purpose | Target User | Key Content |
|-------|---------|-------------|-------------|
| **Setup** | Get system running quickly | New developers, DevOps | Installation, dependencies, service validation |
| **Configuration** | Service authentication setup | Technical teams | OAuth, Key Vault, environment variables |
| **Scenarios** | Understand business logic | All developers, Product | AI classification, automated actions, examples |
| **User Guide** | Complete operational reference | End users, Admins | Daily operations, workflows, maintenance |
| **Testing** | Run tests and validate system | Developers, QA, CI/CD | Advanced test runner, profiles, reporting, CI integration |
| **Troubleshooting** | Resolve integration issues | Operations, Support | Service-specific debugging, error resolution |
| **Demo Playbook** | System demonstrations | Sales, Training | Demo scenarios, presentation guides |
| **UI Components** | User interface overview | Developers, Users | UI system, components, user experience |
| **Services Overview** | Technical architecture | Developers, Architects | Services, APIs, integration patterns |
| **Utilities Reference** | Developer tools and scripts | Developers, DevOps | Utility scripts, tools, helper functions |
| **Logging Migration** | Logging system guide | Developers, Operations | Logging setup, configuration, best practices |

## System Overview

The Inbox Monitor is an AI-powered email processing system that:

1. **Monitors** designated email inbox using Microsoft Graph API
2. **Classifies** customer responses using Azure AI Foundry (6 distinct intents)
3. **Routes** emails to appropriate automated business actions
4. **Integrates** with Salesforce CRM, Databricks expert assignment, and email forwarding

## Key Service Integrations

- **Microsoft Graph API**: Email monitoring and message processing
- **Azure AI Foundry**: Intent classification with confidence scoring
- **Salesforce**: Automated case creation and contact management  
- **Databricks**: Expert assignment tracking and round-robin algorithm
- **Azure Key Vault**: Centralized credential management for all services

## Common Workflows

### New Developer Onboarding
1. Start with [Setup Guide](SETUP.md) for initial system installation
2. Review [Configuration Guide](CONFIGURATION.md) for service authentication  
3. Study [Scenarios Guide](SCENARIOS.md) to understand business logic
4. Bookmark [Troubleshooting Guide](TROUBLESHOOTING.md) for issue resolution

### Production Deployment
1. Follow [Configuration Guide](CONFIGURATION.md) for production environment setup
2. Use [Setup Guide](SETUP.md) validation commands to verify all services
3. Implement [Troubleshooting Guide](TROUBLESHOOTING.md) health monitoring
4. Reference [Scenarios Guide](SCENARIOS.md) for business logic validation

### Issue Resolution
1. Use [Troubleshooting Guide](TROUBLESHOOTING.md) quick diagnostic commands
2. Follow service-specific troubleshooting procedures
3. Reference [Configuration Guide](CONFIGURATION.md) for authentication issues
4. Check [Scenarios Guide](SCENARIOS.md) for business logic debugging

## Architecture Highlights

**OAuth Migration**: System uses OAuth service principal authentication for enhanced security and 80-90% connection overhead reduction.

**AI Classification**: Azure AI Foundry with advanced prompt engineering classifies emails into 6 distinct business intents with confidence scoring.

**Multi-Service Automation**: Each classified email triggers coordinated actions across multiple integrated services for complete customer response handling.

**Connection Pooling**: Efficient database connection management reduces resource usage and improves response times.

**Health Monitoring**: Comprehensive health check endpoints enable production monitoring and alerting.

## Getting Help

For specific issues:
1. **Service Integration Problems**: See [Troubleshooting Guide](TROUBLESHOOTING.md) service-specific sections
2. **Configuration Questions**: Reference [Configuration Guide](CONFIGURATION.md) detailed examples
3. **Business Logic Understanding**: Study [Scenarios Guide](SCENARIOS.md) for complete workflow explanation
4. **System Setup Issues**: Follow [Setup Guide](SETUP.md) step-by-step procedures

For comprehensive system understanding, see the [Main README](../README.md) with complete technical documentation.