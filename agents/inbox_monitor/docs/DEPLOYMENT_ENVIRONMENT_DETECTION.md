# Environment Detection Patterns for Deployment

This document outlines how the Inbox Monitor system detects and adapts to different deployment environments.

## Environment Detection Logic

The system automatically detects the deployment environment using the following priority order:

### 1. Explicit Environment Configuration (Highest Priority)
Set the `ENVIRONMENT` environment variable to explicitly specify the environment:

```bash
# Development
export ENVIRONMENT=development

# Production  
export ENVIRONMENT=production

# Testing/CI
export ENVIRONMENT=testing

# Kubernetes
export ENVIRONMENT=kubernetes

# Generic containerized
export ENVIRONMENT=containerized
```

### 2. Automatic Detection Patterns

When no explicit `ENVIRONMENT` variable is set, the system uses these detection patterns:

#### Kubernetes Detection
The system detects Kubernetes environments by checking for:
- `/var/run/secrets/kubernetes.io/serviceaccount/` directory
- `KUBERNETES_SERVICE_HOST` environment variable
- `KUBERNETES_SERVICE_PORT` environment variable

#### Production Environment Detection
Production environments are detected by:
- `NODE_ENV=production` environment variable
- `FLASK_ENV=production` environment variable  
- `DJANGO_SETTINGS_MODULE` containing "production"
- Domain patterns matching production domains

#### Testing/CI Environment Detection
Testing environments are detected by:
- `CI=true` environment variable (GitHub Actions, GitLab CI, etc.)
- `BUILD_ID` environment variable (Jenkins)
- `GITHUB_ACTIONS=true` environment variable
- `PYTEST_CURRENT_TEST` environment variable

#### Container Detection
Containerized environments are detected by:
- Presence of `/.dockerenv` file
- `container=docker` in `/proc/1/cgroup`
- `DOCKER_CONTAINER=true` environment variable

### 3. Default Behavior
If no environment indicators are found, the system defaults to **DEVELOPMENT** environment.

## Environment-Specific Behavior

### Development Environment
- **Default behavior** when no other environment is detected
- Enhanced debugging and logging enabled
- Development-friendly error messages
- Local file system access patterns

### Production Environment  
- Optimized for performance and security
- Reduced logging verbosity
- Enhanced error handling
- Cloud service integration enabled

### Testing Environment
- Isolated test execution
- Mock service integration
- Enhanced test reporting
- Temporary resource cleanup

### Kubernetes Environment
- Service discovery integration
- Health check endpoints enabled
- Resource limit awareness
- Cluster-specific logging

### Containerized Environment
- Container-aware resource detection
- Docker-specific volume handling
- Container orchestration integration

## Deployment Configuration Examples

### Docker Deployment
```dockerfile
ENV ENVIRONMENT=production
ENV NODE_ENV=production
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inbox-monitor
spec:
  template:
    spec:
      containers:
      - name: inbox-monitor
        env:
        - name: ENVIRONMENT
          value: "kubernetes"
        - name: NODE_ENV  
          value: "production"
```

### CI/CD Pipeline
```yaml
- name: Test
  env:
    ENVIRONMENT: testing
    CI: true
  run: pytest
```

### Development Setup
```bash
# No explicit environment - defaults to development
python main.py

# Or explicitly set development
export ENVIRONMENT=development
python main.py
```

## Troubleshooting Environment Detection

### Check Current Environment Detection
Use the CLI environment detection command:
```bash
python -m cli.environment_detector --info
```

### Common Issues

1. **Environment not detected correctly**
   - Check environment variables are properly set
   - Verify file system indicators are present
   - Use explicit `ENVIRONMENT` variable for certainty

2. **Production settings in development**
   - Ensure no production environment variables are set
   - Check for accidental `.env` files with production settings

3. **Test isolation issues** 
   - Use `ENVIRONMENT=testing` for test runs
   - Clear production environment variables during testing

## Best Practices

1. **Always set explicit environment variables** in deployment configurations
2. **Use environment-specific configuration files** alongside environment detection  
3. **Test environment detection** as part of deployment validation
4. **Monitor environment detection logs** to ensure correct detection in production

## Configuration Priority

The system follows this configuration priority:
1. Explicit `ENVIRONMENT` environment variable
2. Automatic detection patterns (Kubernetes, CI, container indicators)
3. Default to DEVELOPMENT environment

This ensures predictable behavior while providing flexibility for various deployment scenarios.