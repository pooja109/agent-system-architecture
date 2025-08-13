"""
Export Utilities for Test Runner CLI
====================================

Provides comprehensive export functionality for multiple output formats.
"""

import json
import csv
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
import base64

try:
    from .test_execution import TestResult
except ImportError:
    from test_execution import TestResult
try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode

class ExportFormat:
    """Supported export formats."""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    HTML = "html"
    JUNIT = "junit"
    TAP = "tap"
    YAML = "yaml"
    MARKDOWN = "md"
    PDF = "pdf"

class ExportUtilities:
    """Comprehensive export utilities for test results and data."""
    
    def __init__(self):
        self.supported_formats = [
            ExportFormat.JSON,
            ExportFormat.XML,
            ExportFormat.CSV,
            ExportFormat.HTML,
            ExportFormat.JUNIT,
            ExportFormat.TAP,
            ExportFormat.YAML,
            "markdown",
            ExportFormat.PDF
        ]
    
    def export_test_results(self, result: TestResult, output_path: Path, 
                          format_type: str, options: Optional[Dict[str, Any]] = None) -> bool:
        """Export test results in specified format."""
        try:
            options = options or {}
            
            # Ensure output directory exists
            output_path.parent.mkdir(exist_ok=True, parents=True)
            
            if format_type == ExportFormat.JSON:
                return self._export_json(result, output_path, options)
            elif format_type == ExportFormat.XML:
                return self._export_xml(result, output_path, options)
            elif format_type == ExportFormat.CSV:
                return self._export_csv(result, output_path, options)
            elif format_type == ExportFormat.HTML:
                return self._export_html(result, output_path, options)
            elif format_type == ExportFormat.JUNIT:
                return self._export_junit(result, output_path, options)
            elif format_type == ExportFormat.TAP:
                return self._export_tap(result, output_path, options)
            elif format_type == ExportFormat.YAML:
                return self._export_yaml(result, output_path, options)
            elif format_type == ExportFormat.MARKDOWN or format_type == "markdown":
                return self._export_markdown(result, output_path, options)
            elif format_type == ExportFormat.PDF:
                return self._export_pdf(result, output_path, options)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            print(f"Error exporting to {format_type}: {e}")
            return False
    
    def _export_json(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as JSON."""
        data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'format': 'json',
                'version': '1.0'
            },
            'execution': {
                'mode': result.execution_mode.value,
                'command': result.command_executed,
                'start_time': getattr(result, 'start_time', None),
                'end_time': getattr(result, 'end_time', None),
                'duration': result.total_execution_time,
                'return_code': result.return_code
            },
            'summary': {
                'total_tests': result.total_tests,
                'passed': result.passed_tests,
                'failed': result.failed_tests,
                'skipped': result.skipped_tests,
                'errors': result.error_tests,
                'success_rate': result.success_rate
            },
            'test_details': {
                'individual_times': result.individual_test_times,
                'failures': result.failure_details,
                'output_lines': result.output_lines if options.get('include_output', False) else []
            }
        }
        
        # Add pretty printing option
        indent = 2 if options.get('pretty', True) else None
        
        output_path.write_text(json.dumps(data, indent=indent, ensure_ascii=False))
        return True
    
    def _export_xml(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as XML."""
        root = ET.Element('test_results')
        
        # Metadata
        metadata = ET.SubElement(root, 'metadata')
        ET.SubElement(metadata, 'export_timestamp').text = datetime.now().isoformat()
        ET.SubElement(metadata, 'format').text = 'xml'
        ET.SubElement(metadata, 'version').text = '1.0'
        
        # Execution info
        execution = ET.SubElement(root, 'execution')
        ET.SubElement(execution, 'mode').text = result.execution_mode.value
        ET.SubElement(execution, 'duration').text = str(result.total_execution_time)
        ET.SubElement(execution, 'return_code').text = str(result.return_code)
        
        command = ET.SubElement(execution, 'command')
        for arg in result.command_executed:
            ET.SubElement(command, 'arg').text = arg
        
        # Summary
        summary = ET.SubElement(root, 'summary')
        ET.SubElement(summary, 'total_tests').text = str(result.total_tests)
        ET.SubElement(summary, 'passed').text = str(result.passed_tests)
        ET.SubElement(summary, 'failed').text = str(result.failed_tests)
        ET.SubElement(summary, 'skipped').text = str(result.skipped_tests)
        ET.SubElement(summary, 'errors').text = str(result.error_tests)
        ET.SubElement(summary, 'success_rate').text = str(result.success_rate)
        
        # Individual test results
        if result.individual_test_times or result.failure_details:
            tests = ET.SubElement(root, 'tests')
            
            # Combine timing and failure data
            all_tests = set(result.individual_test_times.keys()) | set(result.failure_details)
            
            for test_name in sorted(all_tests):
                test_elem = ET.SubElement(tests, 'test')
                ET.SubElement(test_elem, 'name').text = test_name
                
                if test_name in result.individual_test_times:
                    ET.SubElement(test_elem, 'duration').text = str(result.individual_test_times[test_name])
                
                if test_name in result.failure_details:
                    ET.SubElement(test_elem, 'status').text = 'failed'
                    ET.SubElement(test_elem, 'failure_message').text = test_name  # Simplified
                else:
                    ET.SubElement(test_elem, 'status').text = 'passed'
        
        # Write XML with pretty formatting
        if options.get('pretty', True):
            self._prettify_xml(root)
        
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        return True
    
    def _export_csv(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as CSV."""
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write summary section
            writer.writerow(['Section', 'Metric', 'Value'])
            writer.writerow(['Summary', 'Execution Mode', result.execution_mode.value])
            writer.writerow(['Summary', 'Total Tests', result.total_tests])
            writer.writerow(['Summary', 'Passed Tests', result.passed_tests])
            writer.writerow(['Summary', 'Failed Tests', result.failed_tests])
            writer.writerow(['Summary', 'Skipped Tests', result.skipped_tests])
            writer.writerow(['Summary', 'Error Tests', result.error_tests])
            writer.writerow(['Summary', 'Success Rate', f"{result.success_rate:.2f}%"])
            writer.writerow(['Summary', 'Execution Time', f"{result.total_execution_time:.2f}s"])
            writer.writerow([])  # Empty row
            
            # Write individual test results if available
            if result.individual_test_times:
                writer.writerow(['Test Name', 'Duration (seconds)', 'Status'])
                for test_name, duration in sorted(result.individual_test_times.items()):
                    status = 'FAILED' if test_name in result.failure_details else 'PASSED'
                    writer.writerow([test_name, f"{duration:.3f}", status])
        
        return True
    
    def _export_html(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as HTML."""
        title = options.get('title', 'Test Results Report')
        include_charts = options.get('include_charts', True)
        
        html_content = self._generate_html_report(result, title, include_charts)
        output_path.write_text(html_content, encoding='utf-8')
        return True
    
    def _export_junit(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results in JUnit XML format."""
        root = ET.Element('testsuites')
        root.set('name', 'test_runner')
        root.set('tests', str(result.total_tests))
        root.set('failures', str(result.failed_tests))
        root.set('errors', str(result.error_tests))
        root.set('skipped', str(result.skipped_tests))
        root.set('time', str(result.total_execution_time))
        root.set('timestamp', datetime.now().isoformat())
        
        testsuite = ET.SubElement(root, 'testsuite')
        testsuite.set('name', result.execution_mode.value)
        testsuite.set('tests', str(result.total_tests))
        testsuite.set('failures', str(result.failed_tests))
        testsuite.set('errors', str(result.error_tests))
        testsuite.set('skipped', str(result.skipped_tests))
        testsuite.set('time', str(result.total_execution_time))
        
        # Add individual test cases
        all_tests = set(result.individual_test_times.keys())
        if result.failure_details:
            # Extract test names from failure details (simplified)
            for failure in result.failure_details:
                if '::' in failure:
                    test_name = failure.split('::')[0] + '::' + failure.split('::')[1]
                    all_tests.add(test_name)
        
        for test_name in sorted(all_tests):
            testcase = ET.SubElement(testsuite, 'testcase')
            testcase.set('name', test_name)
            testcase.set('classname', test_name.split('::')[0] if '::' in test_name else 'unknown')
            
            if test_name in result.individual_test_times:
                testcase.set('time', str(result.individual_test_times[test_name]))
            
            # Check if test failed
            if any(test_name in failure for failure in result.failure_details):
                failure_elem = ET.SubElement(testcase, 'failure')
                failure_elem.set('type', 'TestFailure')
                failure_msg = next((f for f in result.failure_details if test_name in f), '')
                failure_elem.text = failure_msg
        
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        return True
    
    def _export_tap(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results in TAP (Test Anything Protocol) format."""
        lines = []
        
        # TAP version
        lines.append("TAP version 13")
        
        # Plan
        lines.append(f"1..{result.total_tests}")
        
        # Individual test results
        test_number = 1
        
        # Process tests with known results first
        for test_name in sorted(result.individual_test_times.keys()):
            duration = result.individual_test_times[test_name]
            is_failure = any(test_name in failure for failure in result.failure_details)
            
            status = "not ok" if is_failure else "ok"
            lines.append(f"{status} {test_number} - {test_name}")
            
            # Add diagnostic info
            lines.append(f"  ---")
            lines.append(f"  duration: {duration:.3f}")
            if is_failure:
                failure_msg = next((f for f in result.failure_details if test_name in f), '')
                lines.append(f"  message: {failure_msg}")
            lines.append(f"  ...")
            
            test_number += 1
        
        # Add any remaining tests (if total > individual times)
        while test_number <= result.total_tests:
            lines.append(f"ok {test_number} - unknown_test_{test_number}")
            test_number += 1
        
        # Summary comment
        lines.append(f"# Tests: {result.total_tests}, Passed: {result.passed_tests}, "
                    f"Failed: {result.failed_tests}, Skipped: {result.skipped_tests}")
        lines.append(f"# Execution time: {result.total_execution_time:.2f}s")
        
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        return True
    
    def _export_yaml(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as YAML."""
        try:
            import yaml
        except ImportError:
            # Fallback to manual YAML-like format
            return self._export_yaml_manual(result, output_path, options)
        
        data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'format': 'yaml',
                'version': '1.0'
            },
            'execution': {
                'mode': result.execution_mode.value,
                'command': result.command_executed,
                'duration': result.total_execution_time,
                'return_code': result.return_code
            },
            'summary': {
                'total_tests': result.total_tests,
                'passed': result.passed_tests,
                'failed': result.failed_tests,
                'skipped': result.skipped_tests,
                'errors': result.error_tests,
                'success_rate': result.success_rate
            },
            'test_details': {
                'individual_times': result.individual_test_times,
                'failures': result.failure_details
            }
        }
        
        output_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        return True
    
    def _export_yaml_manual(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as YAML without yaml library."""
        lines = []
        
        # Metadata
        lines.append("metadata:")
        lines.append(f"  export_timestamp: '{datetime.now().isoformat()}'")
        lines.append("  format: 'yaml'")
        lines.append("  version: '1.0'")
        lines.append("")
        
        # Execution
        lines.append("execution:")
        lines.append(f"  mode: '{result.execution_mode.value}'")
        lines.append("  command:")
        for arg in result.command_executed:
            lines.append(f"    - '{arg}'")
        lines.append(f"  duration: {result.total_execution_time}")
        lines.append(f"  return_code: {result.return_code}")
        lines.append("")
        
        # Summary
        lines.append("summary:")
        lines.append(f"  total_tests: {result.total_tests}")
        lines.append(f"  passed: {result.passed_tests}")
        lines.append(f"  failed: {result.failed_tests}")
        lines.append(f"  skipped: {result.skipped_tests}")
        lines.append(f"  errors: {result.error_tests}")
        lines.append(f"  success_rate: {result.success_rate}")
        lines.append("")
        
        # Test details
        if result.individual_test_times:
            lines.append("individual_times:")
            for test_name, duration in sorted(result.individual_test_times.items()):
                lines.append(f"  '{test_name}': {duration}")
        
        if result.failure_details:
            lines.append("failures:")
            for failure in result.failure_details:
                lines.append(f"  - '{failure}'")
        
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        return True
    
    def _export_markdown(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as Markdown."""
        lines = []
        
        # Title
        title = options.get('title', 'Test Results Report')
        lines.append(f"# {title}")
        lines.append("")
        
        # Metadata
        lines.append("## Execution Details")
        lines.append("")
        lines.append(f"- **Mode**: {result.execution_mode.value}")
        lines.append(f"- **Duration**: {result.total_execution_time:.2f} seconds")
        lines.append(f"- **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Command**: `{' '.join(result.command_executed)}`")
        lines.append("")
        
        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Tests | {result.total_tests} |")
        lines.append(f"| Passed | ✅ {result.passed_tests} |")
        lines.append(f"| Failed | ❌ {result.failed_tests} |")
        lines.append(f"| Skipped | ⏭️ {result.skipped_tests} |")
        lines.append(f"| Errors | ⚠️ {result.error_tests} |")
        lines.append(f"| Success Rate | {result.success_rate:.1f}% |")
        lines.append("")
        
        # Performance details
        if result.individual_test_times:
            times = list(result.individual_test_times.values())
            avg_time = sum(times) / len(times)
            slowest = max(times)
            fastest = min(times)
            
            lines.append("## Performance Metrics")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Average Test Time | {avg_time:.3f}s |")
            lines.append(f"| Slowest Test | {slowest:.3f}s |")
            lines.append(f"| Fastest Test | {fastest:.3f}s |")
            lines.append("")
            
            # Slowest tests table
            slowest_tests = sorted(result.individual_test_times.items(), key=lambda x: x[1], reverse=True)[:10]
            if slowest_tests:
                lines.append("### Slowest Tests")
                lines.append("")
                lines.append("| Test Name | Duration |")
                lines.append("|-----------|----------|")
                for test_name, duration in slowest_tests:
                    lines.append(f"| `{test_name}` | {duration:.3f}s |")
                lines.append("")
        
        # Failures
        if result.failure_details:
            lines.append("## Failures")
            lines.append("")
            for i, failure in enumerate(result.failure_details, 1):
                lines.append(f"### Failure {i}")
                lines.append("")
                lines.append(f"```")
                lines.append(failure)
                lines.append(f"```")
                lines.append("")
        
        # Success/Failure indicator
        if result.success_rate == 100.0:
            lines.append("## Result: ✅ SUCCESS")
        elif result.success_rate >= 80.0:
            lines.append("## Result: ⚠️ PARTIAL SUCCESS")
        else:
            lines.append("## Result: ❌ FAILURE")
        
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        return True
    
    def _export_pdf(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export results as PDF using HTML-to-PDF conversion."""
        try:
            # Try importing PDF generation libraries
            try:
                from weasyprint import HTML, CSS
                pdf_library = 'weasyprint'
            except ImportError:
                try:
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter, A4
                    from reportlab.lib.styles import getSampleStyleSheet
                    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                    from reportlab.lib import colors
                    from reportlab.lib.units import inch
                    pdf_library = 'reportlab'
                except ImportError:
                    print("❌ PDF generation requires either 'weasyprint' or 'reportlab' package")
                    print("   Install with: pip install weasyprint")
                    print("   Or install: pip install reportlab")
                    return False
            
            if pdf_library == 'weasyprint':
                return self._export_pdf_weasyprint(result, output_path, options)
            else:
                return self._export_pdf_reportlab(result, output_path, options)
                
        except Exception as e:
            print(f"Error generating PDF report: {e}")
            return False
    
    def _export_pdf_weasyprint(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export PDF using WeasyPrint (HTML to PDF)."""
        from weasyprint import HTML, CSS
        
        # Generate HTML content for PDF
        html_content = self._generate_pdf_html_content(result, options)
        
        # Create CSS for PDF styling
        css_content = '''
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
            h2 { color: #555; margin-top: 30px; }
            .summary-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            .summary-table th, .summary-table td { 
                border: 1px solid #ddd; padding: 12px; text-align: left; 
            }
            .summary-table th { background-color: #f5f5f5; }
            .passed { color: #4CAF50; font-weight: bold; }
            .failed { color: #f44336; font-weight: bold; }
            .skipped { color: #ff9800; font-weight: bold; }
            .metric { margin: 10px 0; }
            .failure-item { 
                background: #ffebee; border-left: 4px solid #f44336; 
                padding: 10px; margin: 5px 0; 
            }
            @page { margin: 1in; }
            .page-break { page-break-before: always; }
        '''
        
        # Generate PDF
        html_doc = HTML(string=html_content)
        css_doc = CSS(string=css_content)
        html_doc.write_pdf(str(output_path), stylesheets=[css_doc])
        
        return True
    
    def _export_pdf_reportlab(self, result: TestResult, output_path: Path, options: Dict[str, Any]) -> bool:
        """Export PDF using ReportLab (native PDF generation)."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        
        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20
        )
        
        # Title
        title = options.get('title', f'Test Results Report - {result.execution_mode.value.title()} Mode')
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # Execution details
        story.append(Paragraph("Execution Details", heading_style))
        
        exec_data = [
            ['Mode', result.execution_mode.value],
            ['Duration', f'{result.total_execution_time:.2f} seconds'],
            ['Timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Return Code', str(result.return_code)]
        ]
        
        exec_table = Table(exec_data, colWidths=[2*inch, 4*inch])
        exec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(exec_table)
        story.append(Spacer(1, 20))
        
        # Test summary
        story.append(Paragraph("Test Summary", heading_style))
        
        summary_data = [
            ['Metric', 'Count', 'Percentage'],
            ['Total Tests', str(result.total_tests), '100.0%'],
            ['Passed', str(result.passed_tests), f'{(result.passed_tests/result.total_tests*100):.1f}%' if result.total_tests > 0 else '0.0%'],
            ['Failed', str(result.failed_tests), f'{(result.failed_tests/result.total_tests*100):.1f}%' if result.total_tests > 0 else '0.0%'],
            ['Skipped', str(result.skipped_tests), f'{(result.skipped_tests/result.total_tests*100):.1f}%' if result.total_tests > 0 else '0.0%'],
            ['Errors', str(result.error_tests), f'{(result.error_tests/result.total_tests*100):.1f}%' if result.total_tests > 0 else '0.0%']
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Performance metrics
        if result.individual_test_times:
            story.append(Paragraph("Performance Analysis", heading_style))
            
            times = list(result.individual_test_times.values())
            avg_time = sum(times) / len(times) if times else 0
            slowest = max(times) if times else 0
            fastest = min(times) if times else 0
            
            perf_data = [
                ['Average Test Time', f'{avg_time:.3f} seconds'],
                ['Slowest Test', f'{slowest:.3f} seconds'],
                ['Fastest Test', f'{fastest:.3f} seconds'],
                ['Total Individual Tests', str(len(times))]
            ]
            
            perf_table = Table(perf_data, colWidths=[2.5*inch, 2*inch])
            perf_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(perf_table)
            story.append(Spacer(1, 20))
            
            # Top 10 slowest tests
            slowest_tests = sorted(result.individual_test_times.items(), key=lambda x: x[1], reverse=True)[:10]
            if slowest_tests:
                story.append(Paragraph("Slowest Tests (Top 10)", heading_style))
                
                slowest_data = [['Test Name', 'Duration (seconds)']]
                for test_name, duration in slowest_tests:
                    # Truncate very long test names
                    display_name = test_name if len(test_name) <= 60 else test_name[:57] + "..."
                    slowest_data.append([display_name, f'{duration:.3f}'])
                
                slowest_table = Table(slowest_data, colWidths=[4*inch, 1.5*inch])
                slowest_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(slowest_table)
        
        # Failure details
        if result.failure_details:
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"Failure Details ({len(result.failure_details)} failures)", heading_style))
            
            for i, failure in enumerate(result.failure_details[:20]):  # Limit to first 20 failures
                failure_text = failure if len(failure) <= 150 else failure[:147] + "..."
                story.append(Paragraph(f"{i+1}. {failure_text}", styles['Normal']))
                story.append(Spacer(1, 6))
        
        # Build PDF
        doc.build(story)
        return True
    
    def _generate_pdf_html_content(self, result: TestResult, options: Dict[str, Any]) -> str:
        """Generate HTML content optimized for PDF conversion."""
        title = options.get('title', f'Test Results Report - {result.execution_mode.value.title()} Mode')
        
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
        </head>
        <body>
            <h1>{title}</h1>
            
            <h2>Execution Details</h2>
            <table class="summary-table">
                <tr><th>Mode</th><td>{result.execution_mode.value}</td></tr>
                <tr><th>Duration</th><td>{result.total_execution_time:.2f} seconds</td></tr>
                <tr><th>Timestamp</th><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                <tr><th>Return Code</th><td>{result.return_code}</td></tr>
            </table>
            
            <h2>Test Summary</h2>
            <table class="summary-table">
                <tr>
                    <th>Metric</th>
                    <th>Count</th>
                    <th>Percentage</th>
                </tr>
                <tr>
                    <td>Total Tests</td>
                    <td>{result.total_tests}</td>
                    <td>100.0%</td>
                </tr>
                <tr>
                    <td>Passed</td>
                    <td class="passed">{result.passed_tests}</td>
                    <td>{(result.passed_tests/result.total_tests*100):.1f}%</td>
                </tr>
                <tr>
                    <td>Failed</td>
                    <td class="failed">{result.failed_tests}</td>
                    <td>{(result.failed_tests/result.total_tests*100):.1f}%</td>
                </tr>
                <tr>
                    <td>Skipped</td>
                    <td class="skipped">{result.skipped_tests}</td>
                    <td>{(result.skipped_tests/result.total_tests*100):.1f}%</td>
                </tr>
                <tr>
                    <td>Errors</td>
                    <td class="failed">{result.error_tests}</td>
                    <td>{(result.error_tests/result.total_tests*100):.1f}%</td>
                </tr>
            </table>
        '''
        
        # Add performance section if data available
        if result.individual_test_times:
            times = list(result.individual_test_times.values())
            avg_time = sum(times) / len(times) if times else 0
            slowest = max(times) if times else 0
            fastest = min(times) if times else 0
            
            html_content += f'''
            <div class="page-break"></div>
            <h2>Performance Analysis</h2>
            <div class="metric">Average Test Time: <strong>{avg_time:.3f} seconds</strong></div>
            <div class="metric">Slowest Test: <strong>{slowest:.3f} seconds</strong></div>
            <div class="metric">Fastest Test: <strong>{fastest:.3f} seconds</strong></div>
            
            <h3>Slowest Tests (Top 10)</h3>
            <table class="summary-table">
                <tr><th>Test Name</th><th>Duration (seconds)</th></tr>
            '''
            
            slowest_tests = sorted(result.individual_test_times.items(), key=lambda x: x[1], reverse=True)[:10]
            for test_name, duration in slowest_tests:
                display_name = test_name if len(test_name) <= 80 else test_name[:77] + "..."
                html_content += f'<tr><td>{display_name}</td><td>{duration:.3f}</td></tr>'
            
            html_content += '</table>'
        
        # Add failure details
        if result.failure_details:
            html_content += '''
            <div class="page-break"></div>
            <h2>Failure Details</h2>
            '''
            
            for i, failure in enumerate(result.failure_details[:25]):  # Limit failures for PDF
                failure_text = failure if len(failure) <= 200 else failure[:197] + "..."
                html_content += f'<div class="failure-item">{i+1}. {failure_text}</div>'
        
        html_content += '''
            </body>
        </html>
        '''
        
        return html_content
    
    def _generate_html_report(self, result: TestResult, title: str, include_charts: bool) -> str:
        """Generate comprehensive interactive HTML report."""
        return self._generate_interactive_html_report(result, title, include_charts)
    
    def _generate_interactive_html_report(self, result: TestResult, title: str, include_charts: bool) -> str:
        """Generate interactive HTML report with JavaScript drill-down capabilities."""
        
        # Generate test data for JavaScript
        test_data = self._prepare_test_data_for_js(result)
        
        template = '''<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f8fafc; color: #1a202c; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        
        /* Interactive Navigation */
        .nav-tabs {{ display: flex; gap: 10px; margin: 20px 0; border-bottom: 2px solid #e2e8f0; }}
        .nav-tab {{ padding: 12px 24px; background: #f7fafc; border: none; border-radius: 8px 8px 0 0; cursor: pointer; font-weight: 500; transition: all 0.2s; }}
        .nav-tab.active {{ background: #4299e1; color: white; }}
        .nav-tab:hover {{ background: #e2e8f0; }}
        .nav-tab.active:hover {{ background: #3182ce; }}
        
        /* Tab Content */
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        
        /* Metrics Cards */
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: white; padding: 24px; border-radius: 12px; text-align: center; border-left: 4px solid #4299e1; box-shadow: 0 2px 4px rgba(0,0,0,0.05); transition: transform 0.2s; }}
        .metric:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .metric.success {{ border-left-color: #48bb78; }}
        .metric.warning {{ border-left-color: #ed8936; }}
        .metric.danger {{ border-left-color: #f56565; }}
        .metric h3 {{ margin: 0 0 12px 0; color: #4a5568; font-size: 14px; text-transform: uppercase; font-weight: 600; }}
        .metric .value {{ font-size: 32px; font-weight: 700; color: #4299e1; }}
        .metric.success .value {{ color: #48bb78; }}
        .metric.warning .value {{ color: #ed8936; }}
        .metric.danger .value {{ color: #f56565; }}
        
        /* Interactive Tables */
        .table-container {{ background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .table-header {{ padding: 20px; background: #f7fafc; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: between; align-items: center; }}
        .table-controls {{ display: flex; gap: 10px; align-items: center; }}
        .search-box {{ padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; min-width: 200px; }}
        .filter-select {{ padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; }}
        
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f7fafc; font-weight: 600; color: #4a5568; cursor: pointer; user-select: none; }}
        th:hover {{ background: #edf2f7; }}
        tr:hover {{ background: #f7fafc; }}
        
        /* Expandable Rows */
        .expandable-row {{ cursor: pointer; }}
        .expandable-row:hover {{ background: #f0f4f8; }}
        .expand-icon {{ transition: transform 0.2s; }}
        .expand-icon.expanded {{ transform: rotate(90deg); }}
        .detail-row {{ display: none; background: #f8fafc; }}
        .detail-row.show {{ display: table-row; }}
        .detail-content {{ padding: 20px; border-left: 4px solid #4299e1; }}
        
        /* Status Indicators */
        .status-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
        .status-passed {{ background: #c6f6d5; color: #22543d; }}
        .status-failed {{ background: #fed7d7; color: #742a2a; }}
        .status-skipped {{ background: #feebc8; color: #7b341e; }}
        .status-error {{ background: #fed7d7; color: #742a2a; }}
        
        /* Charts Container */
        .chart-container {{ background: white; border-radius: 12px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        
        /* Failure Details */
        .failure-item {{ background: white; border-left: 4px solid #f56565; padding: 20px; margin: 12px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .failure-header {{ font-weight: 600; color: #742a2a; margin-bottom: 12px; cursor: pointer; }}
        .failure-details {{ font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; background: #f7fafc; padding: 15px; border-radius: 6px; overflow-x: auto; display: none; }}
        .failure-details.show {{ display: block; }}
        
        /* Utility Classes */
        .hidden {{ display: none !important; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #2d3748; margin-bottom: 20px; }}
        .timestamp {{ color: #718096; font-size: 14px; }}
        .command {{ background: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 6px; font-family: 'Monaco', 'Menlo', monospace; margin: 10px 0; overflow-x: auto; }}
        
        /* Responsive Design */
        @media (max-width: 768px) {{
            .container {{ padding: 10px; }}
            .metrics {{ grid-template-columns: 1fr; }}
            .nav-tabs {{ flex-wrap: wrap; }}
            .table-controls {{ flex-direction: column; gap: 10px; }}
            .search-box {{ min-width: unset; width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="timestamp">Generated: {timestamp}</div>
        </div>
        
        <!-- Interactive Navigation -->
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showTab('overview')">📊 Overview</button>
            <button class="nav-tab" onclick="showTab('performance')">⚡ Performance</button>
            <button class="nav-tab" onclick="showTab('failures')">❌ Failures</button>
            <button class="nav-tab" onclick="showTab('details')">🔍 Details</button>
        </div>
        
        <!-- Overview Tab -->
        <div id="overview" class="tab-content active">
            <div class="section">
                <h2>Execution Summary</h2>
                <p><strong>Mode:</strong> {mode}</p>
                <p><strong>Duration:</strong> {duration:.2f} seconds</p>
                <div class="command"><strong>Command:</strong> {command}</div>
            </div>
            
            <div class="metrics">
                <div class="metric">
                    <h3>Total Tests</h3>
                    <div class="value">{total_tests}</div>
                </div>
                <div class="metric success">
                    <h3>Passed</h3>
                    <div class="value">{passed_tests}</div>
                </div>
                <div class="metric danger">
                    <h3>Failed</h3>
                    <div class="value">{failed_tests}</div>
                </div>
                <div class="metric warning">
                    <h3>Skipped</h3>
                    <div class="value">{skipped_tests}</div>
                </div>
                <div class="metric {success_class}">
                    <h3>Success Rate</h3>
                    <div class="value">{success_rate:.1f}%</div>
                </div>
            </div>
            
            {overview_charts}
        </div>
        
        <!-- Performance Tab -->
        <div id="performance" class="tab-content">
            {performance_content}
        </div>
        
        <!-- Failures Tab -->
        <div id="failures" class="tab-content">
            {failures_content}
        </div>
        
        <!-- Details Tab -->
        <div id="details" class="tab-content">
            {details_content}
        </div>
    </div>
    
    <script>
        // Test data for JavaScript processing
        const testData = {test_data_js};
        
        // Tab Management
        function showTab(tabName) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});
            document.querySelectorAll('.nav-tab').forEach(tab => {{
                tab.classList.remove('active');
            }});
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
        }}
        
        // Interactive Table Functionality
        function initializeTables() {{
            // Table sorting
            document.querySelectorAll('th[data-sort]').forEach(header => {{
                header.addEventListener('click', () => sortTable(header));
            }});
            
            // Search functionality
            document.querySelectorAll('.search-box').forEach(searchBox => {{
                searchBox.addEventListener('input', (e) => {{
                    filterTable(e.target.closest('.table-container').querySelector('table'), e.target.value);
                }});
            }});
            
            // Expandable rows
            document.querySelectorAll('.expandable-row').forEach(row => {{
                row.addEventListener('click', () => toggleRowDetails(row));
            }});
        }}
        
        function sortTable(header) {{
            const table = header.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr:not(.detail-row)'));
            const columnIndex = Array.from(header.parentNode.children).indexOf(header);
            const isNumeric = header.dataset.sort === 'numeric';
            const isCurrentlyAsc = header.classList.contains('sort-asc');
            
            // Remove existing sort classes
            header.parentNode.querySelectorAll('th').forEach(th => {{
                th.classList.remove('sort-asc', 'sort-desc');
            }});
            
            // Sort rows
            rows.sort((a, b) => {{
                const aVal = a.cells[columnIndex].textContent.trim();
                const bVal = b.cells[columnIndex].textContent.trim();
                
                let comparison = 0;
                if (isNumeric) {{
                    comparison = parseFloat(aVal) - parseFloat(bVal);
                }} else {{
                    comparison = aVal.localeCompare(bVal);
                }}
                
                return isCurrentlyAsc ? -comparison : comparison;
            }});
            
            // Add new sort class
            header.classList.add(isCurrentlyAsc ? 'sort-desc' : 'sort-asc');
            
            // Reappend sorted rows
            rows.forEach(row => tbody.appendChild(row));
        }}
        
        function filterTable(table, searchTerm) {{
            const tbody = table.querySelector('tbody');
            const rows = tbody.querySelectorAll('tr:not(.detail-row)');
            
            searchTerm = searchTerm.toLowerCase();
            
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            }});
        }}
        
        function toggleRowDetails(row) {{
            const detailRow = row.nextElementSibling;
            const expandIcon = row.querySelector('.expand-icon');
            
            if (detailRow && detailRow.classList.contains('detail-row')) {{
                detailRow.classList.toggle('show');
                expandIcon.classList.toggle('expanded');
            }}
        }}
        
        // Failure Details Toggle
        function toggleFailureDetails(element) {{
            const details = element.nextElementSibling;
            if (details && details.classList.contains('failure-details')) {{
                details.classList.toggle('show');
            }}
        }}
        
        // Initialize everything when page loads
        document.addEventListener('DOMContentLoaded', function() {{
            initializeTables();
            
            // Add click handlers for failure items
            document.querySelectorAll('.failure-header').forEach(header => {{
                header.addEventListener('click', () => toggleFailureDetails(header));
            }});
        }});
        
        // Performance Analysis Functions
        function showPerformanceDetails(testName) {{
            alert(`Performance details for: ${{testName}}`);
        }}
        
        // Export Functions
        function exportTableData(format) {{
            const activeTab = document.querySelector('.tab-content.active');
            const table = activeTab.querySelector('table');
            
            if (!table) {{
                alert('No table data to export');
                return;
            }}
            
            let data = [];
            const rows = table.querySelectorAll('tbody tr:not(.detail-row)');
            
            rows.forEach(row => {{
                if (row.style.display !== 'none') {{
                    const rowData = Array.from(row.cells).map(cell => cell.textContent.trim());
                    data.push(rowData);
                }}
            }});
            
            if (format === 'csv') {{
                exportAsCSV(data);
            }} else if (format === 'json') {{
                exportAsJSON(data);
            }}
        }}
        
        function exportAsCSV(data) {{
            const csv = data.map(row => row.join(',')).join('\\n');
            downloadFile(csv, 'test-results.csv', 'text/csv');
        }}
        
        function exportAsJSON(data) {{
            const json = JSON.stringify(data, null, 2);
            downloadFile(json, 'test-results.json', 'application/json');
        }}
        
        function downloadFile(content, fileName, mimeType) {{
            const blob = new Blob([content], {{ type: mimeType }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>'''
        
        # Prepare data for template formatting
        success_class = 'success' if result.success_rate >= 90 else 'warning' if result.success_rate >= 70 else 'danger'
        
        # Generate content for each tab
        performance_content = self._generate_performance_tab(result)
        failures_content = self._generate_failures_tab(result) 
        details_content = self._generate_details_tab(result)
        overview_charts = self._generate_overview_charts(result, include_charts)
        
        # Format and return the complete HTML
        return template.format(
            title=title,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            mode=result.execution_mode.value.replace('_', ' ').title(),
            duration=result.total_execution_time,
            command=' '.join(result.command_executed),
            total_tests=result.total_tests,
            passed_tests=result.passed_tests,
            failed_tests=result.failed_tests,
            skipped_tests=result.skipped_tests,
            success_rate=result.success_rate,
            success_class=success_class,
            test_data_js=json.dumps(test_data, indent=2),
            performance_content=performance_content,
            failures_content=failures_content,
            details_content=details_content,
            overview_charts=overview_charts
        )
    
    def _prepare_test_data_for_js(self, result: TestResult) -> Dict[str, Any]:
        """Prepare test data for JavaScript processing."""
        return {
            'execution': {
                'mode': result.execution_mode.value,
                'duration': result.total_execution_time,
                'command': result.command_executed,
                'timestamp': datetime.now().isoformat()
            },
            'summary': {
                'total': result.total_tests,
                'passed': result.passed_tests,
                'failed': result.failed_tests,
                'skipped': result.skipped_tests,
                'errors': result.error_tests,
                'success_rate': result.success_rate
            },
            'performance': {
                'individual_times': result.individual_test_times or {},
                'total_time': result.total_execution_time
            },
            'failures': result.failure_details or []
        }
    
    def _generate_performance_tab(self, result: TestResult) -> str:
        """Generate performance analysis tab content."""
        if not result.individual_test_times:
            return '''
            <div class="section">
                <h2>Performance Analysis</h2>
                <p>No individual test timing data available for this execution.</p>
            </div>
            '''
        
        times = list(result.individual_test_times.values())
        avg_time = sum(times) / len(times)
        slowest_tests = sorted(result.individual_test_times.items(), key=lambda x: x[1], reverse=True)[:20]
        
        content = f'''
        <div class="section">
            <h2>Performance Analysis</h2>
            
            <div class="metrics">
                <div class="metric">
                    <h3>Average Time</h3>
                    <div class="value">{avg_time:.3f}s</div>
                </div>
                <div class="metric">
                    <h3>Slowest Test</h3>
                    <div class="value">{max(times):.3f}s</div>
                </div>
                <div class="metric">
                    <h3>Fastest Test</h3>
                    <div class="value">{min(times):.3f}s</div>
                </div>
                <div class="metric">
                    <h3>Total Tests Timed</h3>
                    <div class="value">{len(times)}</div>
                </div>
            </div>
            
            <div class="table-container">
                <div class="table-header">
                    <h3>Slowest Tests (Top 20)</h3>
                    <div class="table-controls">
                        <input type="text" class="search-box" placeholder="Search tests...">
                        <button onclick="exportTableData('csv')" style="padding: 8px 16px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; cursor: pointer;">Export CSV</button>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th data-sort="text">Test Name</th>
                            <th data-sort="numeric">Duration (seconds)</th>
                            <th data-sort="numeric">Relative Speed</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
        '''
        
        for test_name, duration in slowest_tests:
            relative_speed = duration / avg_time
            relative_class = 'danger' if relative_speed > 3 else 'warning' if relative_speed > 1.5 else 'success'
            relative_text = f"{relative_speed:.1f}x avg"
            
            # Truncate long test names for display
            display_name = test_name if len(test_name) <= 80 else test_name[:77] + "..."
            
            content += f'''
                        <tr class="expandable-row">
                            <td title="{test_name}">
                                <span class="expand-icon">▶</span> {display_name}
                            </td>
                            <td>{duration:.3f}</td>
                            <td><span class="status-badge status-{relative_class}">{relative_text}</span></td>
                            <td><button onclick="showPerformanceDetails('{test_name}')" style="padding: 4px 12px; border: 1px solid #e2e8f0; border-radius: 4px; background: white; cursor: pointer; font-size: 12px;">Details</button></td>
                        </tr>
                        <tr class="detail-row">
                            <td colspan="4">
                                <div class="detail-content">
                                    <strong>Full Test Name:</strong> {test_name}<br>
                                    <strong>Execution Time:</strong> {duration:.6f} seconds<br>
                                    <strong>Performance Category:</strong> {'Slow' if relative_speed > 3 else 'Moderate' if relative_speed > 1.5 else 'Fast'}
                                </div>
                            </td>
                        </tr>
            '''
        
        content += '''
                    </tbody>
                </table>
            </div>
        </div>
        '''
        
        return content
    
    def _generate_failures_tab(self, result: TestResult) -> str:
        """Generate failures analysis tab content."""
        if not result.failure_details:
            return '''
            <div class="section">
                <h2>Test Failures</h2>
                <div style="text-align: center; padding: 40px; color: #48bb78;">
                    <h3>🎉 No test failures!</h3>
                    <p>All tests passed successfully.</p>
                </div>
            </div>
            '''
        
        content = f'''
        <div class="section">
            <h2>Test Failures ({len(result.failure_details)} failures)</h2>
            
            <div class="table-container">
                <div class="table-header">
                    <h3>Failure Details</h3>
                    <div class="table-controls">
                        <input type="text" class="search-box" placeholder="Search failures...">
                        <select class="filter-select">
                            <option value="">All Failures</option>
                            <option value="AssertionError">Assertion Errors</option>
                            <option value="ImportError">Import Errors</option>
                            <option value="AttributeError">Attribute Errors</option>
                        </select>
                    </div>
                </div>
        '''
        
        for i, failure in enumerate(result.failure_details[:50], 1):  # Limit to 50 failures
            # Extract test name and error type
            if '::' in failure:
                test_name = failure.split('::')[0] if '::' in failure else failure[:100]
            else:
                test_name = failure[:100] + "..." if len(failure) > 100 else failure
            
            error_type = "Unknown"
            if " - " in failure:
                error_part = failure.split(" - ", 1)[1] if " - " in failure else failure
                if ":" in error_part:
                    error_type = error_part.split(":")[0]
            
            content += f'''
                <div class="failure-item">
                    <div class="failure-header" onclick="toggleFailureDetails(this)">
                        #{i}: {test_name} 
                        <span class="status-badge status-failed">{error_type}</span>
                    </div>
                    <div class="failure-details">
                        {failure}
                    </div>
                </div>
            '''
        
        if len(result.failure_details) > 50:
            content += f'''
                <div style="text-align: center; padding: 20px; color: #718096; font-style: italic;">
                    ... and {len(result.failure_details) - 50} more failures. Export full results for complete details.
                </div>
            '''
        
        content += '''
            </div>
        </div>
        '''
        
        return content
    
    def _generate_details_tab(self, result: TestResult) -> str:
        """Generate detailed information tab content."""
        return f'''
        <div class="section">
            <h2>Detailed Information</h2>
            
            <div class="table-container">
                <div class="table-header">
                    <h3>Execution Environment</h3>
                </div>
                <table>
                    <tbody>
                        <tr><td><strong>Execution Mode</strong></td><td>{result.execution_mode.value}</td></tr>
                        <tr><td><strong>Total Execution Time</strong></td><td>{result.total_execution_time:.6f} seconds</td></tr>
                        <tr><td><strong>Return Code</strong></td><td>{result.return_code}</td></tr>
                        <tr><td><strong>Command Executed</strong></td><td><code>{' '.join(result.command_executed)}</code></td></tr>
                        <tr><td><strong>Individual Test Count</strong></td><td>{len(result.individual_test_times) if result.individual_test_times else 'N/A'}</td></tr>
                        <tr><td><strong>Failure Detail Count</strong></td><td>{len(result.failure_details) if result.failure_details else 0}</td></tr>
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h3>Test Statistics</h3>
                <div class="metrics">
                    <div class="metric">
                        <h3>Pass Rate</h3>
                        <div class="value">{(result.passed_tests / result.total_tests * 100) if result.total_tests > 0 else 0:.1f}%</div>
                    </div>
                    <div class="metric">
                        <h3>Fail Rate</h3>
                        <div class="value">{(result.failed_tests / result.total_tests * 100) if result.total_tests > 0 else 0:.1f}%</div>
                    </div>
                    <div class="metric">
                        <h3>Skip Rate</h3>
                        <div class="value">{(result.skipped_tests / result.total_tests * 100) if result.total_tests > 0 else 0:.1f}%</div>
                    </div>
                    <div class="metric">
                        <h3>Error Rate</h3>
                        <div class="value">{(result.error_tests / result.total_tests * 100) if result.total_tests > 0 else 0:.1f}%</div>
                    </div>
                </div>
            </div>
            
            <div class="table-container">
                <div class="table-header">
                    <h3>Export Options</h3>
                </div>
                <div style="padding: 20px;">
                    <button onclick="exportTableData('csv')" style="padding: 12px 24px; margin: 5px; border: 1px solid #4299e1; border-radius: 6px; background: #4299e1; color: white; cursor: pointer;">Export as CSV</button>
                    <button onclick="exportTableData('json')" style="padding: 12px 24px; margin: 5px; border: 1px solid #4299e1; border-radius: 6px; background: white; color: #4299e1; cursor: pointer;">Export as JSON</button>
                </div>
            </div>
        </div>
        '''
    
    def _generate_overview_charts(self, result: TestResult, include_charts: bool) -> str:
        """Generate overview charts section."""
        if not include_charts:
            return ""
        
        return '''
        <div class="chart-container">
            <h3>Test Results Distribution</h3>
            <div style="text-align: center; padding: 40px; color: #718096;">
                <p>📊 Chart visualization would appear here with a charting library like Chart.js or D3.js</p>
                <p>This could include pie charts, bar charts, and trend analysis visualizations.</p>
            </div>
        </div>
        '''
    
    def _prettify_xml(self, elem, level=0):
        """Add pretty formatting to XML element."""
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._prettify_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
    
    def export_multiple_formats(self, result: TestResult, output_dir: Path, 
                               formats: List[str], options: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Export test results in multiple formats."""
        results = {}
        options = options or {}
        
        output_dir.mkdir(exist_ok=True, parents=True)
        
        for format_type in formats:
            if format_type not in self.supported_formats:
                print(f"Warning: Unsupported format '{format_type}' skipped")
                results[format_type] = False
                continue
            
            # Generate appropriate filename
            extension = format_type if format_type != 'junit' else 'xml'
            output_file = output_dir / f"test_results.{extension}"
            
            # Export format
            success = self.export_test_results(result, output_file, format_type, options)
            results[format_type] = success
            
            if success:
                print(f"Exported {format_type.upper()} report to: {output_file}")
            else:
                print(f"Failed to export {format_type.upper()} report")
        
        return results
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported export formats."""
        return self.supported_formats.copy()
    
    def validate_format(self, format_type: str) -> bool:
        """Validate if format is supported."""
        return format_type in self.supported_formats
    
    def get_format_info(self, format_type: str) -> Dict[str, Any]:
        """Get information about a specific format."""
        format_info = {
            ExportFormat.JSON: {
                'description': 'JavaScript Object Notation - structured data format',
                'use_cases': ['API integration', 'data processing', 'archival'],
                'features': ['human readable', 'machine readable', 'hierarchical']
            },
            ExportFormat.XML: {
                'description': 'Extensible Markup Language - structured document format', 
                'use_cases': ['data exchange', 'configuration files', 'web services'],
                'features': ['hierarchical', 'schema validation', 'namespace support']
            },
            ExportFormat.CSV: {
                'description': 'Comma Separated Values - tabular data format',
                'use_cases': ['spreadsheet import', 'data analysis', 'reporting'],
                'features': ['tabular', 'simple', 'widely supported']
            },
            ExportFormat.HTML: {
                'description': 'HyperText Markup Language - web document format',
                'use_cases': ['web reports', 'documentation', 'dashboards'],
                'features': ['visual formatting', 'interactive', 'embeddable']
            },
            ExportFormat.JUNIT: {
                'description': 'JUnit XML format - standard test result format',
                'use_cases': ['CI/CD integration', 'test reporting tools', 'Jenkins'],
                'features': ['standardized', 'tool integration', 'hierarchical']
            },
            ExportFormat.TAP: {
                'description': 'Test Anything Protocol - simple test result format',
                'use_cases': ['test harnesses', 'continuous integration', 'debugging'],
                'features': ['simple', 'streaming', 'human readable']
            },
            ExportFormat.YAML: {
                'description': 'YAML Ain\'t Markup Language - human readable data format',
                'use_cases': ['configuration files', 'documentation', 'data exchange'],
                'features': ['human readable', 'hierarchical', 'comments support']
            },
            ExportFormat.MARKDOWN: {
                'description': 'Markdown - lightweight markup language',
                'use_cases': ['documentation', 'README files', 'web publishing'],
                'features': ['human readable', 'version control friendly', 'convertible']
            },
            "markdown": {
                'description': 'Markdown - lightweight markup language',
                'use_cases': ['documentation', 'README files', 'web publishing'],
                'features': ['human readable', 'version control friendly', 'convertible']
            },
            ExportFormat.PDF: {
                'description': 'Portable Document Format - formatted document format',
                'use_cases': ['reports', 'documentation', 'professional presentations'],
                'features': ['professional formatting', 'print-ready', 'universal compatibility']
            }
        }
        
        return format_info.get(format_type, {'description': 'Unknown format', 'use_cases': [], 'features': []})
    
    def create_export_summary(self, output_dir: Path, export_results: Dict[str, bool]) -> Path:
        """Create a summary of all exports."""
        summary_file = output_dir / 'export_summary.json'
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_formats': len(export_results),
            'successful_exports': sum(export_results.values()),
            'failed_exports': len(export_results) - sum(export_results.values()),
            'results': export_results,
            'files': []
        }
        
        # List generated files
        for format_type, success in export_results.items():
            if success:
                extension = format_type if format_type != 'junit' else 'xml'
                file_path = output_dir / f"test_results.{extension}"
                if file_path.exists():
                    summary['files'].append({
                        'format': format_type,
                        'filename': file_path.name,
                        'size_bytes': file_path.stat().st_size
                    })
        
        summary_file.write_text(json.dumps(summary, indent=2))
        return summary_file