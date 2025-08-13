# Dashboard System Troubleshooting Guide

## Overview

This guide helps resolve common issues with the Rich UI Dashboard system. The dashboard automatically detects terminal capabilities and falls back gracefully, but understanding the troubleshooting steps can help optimize your experience.

## Quick Diagnostics

### Check System Status

```bash
# Test basic functionality
python e2e_demo.py --format dashboard --dry-run

# Check terminal capabilities  
python -c "
from e2e_demo.terminal_detector import TerminalDetector
detector = TerminalDetector()
caps = detector.get_capabilities()
for key, value in caps.items():
    print(f'{key}: {value}')
"

# Test component imports
python -c "
from e2e_demo.dashboard_integration import DashboardIntegration
from e2e_demo.animation_controller import AnimationController
from e2e_demo.service_monitor import ServiceMonitor
print('✅ All components import successfully')
"
```

## Common Issues and Solutions

### 1. Dashboard Not Appearing

**Symptoms:**
- Command runs but shows simple text output instead of rich dashboard
- No visual progress indicators or animations

**Diagnosis:**
```bash
python -c "
from e2e_demo.terminal_detector import TerminalDetector
detector = TerminalDetector()
print(f'Rich support: {detector.supports_rich()}')
print(f'Terminal: {detector.terminal}')
print(f'Size: {detector.width}x{detector.height}')
print(f'Colors: {detector.color_support}')
"
```

**Solutions:**

#### A. Terminal Size Too Small
```bash
# Check terminal size
echo "Terminal size: $(tput cols)x$(tput lines)"

# Resize terminal to at least 80x20
# Or try with smaller content:
python e2e_demo.py --format simple
```

#### B. Rich Library Missing
```bash
# Check Rich installation
python -c "import rich; print(f'Rich version: {rich.__version__}')"

# Install/upgrade Rich
pip install "rich>=13.0.0"
```

#### C. Unsupported Terminal
```bash
# Check terminal type
echo "TERM: $TERM"
echo "TERM_PROGRAM: $TERM_PROGRAM"

# Try forcing color support
export TERM=xterm-256color
python e2e_demo.py --format dashboard --dry-run
```

#### D. CI/CD Environment
```bash
# Check if running in CI
env | grep -E "(CI|JENKINS|TRAVIS|GITHUB_ACTIONS)"

# Force dashboard in CI (not recommended)
unset CI
python e2e_demo.py --format dashboard --dry-run
```

### 2. Performance Issues

**Symptoms:**
- Dashboard updates slowly or appears choppy
- High CPU usage during execution
- System becomes unresponsive

**Diagnosis:**
```bash
# Check performance stats
python -c "
from e2e_demo.animation_controller import create_dashboard_controller
controller = create_dashboard_controller()
controller.start_animation('loading')
import time; time.sleep(2)
stats = controller.get_performance_stats()
print(f'Actual FPS: {stats.get(\"actual_fps\", 0)}')
print(f'Performance degraded: {stats.get(\"performance_degraded\", False)}')
controller.stop_all_animations()
"
```

**Solutions:**

#### A. Reduce Refresh Rate
```bash
# Use simple format for better performance
python e2e_demo.py --format simple

# Or reduce terminal size to trigger slower refresh
# Terminal < 80 chars = 1 FPS
# Terminal < 120 chars = 2 FPS
```

#### B. Disable Animations
```python
# In code, disable performance mode
from e2e_demo.animation_controller import AnimationController
controller = AnimationController()
controller.set_performance_mode(True)  # Disables animations
```

#### C. Check System Resources
```bash
# Monitor CPU usage
top -p $(pgrep -f e2e_demo.py)

# Check memory usage
python -c "
import psutil
print(f'Memory usage: {psutil.virtual_memory().percent}%')
print(f'CPU usage: {psutil.cpu_percent()}%')
"
```

### 3. Output Corruption or Artifacts

**Symptoms:**
- Terminal displays garbled text
- Cursor position issues
- Colors not displaying correctly

**Solutions:**

#### A. Reset Terminal
```bash
# Clear and reset terminal
reset
clear

# Or try tput reset
tput reset
```

#### B. Check Terminal Compatibility
```bash
# Test with different TERM settings
TERM=xterm python e2e_demo.py --format dashboard --dry-run
TERM=xterm-256color python e2e_demo.py --format dashboard --dry-run
TERM=screen python e2e_demo.py --format dashboard --dry-run
```

#### C. Disable Rich Features
```bash
# Force simple output
python e2e_demo.py --format simple

# Check without colors
python e2e_demo.py --format dashboard --no-color
```

### 4. BrokenPipeError Issues

**Symptoms:**
- `BrokenPipeError: [Errno 32] Broken pipe`
- Application crashes when output is piped

**Note:** This should be resolved in the latest version, but if you encounter it:

**Diagnosis:**
```bash
# Test pipe handling
python e2e_demo.py --format dashboard --dry-run | head -5
```

**Solutions:**

#### A. Update Implementation
Ensure you have the latest version with comprehensive error handling.

#### B. Use Simple Format for Piping
```bash
# For scripts and piping, use simple format
python e2e_demo.py --format simple | head -5
python e2e_demo.py --format json > results.json
```

#### C. Alternative Output Methods
```bash
# Save to file instead of piping
python e2e_demo.py --format dashboard --output results.txt
```

### 5. Import Errors

**Symptoms:**
- `ImportError: No module named 'rich'`
- `ModuleNotFoundError: No module named 'e2e_demo.dashboard_integration'`

**Solutions:**

#### A. Install Dependencies
```bash
# Install all requirements
pip install -r requirements.txt

# Or install Rich specifically
pip install "rich>=13.0.0"
```

#### B. Check Python Path
```bash
# Verify current directory
pwd
ls e2e_demo/

# Run from correct directory
cd /path/to/agents/inbox_monitor
python e2e_demo.py --format dashboard --dry-run
```

#### C. Virtual Environment Issues
```bash
# Check active environment
which python
pip list | grep rich

# Reinstall in correct environment
pip uninstall rich
pip install "rich>=13.0.0"
```

### 6. Animation Issues

**Symptoms:**
- Animations not displaying
- Jerky or inconsistent animation
- Animation doesn't stop

**Diagnosis:**
```bash
python -c "
from e2e_demo.animation_controller import create_dashboard_controller
controller = create_dashboard_controller()
print(f'Animation support: {hasattr(controller, \"start_animation\")}')
controller.start_animation('loading')
print(f'Loading active: {controller.is_animation_active(\"loading\")}')
controller.stop_all_animations()
"
```

**Solutions:**

#### A. Check Performance Mode
```python
from e2e_demo.animation_controller import AnimationController
controller = AnimationController()
controller.set_performance_mode(False)  # Enable animations
```

#### B. Verify Frame Rate Settings
```python
# Check animation configuration
stats = controller.get_performance_stats()
print(f"Target FPS: {stats.get('target_fps', 'unknown')}")
print(f"Actual FPS: {stats.get('actual_fps', 'unknown')}")
```

### 7. Service Monitor Issues

**Symptoms:**
- Service status not updating
- Health metrics incorrect
- Operations not being tracked

**Diagnosis:**
```bash
python -c "
from e2e_demo.service_monitor import ServiceMonitor
monitor = ServiceMonitor()
monitor.start_monitoring()

# Test operation
op_id = monitor.start_operation('test_service', 'test_op')
print(f'Operation started: {op_id}')
monitor.complete_operation(op_id, success=True)

summary = monitor.get_health_summary()
print(f'Services: {summary[\"total_services\"]}')
monitor.stop_monitoring()
"
```

**Solutions:**

#### A. Check Callback Registration
```python
def status_callback(service_name, duration, success):
    print(f"{service_name}: {duration:.2f}s ({'✅' if success else '❌'})")

monitor = ServiceMonitor(update_callback=status_callback)
```

#### B. Verify Service Registration
```python
# Services are auto-registered when operations start
statuses = monitor.get_all_service_statuses()
print(f"Registered services: {list(statuses.keys())}")
```

## Environment-Specific Solutions

### Windows

```bash
# Use Windows Terminal for best experience
# Install from Microsoft Store or GitHub

# For Command Prompt, use simple format
python e2e_demo.py --format simple

# For PowerShell, check execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### macOS

```bash
# Use iTerm2 for best experience
# Built-in Terminal.app also works well

# If colors not working:
export TERM=xterm-256color
```

### Linux

```bash
# Most terminals work well, but try these for issues:

# For GNOME Terminal
export TERM=gnome-256color

# For Konsole
export TERM=konsole-256color

# For tmux/screen
export TERM=screen-256color
```

### SSH/Remote

```bash
# Enable X11 forwarding if needed
ssh -X user@remote

# Use simple format over slow connections
python e2e_demo.py --format simple

# Check terminal forwarding
echo $TERM
```

## Advanced Troubleshooting

### Debug Mode

```bash
# Enable verbose output
python e2e_demo.py --format dashboard --detail-level verbose --dry-run

# Python debug mode
python -u e2e_demo.py --format dashboard --dry-run
```

### Performance Profiling

```bash
# Profile with cProfile
python -m cProfile -s cumulative e2e_demo.py --format dashboard --dry-run

# Memory profiling (if memory_profiler installed)
mprof run e2e_demo.py --format dashboard --dry-run
mprof plot
```

### Component Testing

```bash
# Test individual components
python -c "
# Test terminal detection
from e2e_demo.terminal_detector import TerminalDetector
detector = TerminalDetector()
print('Terminal detection:', 'OK' if detector.supports_rich() else 'Limited')

# Test animation controller
from e2e_demo.animation_controller import create_dashboard_controller
controller = create_dashboard_controller()
controller.start_animation('loading')
print('Animation controller:', 'OK' if controller.is_animation_active('loading') else 'Failed')
controller.stop_all_animations()

# Test service monitor
from e2e_demo.service_monitor import ServiceMonitor
monitor = ServiceMonitor()
op_id = monitor.start_operation('test', 'init')
monitor.complete_operation(op_id, True)
print('Service monitor:', 'OK' if monitor.get_health_summary()['total_services'] > 0 else 'Failed')
monitor.stop_monitoring()
"
```

## Getting Help

### Log Collection

If you need to report an issue, collect this information:

```bash
# System information
python --version
pip list | grep rich
echo "OS: $(uname -a)"
echo "Terminal: $TERM"
echo "Size: $(tput cols)x$(tput lines)"

# Component status
python -c "
from e2e_demo.terminal_detector import TerminalDetector
print('Capabilities:', TerminalDetector().get_capabilities())
"

# Run with error output
python e2e_demo.py --format dashboard --dry-run 2>&1 | tee debug.log
```

### Common Environment Variables

```bash
# Force specific behaviors for testing
export TERM=xterm-256color       # Force color support
export COLUMNS=120               # Set terminal width
export LINES=30                  # Set terminal height
unset CI                         # Disable CI detection

# Rich-specific variables  
export FORCE_COLOR=1             # Force color output
export NO_COLOR=1                # Disable color output
```

### Fallback Strategy

If dashboard continues to have issues:

1. **Use simple format**: `--format simple`
2. **Use JSON for automation**: `--format json`
3. **Use table for readability**: `--format table`
4. **Save to file**: `--output results.txt`
5. **Update terminal**: Install modern terminal (Windows Terminal, iTerm2, etc.)

## Performance Tuning

### Optimal Settings by Use Case

#### Development/Interactive
```bash
python e2e_demo.py --format dashboard --business
```

#### CI/CD Pipeline
```bash
python e2e_demo.py --format json --output results.json
```

#### Presentations/Demos
```bash
python e2e_demo.py --format dashboard --timing --verbose
```

#### Low-Resource Systems
```bash
python e2e_demo.py --format simple --business
```

### Terminal Recommendations

| Use Case | Terminal | Configuration |
|----------|----------|---------------|
| Windows Development | Windows Terminal | Default settings |
| macOS Development | iTerm2 | 256-color profile |
| Linux Development | GNOME Terminal | True color enabled |
| SSH/Remote | tmux + modern terminal | 256-color mode |
| CI/CD | Any | Use `--format simple` |

---

**Note:** The dashboard system is designed to be robust and self-healing. Most issues resolve automatically through graceful fallback mechanisms. If you encounter persistent problems, the simple format provides the same information without visual enhancements.