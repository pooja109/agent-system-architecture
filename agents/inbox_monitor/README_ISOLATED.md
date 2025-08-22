# Inbox Monitor - Isolated Service
================================

This documentation covers the isolated deployment configuration for the Inbox Monitor service, implemented as part of Phase 2 of the AKS Pod Migration.

## Isolation Features

The Inbox Monitor service is now fully self-contained and can run independently:

✅ **Complete Isolation**: No dependencies on parent directory  
✅ **Environment Loading**: Automatic .env file detection and loading  
✅ **Service Scripts**: Shell and Python runners included  
✅ **Container Ready**: Designed for Docker/Kubernetes deployment  
✅ **Backward Compatible**: Still works in existing repo structure  

## Quick Start

### Option 1: Shell Script (Recommended)
```bash
cd agents/inbox_monitor
./run.sh --help
./run.sh check --limit 1 --live --yes
```

### Option 2: Python Runner
```bash
cd agents/inbox_monitor
python run.py --help
python run.py check --limit 1 --live --yes
```

### Option 3: Direct Execution
```bash
cd agents/inbox_monitor
python main.py --help
python main.py check --limit 1 --live --yes
```

## Environment Configuration

### Local Development
Create a `.env` file in the `agents/inbox_monitor` directory:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Environment File Priority
The service searches for environment files in this order:
1. `agents/inbox_monitor/.env` (highest priority)
2. Current working directory `.env`
3. Repository root `.env` (backward compatibility)

### Container Deployment
For containerized environments, set these environment variables:
- `IS_CONTAINER=true` - Disables .env file loading
- `KUBERNETES_SERVICE_HOST` - Auto-detected in Kubernetes

## Service Architecture

### Directory Structure
```
agents/inbox_monitor/
├── __init__.py              # Service metadata and paths
├── main.py                  # Main entry point with env loading
├── run.sh                   # Shell script runner
├── run.py                   # Python runner alternative
├── requirements.txt         # Complete dependencies
├── .env.example            # Environment template
├── .gitignore              # Local file exclusions
├── README_ISOLATED.md      # This documentation
├── config/
│   ├── settings.py         # Enhanced settings with local env loading
│   └── ...
├── services/
├── models/
├── utils/
└── tests/
```

### Key Components

#### Environment Loading (`main.py`)
- Loads .env files before any imports
- Sets `INBOX_MONITOR_ROOT` environment variable
- Configures prompts path relative to service root
- Supports multiple .env file locations

#### Service Metadata (`__init__.py`)
- Defines service version and metadata
- Exports common directory paths
- Ensures service root is in Python path

#### Configuration (`config/settings.py`)
- Priority-based environment loading
- Container environment detection
- Backward compatibility with repo-wide .env

## Isolation Validation

### Self-Test
```bash
cd agents/inbox_monitor
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from models.email import Email
from services.monitor import InboxMonitor
from config.settings import get_settings
print('✅ All imports successful - service is isolated!')
"
```

### Dependency Check
```bash
cd agents/inbox_monitor
python -c "
import ast
import sys
from pathlib import Path

def check_imports(file_path):
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith('..'):
                    return f'Parent import found: {node.module}'
        return None
    except:
        return None

issues = []
for py_file in Path('.').rglob('*.py'):
    if 'test' not in str(py_file):
        issue = check_imports(py_file)
        if issue:
            issues.append(f'{py_file}: {issue}')

if issues:
    print('❌ Parent directory imports found:')
    for issue in issues:
        print(f'  {issue}')
    sys.exit(1)
else:
    print('✅ No parent directory imports found - service is isolated!')
"
```

## Deployment Scenarios

### Local Development
1. Clone repository
2. Navigate to `agents/inbox_monitor`
3. Create `.env` file with your settings
4. Run `./run.sh --install-deps`
5. Execute commands: `./run.sh check --limit 1`

### Docker Container
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY agents/inbox_monitor/ /app/

RUN pip install -r requirements.txt

ENV IS_CONTAINER=true
EXPOSE 8080

CMD ["python", "main.py", "run"]
```

### Kubernetes Pod
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: inbox-monitor
spec:
  containers:
  - name: inbox-monitor
    image: your-registry/inbox-monitor:latest
    env:
    - name: IS_CONTAINER
      value: "true"
    ports:
    - containerPort: 8080
```

## Migration Benefits

### Phase 2 Achievements
- ✅ Complete service isolation
- ✅ Container-ready architecture
- ✅ Multiple execution methods
- ✅ Environment flexibility
- ✅ Backward compatibility
- ✅ Production deployment preparation

### Next Phases
This isolation enables:
- **Phase 3**: Docker containerization
- **Phase 4**: Kubernetes deployment
- **Phase 5**: Service mesh integration
- **Phase 6**: Production scaling

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure you're in the service directory
cd agents/inbox_monitor
python main.py --help
```

#### Environment Variables Not Loading
```bash
# Check .env file exists and is readable
ls -la .env
cat .env | head -5

# Verify environment loading
python -c "
from config.settings import get_settings
settings = get_settings(test_mode=True)
print('✅ Settings loaded successfully')
"
```

#### Permission Issues
```bash
# Make scripts executable
chmod +x run.sh
chmod +x run.py
```

## Support

For issues with the isolated deployment:
1. Check this documentation
2. Validate environment configuration
3. Run isolation tests
4. Review service logs
5. Contact development team

## Version Information

- **Service Version**: 2.0.0
- **Phase**: 2 (Inbox Monitor Isolation)
- **Status**: Complete
- **Next Phase**: Docker Containerization