# Inbox Monitor User Guide

Complete operational reference for daily usage, monitoring, and maintenance of the Inbox Monitor system.

> **📚 Related Documentation:**
> - **Getting Started:** [Setup Guide](SETUP.md) - Initial installation and configuration
> - **Configuration:** [Configuration Guide](CONFIGURATION.md) - Service authentication and setup
> - **Understanding the System:** [Scenarios Guide](SCENARIOS.md) - AI email classification and business actions
> - **Testing:** [Testing Guide](TESTING.md) - Validate system operation
> - **Demonstrations:** [Demo Playbook](DEMO_PLAYBOOK.md) - Demo scenarios and presentations
> - **Need Help?** [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Quick Start

```bash
# Run with dashboard (default)
python e2e_demo.py

# Run specific scenario
python e2e_demo.py --scenario 7

# Run with technical details
python e2e_demo.py --technical --timing

# Export results
python e2e_demo.py --format dashboard --export all
```

## Command Line Options

### Basic Options
- `--live` - Use real services (requires confirmation)
- `--scenario N` - Run specific scenario (5-10 built-in, or custom)
- `--format FORMAT` - Output format (dashboard, simple, json, table, markdown)
- `--help` - Show help message

### Output Control
- `--quiet` - Minimal output
- `--verbose` - Show all details
- `--business` - Business-friendly output (default)
- `--technical` - Include technical details
- `--timing` - Show performance metrics
- `--no-color` - Disable colored output

### Configuration
- `--config FILE` - Load configuration from YAML
- `--save-config FILE` - Save current configuration

### Export Options
- `--output FILE` - Save output to file
- `--export FORMAT` - Export format (json, csv, html, markdown, excel, all)

## Creating Custom Scenarios

1. Create a YAML file in `scenarios/` directory
2. Follow the schema (see `scenarios/example_scenario.yaml`)
3. Run with `python e2e_demo.py --scenario YOUR_ID`

### Scenario YAML Format

```yaml
id: 20
name: Your Scenario Name
description: Description of what this tests
category: custom  # support, inquiry, no_longer_works, custom
tags:
  - tag1
  - tag2

email:
  from: sender@example.com
  to: support@company.com
  subject: Email Subject
  body: |
    Email body content
    Can be multi-line

expected_outcome: What should happen

validation:
  required_fields:
    - from
    - subject
  success_criteria:
    - Criteria 1
    - Criteria 2

mock_response:
  delay: 0.5
  success_rate: 0.95
```

## Configuration Files

Create `demo_config.yaml`:
```yaml
mock_mode: true
output_format: dashboard
detail_level: business
show_timing: true
export_format: all
scenarios_dir: scenarios
templates_dir: templates
export_dir: exports
```

Load with: `python e2e_demo.py --config demo_config.yaml`

## Demo Templates

Pre-built templates in `templates/`:
- `executive_demo.yaml` - For executive presentations
- `technical_demo.yaml` - For technical audiences  
- `sales_demo.yaml` - For sales demonstrations

Copy to scenarios directory to use:
```bash
cp templates/executive_demo.yaml scenarios/
python e2e_demo.py --scenario 101
```

## Export and Reporting

### Export Formats
- **JSON** - Machine-readable data
- **CSV** - Spreadsheet compatible
- **HTML** - Professional web report
- **Markdown** - Documentation format
- **Excel** - Enhanced CSV for Excel

### Export Examples
```bash
# Export all formats
python e2e_demo.py --export all

# Export specific format
python e2e_demo.py --export html --output my_results.html

# Export with custom filename
python e2e_demo.py --export json --output custom_report
```

### Report Types
- **Technical Report** - Detailed system metrics
- **Executive Summary** - High-level business metrics
- **Performance Report** - Speed and efficiency metrics

## Advanced Features

### Error Recovery
The system automatically handles:
- Network timeouts
- Service failures  
- Invalid responses
- Rate limiting

### Performance Optimization
- Automatic caching of repeated requests
- Response time monitoring
- Resource usage tracking
- Performance recommendations

### YAML Scenario Loading
- Schema validation
- Error reporting
- Template support
- Bulk loading

## Troubleshooting

### Dashboard Not Displaying
- Check terminal size (minimum 80x24)
- Try `--format simple` as fallback
- Ensure Rich library is installed: `pip install rich`

### Performance Issues
- Use `--timing` to identify bottlenecks
- Check network connectivity for live mode
- Review logs in `exports/logs/`

### YAML Validation Errors
- Check scenario YAML syntax
- Verify required fields are present
- Use example scenarios as templates
- Check validation report output

### Export Problems
- Ensure `exports/` directory is writable
- Check disk space
- Verify export format is supported
- Check file permissions

## Integration Examples

### CI/CD Integration
```bash
# Run and export results for CI
python e2e_demo.py --format json --export json --output ci_results.json

# Check exit code
if [ $? -eq 0 ]; then
    echo "All scenarios passed"
else
    echo "Some scenarios failed"
fi
```

### Automated Reporting
```bash
# Generate daily reports
python e2e_demo.py --export all --output "daily_$(date +%Y%m%d)"

# Generate executive summary
python -c "from e2e_demo.export_system import ExportSystem; ExportSystem().generate_executive_summary(results)"
```

## Best Practices

### Scenario Design
1. Keep scenarios focused on single business case
2. Use realistic email content
3. Include clear expected outcomes
4. Add appropriate tags for filtering

### Demo Presentation
1. Start with dashboard format for visual appeal
2. Use business language for non-technical audiences
3. Show technical details for developers
4. Export reports for follow-up distribution

### Performance Monitoring
1. Run with `--timing` to identify slow operations
2. Monitor cache hit rates
3. Check error recovery effectiveness
4. Review performance recommendations

### Configuration Management
1. Use YAML configs for consistent setups
2. Version control your custom scenarios
3. Document any custom configurations
4. Test configurations before presentations

## API Reference

### Programmatic Usage
```python
from e2e_demo.runner import DemoRunner
from e2e_demo.export_system import ExportSystem

# Run scenarios programmatically
runner = DemoRunner()
results = runner.run_scenario(scenario_id=7)

# Export results
exporter = ExportSystem()
files = exporter.export_results(results, format="all")
```

### Custom Integration
```python
# Custom scenario creation
from e2e_demo.scenarios import Scenario
from e2e_demo.scenario_loader import ScenarioLoader

# Load custom scenarios
loader = ScenarioLoader("my_scenarios")
scenarios = loader.load_all_scenarios()

# Export with custom formatting
exporter = ExportSystem("my_exports")
summary = exporter.generate_executive_summary(results)
```

## Support and Resources

### Documentation
- [Setup Guide](SETUP.md) - Installation and configuration
- [Scenarios Guide](SCENARIOS.md) - Creating and managing scenarios
- [Testing Guide](TESTING.md) - Running tests and validation
- [Configuration Guide](CONFIGURATION.md) - Advanced configuration options

### Getting Help
1. Check the troubleshooting section above
2. Review the example scenarios and templates
3. Check logs in the `exports/logs/` directory
4. Validate YAML syntax using online validators

### Common Use Cases
- **Executive Demos** - Use dashboard format with business outcomes
- **Technical Demos** - Include technical details and performance metrics
- **Sales Presentations** - Focus on business value and ROI
- **Training Sessions** - Use step-by-step technical format
- **Quality Assurance** - Export detailed reports for analysis

## Version Information

E2E Demo System v4.0 - Phase 4 Complete
- ✅ YAML scenario configuration
- ✅ Comprehensive export system
- ✅ Error recovery mechanisms
- ✅ Performance optimization
- ✅ Demo templates
- ✅ Complete documentation