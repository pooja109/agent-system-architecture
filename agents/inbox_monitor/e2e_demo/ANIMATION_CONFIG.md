# Animation Controller Configuration Guide

## Overview

The Animation Controller manages smooth visual transitions and effects in the dashboard system. It provides comprehensive configuration options to balance visual quality with performance requirements across different environments.

## Quick Start

### Pre-configured Controllers

Use factory functions for common scenarios:

```python
from e2e_demo.animation_controller import (
    create_dashboard_controller,     # Balanced performance (recommended)
    create_loading_controller,       # Optimized for loading screens  
    create_performance_controller,   # Maximum performance, minimal visuals
    create_presentation_controller,  # Enhanced visuals for demos
    create_ci_controller            # CI/CD environments
)

# Standard usage
controller = create_dashboard_controller()
controller.start_animation('loading')
```

### Custom Configuration

```python
from e2e_demo.animation_controller import AnimationController, AnimationConfig

# Create custom configuration
config = AnimationConfig(
    max_fps=2.0,           # 2 frames per second
    enabled=True,          # Enable animations
    smooth_transitions=True, # Smooth state changes
    performance_mode=False  # Full features
)

controller = AnimationController(config)
```

## Configuration Options

### AnimationConfig Parameters

| Parameter | Type | Default | Description | Recommendations |
|-----------|------|---------|-------------|-----------------|
| `max_fps` | float | 4.0 | Maximum frames per second | 1.0-4.0 for terminals |
| `enabled` | bool | True | Enable/disable all animations | False for CI/scripts |
| `smooth_transitions` | bool | True | Enable smooth state changes | False for instant feedback |
| `cpu_threshold` | float | 80.0 | CPU% threshold for degradation | 70-90 based on hardware |
| `performance_mode` | bool | False | Emergency performance mode | True for resource constraints |

### Frame Rate Guidelines

| FPS | Use Case | Performance | Visual Quality | Best For |
|-----|----------|-------------|----------------|----------|
| 1.0 | Minimal | Excellent | Basic | CI/CD, scripts |
| 2.0 | Conservative | Very Good | Good | Loading screens, low-end systems |
| 3.0 | Balanced | Good | Very Good | Presentations, demos |
| 4.0 | Standard | Good | Excellent | Interactive dashboards |
| >4.0 | High | Poor | Diminishing returns | Not recommended for terminals |

## Pre-configured Controllers

### 1. Dashboard Controller (Recommended)

**Use Case:** Standard dashboard displays, real-time monitoring

```python
controller = create_dashboard_controller()

# Configuration:
# - max_fps: 4.0 (smooth updates)
# - smooth_transitions: True (polished appearance) 
# - cpu_threshold: 80.0 (adaptive performance)
# - performance_mode: False (full features)
```

**Best For:**
- Interactive dashboards
- Real-time status monitoring
- Progress tracking displays
- Development environments

### 2. Loading Controller

**Use Case:** Application startup, service initialization

```python
controller = create_loading_controller()

# Configuration:
# - max_fps: 2.0 (slower, less CPU intensive)
# - smooth_transitions: True (smooth progression)
# - performance_mode: False (visual feedback important)
```

**Best For:**
- Application loading sequences
- Service connection progress
- One-time initialization screens
- User onboarding flows

### 3. Performance Controller

**Use Case:** Resource-constrained environments

```python
controller = create_performance_controller()

# Configuration:
# - max_fps: 1.0 (minimal CPU usage)
# - enabled: False (animations disabled)
# - smooth_transitions: False (instant changes)
# - performance_mode: True (maximum efficiency)
```

**Best For:**
- Resource-limited systems
- Battery-powered devices
- High-load scenarios
- Background processing

### 4. Presentation Controller

**Use Case:** Live demonstrations, client showcases

```python
controller = create_presentation_controller()

# Configuration:
# - max_fps: 3.0 (smooth but controlled)
# - smooth_transitions: True (professional appearance)
# - cpu_threshold: 85.0 (higher tolerance for demos)
# - performance_mode: False (visual quality priority)
```

**Best For:**
- Client demonstrations
- Sales presentations
- Marketing showcases
- Training sessions

### 5. CI/CD Controller

**Use Case:** Automated testing, continuous integration

```python
controller = create_ci_controller()

# Configuration:
# - max_fps: 1.0 (minimal resources)
# - enabled: False (no animations in automation)
# - smooth_transitions: False (immediate feedback)
# - performance_mode: True (efficiency priority)
```

**Best For:**
- Automated test suites
- Continuous integration pipelines
- Headless environments
- Batch processing

## Advanced Configuration

### Custom Animation Config

```python
from e2e_demo.animation_controller import AnimationController, AnimationConfig

# High-performance gaming setup (not recommended for terminals)
gaming_config = AnimationConfig(
    max_fps=8.0,              # Very fast (use carefully)
    enabled=True,
    smooth_transitions=True,
    cpu_threshold=95.0,       # High tolerance
    performance_mode=False
)

# Ultra-minimal for embedded systems
embedded_config = AnimationConfig(
    max_fps=0.5,              # Very slow (2 second intervals)
    enabled=False,
    smooth_transitions=False,
    cpu_threshold=50.0,       # Very conservative
    performance_mode=True
)

# Adaptive configuration
adaptive_config = AnimationConfig(
    max_fps=2.0,              # Conservative baseline
    enabled=True,
    smooth_transitions=True,
    cpu_threshold=70.0,       # Early degradation
    performance_mode=False
)
```

### Runtime Configuration Changes

```python
# Start with standard configuration
controller = create_dashboard_controller()

# Monitor performance and adapt
stats = controller.get_performance_stats()
if stats.get('performance_degraded', False):
    # Switch to performance mode
    controller.set_performance_mode(True)
    print("Switched to performance mode due to degradation")

# Check system resources
import psutil
cpu_percent = psutil.cpu_percent(interval=1)
if cpu_percent > 90:
    controller.set_performance_mode(True)
    print(f"High CPU usage ({cpu_percent}%), enabling performance mode")
```

## Performance Monitoring

### Built-in Performance Statistics

```python
# Get comprehensive performance data
stats = controller.get_performance_stats()

print(f"Actual FPS: {stats.get('actual_fps', 0):.1f}")
print(f"Target FPS: {stats.get('target_fps', 0):.1f}") 
print(f"Performance degraded: {stats.get('performance_degraded', False)}")
print(f"Active animations: {stats.get('active_animations', 0)}")
print(f"Average frame time: {stats.get('average_frame_time', 0):.3f}s")
```

### Performance Thresholds

```python
# Set up performance monitoring
def monitor_performance(controller):
    while controller.is_running:
        stats = controller.get_performance_stats()
        
        # Check for performance issues
        if stats.get('actual_fps', 0) < stats.get('target_fps', 0) * 0.5:
            print("⚠️ Performance significantly below target")
            
        if stats.get('performance_degraded', False):
            print("🔻 Performance degradation detected")
            
        # Adaptive response
        if stats.get('average_frame_time', 0) > 0.5:  # 500ms per frame
            controller.set_performance_mode(True)
            print("🚨 Enabling emergency performance mode")
            
        time.sleep(5)  # Check every 5 seconds
```

## Environment-Specific Configurations

### Windows

```python
# Windows Terminal or PowerShell
if platform.system() == 'Windows':
    if os.environ.get('WT_SESSION'):
        # Windows Terminal - full features
        controller = create_dashboard_controller()
    else:
        # Command Prompt - conservative
        controller = create_performance_controller()
```

### macOS

```python
# macOS Terminal or iTerm2
if platform.system() == 'Darwin':
    term_program = os.environ.get('TERM_PROGRAM', '')
    if 'iterm' in term_program.lower():
        # iTerm2 - enhanced features
        controller = create_presentation_controller()
    else:
        # Terminal.app - standard
        controller = create_dashboard_controller()
```

### Linux

```python
# Linux terminal detection
if platform.system() == 'Linux':
    if os.environ.get('GNOME_TERMINAL_SERVICE'):
        # GNOME Terminal
        controller = create_dashboard_controller()
    elif os.environ.get('KONSOLE_VERSION'):
        # KDE Konsole  
        controller = create_dashboard_controller()
    else:
        # Unknown/minimal terminal
        controller = create_loading_controller()
```

### SSH/Remote

```python
# Remote session detection
if os.environ.get('SSH_CLIENT') or os.environ.get('SSH_TTY'):
    # SSH session - conservative settings
    config = AnimationConfig(
        max_fps=1.0,           # Very slow over network
        enabled=True,          # Keep basic animations
        smooth_transitions=False, # Instant changes
        performance_mode=False
    )
    controller = AnimationController(config)
```

## Troubleshooting Performance

### Common Performance Issues

#### High CPU Usage
```python
# Check current CPU impact
import psutil
before_cpu = psutil.cpu_percent(interval=1)

controller = create_dashboard_controller()
controller.start_animation('loading')
time.sleep(5)

after_cpu = psutil.cpu_percent(interval=1)
cpu_impact = after_cpu - before_cpu

if cpu_impact > 10:  # More than 10% CPU increase
    print(f"High CPU impact: {cpu_impact}%")
    controller.set_performance_mode(True)
```

#### Memory Leaks
```python
# Monitor memory usage
import tracemalloc

tracemalloc.start()
controller = create_dashboard_controller()

# Run animations for a while
controller.start_animation('loading')
time.sleep(30)
controller.stop_animation('loading')

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()
```

#### Frame Rate Issues
```python
# Diagnose frame rate problems
controller = create_dashboard_controller()
controller.start_animation('loading')

# Monitor for 10 seconds
start_time = time.time()
while time.time() - start_time < 10:
    stats = controller.get_performance_stats()
    actual_fps = stats.get('actual_fps', 0)
    target_fps = stats.get('target_fps', 4.0)
    
    if actual_fps < target_fps * 0.7:  # 30% below target
        print(f"Frame rate issue: {actual_fps:.1f}/{target_fps:.1f} FPS")
        
    time.sleep(1)

controller.stop_all_animations()
```

## Best Practices

### 1. Choose Appropriate Configuration

```python
# Don't over-configure - use presets
controller = create_dashboard_controller()  # ✅ Good

# Avoid manual configuration unless necessary
config = AnimationConfig(max_fps=4.0, enabled=True)  # ❌ Unnecessary
controller = AnimationController(config)
```

### 2. Monitor Performance in Production

```python
# Include performance monitoring
def setup_monitoring(controller):
    def log_performance():
        stats = controller.get_performance_stats()
        if stats.get('performance_degraded'):
            logging.warning("Animation performance degraded")
    
    # Check every minute
    timer = threading.Timer(60, log_performance)
    timer.daemon = True
    timer.start()
```

### 3. Graceful Degradation

```python
# Always have fallback options
try:
    controller = create_dashboard_controller()
    controller.start_animation('loading')
except Exception as e:
    print(f"Animation failed, falling back: {e}")
    # Continue without animations
    pass
```

### 4. Test Across Environments

```python
# Environment-aware configuration
def create_environment_appropriate_controller():
    if os.environ.get('CI'):
        return create_ci_controller()
    elif 'pytest' in sys.modules:
        return create_performance_controller()
    elif os.environ.get('PRESENTATION_MODE'):
        return create_presentation_controller()
    else:
        return create_dashboard_controller()
```

### 5. Clean Resource Management

```python
# Always use context managers
with create_dashboard_controller() as controller:
    controller.start_animation('loading')
    # Animations automatically cleaned up
```

## Configuration Examples by Use Case

### Interactive Development
```python
# Balanced performance for development
controller = create_dashboard_controller()
```

### Automated Testing
```python  
# No animations, maximum speed
controller = create_ci_controller()
```

### Client Demonstrations
```python
# Enhanced visuals for demos
controller = create_presentation_controller()
```

### Production Monitoring
```python
# Conservative settings for stability
config = AnimationConfig(
    max_fps=2.0,
    enabled=True,
    smooth_transitions=True,
    cpu_threshold=75.0,  # Conservative threshold
    performance_mode=False
)
controller = AnimationController(config)
```

### Low-End Hardware
```python
# Minimal resource usage
controller = create_performance_controller()
```

---

**Note:** The animation system is designed to be adaptive and self-tuning. Start with the pre-configured controllers and only customize when you have specific performance requirements or constraints.