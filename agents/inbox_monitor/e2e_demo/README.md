# E2E Demo Rich UI Integration Guide

## Overview

The E2E Demo Rich UI Integration provides an enterprise-grade dashboard experience for email processing demonstrations. This system transforms verbose logs into an informative, delightful dashboard experience suitable for both technical staff and business users.

## Features

### 🎨 Rich Dashboard Experience
- **Real-time progress tracking** with smooth visual transitions
- **Service status monitoring** with progressive updates (pending → connecting → healthy)
- **Professional business metrics** display with executive summary format
- **Adaptive terminal compatibility** with graceful fallback to simple output

### 🎬 Animation System
- **Smooth animations** at optimized frame rates (1-4 FPS)
- **CPU usage monitoring** with automatic performance degradation
- **Built-in animation sequences** for loading, progress, and service connections
- **Thread-safe operation** with proper resource cleanup

### 📊 Service Monitoring
- **Progressive service health tracking** with real-time metrics
- **Performance assessment** with response time analysis
- **Automatic failure detection** and recovery reporting
- **Business-friendly status reporting**

## Quick Start

### Basic Usage

```bash
# Run with rich dashboard (default in supported terminals)
python e2e_demo.py --format dashboard

# Run specific scenario with dashboard
python e2e_demo.py --format dashboard --scenario 7

# Dry run to preview configuration
python e2e_demo.py --format dashboard --dry-run

# Fallback to simple format if dashboard unsupported
python e2e_demo.py --format simple
```

### Configuration Options

```bash
# Load configuration from file
python e2e_demo.py --config demo_config.yaml --format dashboard

# Business-friendly verbose output
python e2e_demo.py --format dashboard --business --timing

# Save current configuration
python e2e_demo.py --save-config my_config.yaml --format dashboard
```

## Dashboard Components

### 1. Dashboard Integration (`dashboard_integration.py`)

Main integration layer that connects the enterprise dashboard to the demo runner.

```python
from e2e_demo.dashboard_integration import DashboardIntegration
from e2e_demo.config import DemoConfig

# Initialize dashboard
config = DemoConfig(output_format='dashboard')
integration = DashboardIntegration(config)

# Use as async context manager
async with integration:
    # Dashboard automatically starts and stops
    integration.add_message("Demo started", "info")
    
    # Track service operations
    op_id = integration.start_service_operation("ai_foundry", "classify")
    # ... perform operation ...
    integration.complete_service_operation(op_id, success=True)
```

### 2. Animation Controller (`animation_controller.py`)

Manages smooth animations with performance optimization.

```python
from e2e_demo.animation_controller import create_dashboard_controller

# Create optimized controller
controller = create_dashboard_controller()

# Start built-in animations
controller.start_animation('loading')
controller.start_animation('connecting')

# Check animation status
if controller.is_animation_active('loading'):
    print("Loading animation running")

# Monitor performance
stats = controller.get_performance_stats()
print(f"Current FPS: {stats['actual_fps']}")

# Clean shutdown
controller.stop_all_animations()
```

### 3. Service Monitor (`service_monitor.py`)

Comprehensive service health tracking and monitoring.

```python
from e2e_demo.service_monitor import ServiceMonitor

# Create monitor with callback
def status_callback(service_name, duration, success):
    print(f"{service_name}: {duration:.2f}s ({'✅' if success else '❌'})")

monitor = ServiceMonitor(update_callback=status_callback)
monitor.start_monitoring()

# Track operations
op_id = monitor.start_operation("azure_ai", "classification") 
# ... perform work ...
monitor.complete_operation(op_id, success=True)

# Get health summary
health = monitor.get_health_summary()
print(f"Healthy services: {health['healthy_services']}")
```

### 4. Terminal Detector (`terminal_detector.py`)

Intelligent terminal capability detection with graceful fallback.

```python
from e2e_demo.terminal_detector import TerminalDetector

detector = TerminalDetector()

# Check capabilities
caps = detector.get_capabilities()
print(f"Terminal: {caps['terminal']} ({caps['width']}x{caps['height']})")
print(f"Rich support: {caps['rich_support']}")
print(f"Color support: {caps['color_support']}")

# Use in conditional logic
if detector.supports_rich():
    # Use rich dashboard
    pass
else:
    # Fall back to simple output
    pass
```

## Configuration Examples

### Basic Demo Configuration (`demo_config.yaml`)

```yaml
# Dashboard settings
output_format: dashboard
detail_level: business
show_timing: true

# Service settings
mock_mode: true
scenario: null  # Run all scenarios

# Output settings
output_file: null
use_color: true
```

### Advanced Configuration

```yaml
# Performance-optimized configuration
output_format: dashboard
detail_level: technical

# Custom service settings
services:
  azure_ai:
    timeout: 30
    retry_attempts: 3
  salesforce:
    timeout: 15
    retry_attempts: 2

# Terminal optimization
terminal:
  force_rich: false
  min_width: 80
  adaptive_refresh: true
```

## Terminal Compatibility

### Supported Terminals

| Terminal | Rich Support | Unicode | Colors | Performance |
|----------|-------------|---------|--------|-------------|
| VS Code Terminal | ✅ Excellent | ✅ Full | ✅ Full | High |
| Windows Terminal | ✅ Excellent | ✅ Full | ✅ Full | High |
| iTerm2 (macOS) | ✅ Excellent | ✅ Full | ✅ Full | High |
| GNOME Terminal | ✅ Good | ✅ Full | ✅ Full | Medium |
| Git Bash | ❌ Fallback | ⚠️ Limited | ✅ Basic | Low |
| CMD.exe | ❌ Fallback | ❌ None | ⚠️ Limited | Low |

### Automatic Fallback

The system automatically detects terminal capabilities and falls back to appropriate output:

- **Rich Dashboard**: Full-featured dashboard with animations (supported terminals)
- **Simple Output**: Clean text output with colors (basic terminals) 
- **Plain Text**: Minimal output for CI/CD or non-interactive environments

## Performance Optimization

### Adaptive Refresh Rates

The dashboard automatically adjusts refresh rates based on terminal capabilities:

- **CI/CD environments**: 1 FPS (minimal CPU usage)
- **Small terminals (< 80 chars)**: 1 FPS (reduced complexity)
- **Normal terminals (80-120 chars)**: 2 FPS (balanced performance)
- **Wide terminals (> 120 chars)**: 3 FPS (enhanced experience)

### CPU Usage Monitoring

The animation controller monitors CPU usage and automatically:

- **Reduces frame rate** when performance degradation detected
- **Disables animations** in performance mode
- **Uses longer update intervals** to reduce CPU spinning
- **Provides performance statistics** for monitoring

## Error Handling

### Graceful Degradation

The system handles errors gracefully:

```python
# BrokenPipeError handling (output redirection)
python e2e_demo.py --format dashboard | head -5  # Works correctly

# Terminal detection failures
export TERM=dumb  # Falls back to simple output

# Rich library missing
pip uninstall rich  # Falls back to simple formatting
```

### Error Recovery

Multi-layer error boundaries ensure:

- **Dashboard failures** don't stop scenario execution
- **Animation errors** don't crash the application  
- **Service monitoring failures** don't affect core functionality
- **Display corruption** triggers automatic recovery

## Advanced Usage

### Custom Service Integration

```python
from e2e_demo.dashboard_integration import DashboardIntegration
from e2e_demo.service_monitor import ServiceMonitor

# Custom service callback
def my_service_callback(service_name, duration, success):
    if not success:
        print(f"⚠️ Service {service_name} failed after {duration:.1f}s")
    
# Integrate with existing code
integration = DashboardIntegration(config)
integration.service_monitor.update_callback = my_service_callback
```

### Performance Monitoring

```python
from e2e_demo.animation_controller import create_dashboard_controller

controller = create_dashboard_controller()

# Monitor performance in real-time
while True:
    stats = controller.get_performance_stats()
    if stats['performance_degraded']:
        print("Performance degradation detected!")
        controller.set_performance_mode(True)  # Disable animations
    time.sleep(1)
```

### Custom Animation Sequences

```python
from e2e_demo.animation_controller import AnimationController, AnimationSequence, AnimationFrame

controller = AnimationController()

# Create custom animation
frames = [
    AnimationFrame("🔍 Searching", 0.3),
    AnimationFrame("🔍 Searching.", 0.3), 
    AnimationFrame("🔍 Searching..", 0.3),
    AnimationFrame("🔍 Searching...", 0.3)
]

search_animation = AnimationSequence("searching", frames)
search_animation.loop = True

controller.register_animation("searching", search_animation)
controller.start_animation("searching")
```

## Troubleshooting

### Common Issues

**Dashboard not appearing:**
- Check terminal compatibility with `--format simple`
- Verify Rich library installed: `pip install rich>=13.0.0`
- Check terminal size: minimum 80x20 required

**Performance issues:**
- Use `--format simple` for better performance
- Check CPU usage with performance stats
- Reduce terminal size to trigger slower refresh rates

**Output corruption:**
- Try `reset` command to clear terminal
- Use `--format simple` as fallback
- Check for terminal-specific issues

**BrokenPipeError:**
- Normal when piping output: `python e2e_demo.py | head`
- Application handles gracefully and continues
- Use `--format simple` for scripting scenarios

### Debug Mode

Enable verbose output for troubleshooting:

```bash
# Enable debug logging
python e2e_demo.py --format dashboard --detail-level verbose

# Check component status
python -c "
from e2e_demo.terminal_detector import TerminalDetector
detector = TerminalDetector()
print(detector.get_capabilities())
"
```

## Contributing

When extending the dashboard system:

1. **Follow existing patterns**: Use async context managers and error boundaries
2. **Add comprehensive error handling**: Every component should fail gracefully
3. **Include performance considerations**: Monitor CPU and memory usage
4. **Test terminal compatibility**: Verify behavior across different terminals
5. **Document new features**: Update this guide with usage examples

## API Reference

### DashboardIntegration

- `start()` / `stop()`: Lifecycle management
- `add_message(message, level)`: Add dashboard messages
- `start_service_operation(service, operation)`: Track service operations
- `update_phase(phase)`: Update execution phase

### AnimationController  

- `start_animation(name)` / `stop_animation(name)`: Control animations
- `get_performance_stats()`: Monitor performance
- `set_performance_mode(enabled)`: Toggle performance mode

### ServiceMonitor

- `start_operation(service, type)`: Begin operation tracking
- `complete_operation(id, success)`: Complete operation
- `get_health_summary()`: Get system health overview

### TerminalDetector

- `supports_rich()`: Check Rich library compatibility
- `get_capabilities()`: Get full capability assessment
- `is_ci_environment()`: Detect CI/CD environments

---

*For more detailed API documentation, see the docstrings in each module.*