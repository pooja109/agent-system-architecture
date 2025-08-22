# Email Agent - Isolated Deployment Guide
=========================================

## Overview
This email agent is designed to run as an isolated microservice, either locally or in a containerized environment like Kubernetes.

## Quick Start

### Local Development
1. Copy `.env.sample` to `.env` and configure
2. Install dependencies: `pip install -r requirements.txt`
3. Run the service: `python run.py` or `./run.sh`

### Docker Deployment
```bash
docker build -t email-agent .
docker run --env-file .env -p 8081:8081 email-agent
```

### Kubernetes Deployment
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## Environment Variables

### Required Variables
- `AZURE_KEY_VAULT_URL`: Key Vault URL for secrets
- `AZURE_TENANT_ID`: Azure AD tenant ID
- `AZURE_CLIENT_ID`: Service principal client ID
- `AZURE_CLIENT_SECRET`: Service principal secret
- `DATABRICKS_SERVER_HOSTNAME`: Databricks server
- `DATABRICKS_HTTP_PATH`: Databricks SQL endpoint path

### Optional Variables
See `.env.sample` for complete list of configuration options.

## Health Checks
The service exposes health endpoints on port 8081:
- `/health` - Basic health check
- `/health/detailed` - Detailed health status
- `/ready` - Readiness probe

## Logging
Logs are output in JSON format by default. Set `LOG_FORMAT=text` for human-readable logs.

## Testing Isolation
```bash
# Validate environment
python config/env_validator.py

# Run tests
pytest tests/

# Test in isolated directory
cp -r . /tmp/email-agent-test
cd /tmp/email-agent-test
python run.py test
```

## Troubleshooting

### Service won't start
1. Check environment variables: `python config/env_validator.py`
2. Verify dependencies: `pip list`
3. Check logs: `LOG_LEVEL=DEBUG python main.py`

### Connection issues
1. Verify network connectivity to Azure services
2. Check Key Vault access permissions
3. Validate Databricks credentials

### Email sending failures
1. Check Azure Communication Services configuration
2. Verify sender email is configured in ACS
3. Check recipient email validation

## Architecture
```
email-agent/
├── config/           # Configuration management
├── services/         # Business logic services
├── database/         # Database clients
├── tests/           # Test suites
├── main.py          # Main entry point
├── run.py           # Python runner
├── run.sh           # Shell runner
└── .env.sample      # Environment template
```

## Dependencies
- Python 3.8+
- Azure SDK libraries
- Databricks SQL connector
- See requirements.txt for complete list

## Support
For issues or questions, contact the platform team.