"""
Enterprise CLI Dashboard for E2E Integration Testing
==================================================

World-class terminal visualization that transforms verbose logs into an informative,
delightful dashboard experience for both technical staff and business users.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import threading

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich.tree import Tree
from rich.align import Align
from rich import box
from rich.rule import Rule


class TestPhase(Enum):
    """Test execution phases for progressive visualization."""
    INITIALIZING = "initializing"
    AUTHENTICATING = "authenticating" 
    CONNECTING = "connecting"
    TESTING = "testing"
    COMPLETING = "completing"
    FINISHED = "finished"


class ServiceStatus(Enum):
    """Service health status indicators."""
    PENDING = ("⏳", "dim")
    CONNECTING = ("🔄", "yellow")
    HEALTHY = ("✅", "green")
    WARNING = ("⚠️", "yellow")
    ERROR = ("❌", "red")
    DISABLED = ("⏸️", "dim")
    DEGRADED = ("🟡", "yellow")
    CRITICAL = ("🔴", "red")
    RECOVERING = ("🔄", "blue")


@dataclass
class ServiceMetric:
    """Individual service performance metric."""
    name: str
    current_duration: float = 0.0
    average_duration: float = 0.0
    status: ServiceStatus = ServiceStatus.PENDING
    operations_count: int = 0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Enhanced health tracking
    success_count: int = 0
    failure_count: int = 0
    sla_threshold: float = 2.0
    sla_violations: int = 0
    trend: str = "stable"  # "improving", "stable", "degrading"
    health_score: float = 100.0  # 0-100 health percentage
    
    @property 
    def status_display(self) -> str:
        """Get formatted status display with trend indicator."""
        icon, color = self.status.value
        duration_text = f"{self.current_duration:.1f}s" if self.current_duration > 0 else "---"
        
        # Add trend indicator
        trend_indicators = {
            "improving": "📈",
            "degrading": "📉", 
            "stable": "➖"
        }
        trend_icon = trend_indicators.get(self.trend, "")
        
        return f"{icon} {duration_text} {trend_icon}"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total_ops = self.success_count + self.failure_count
        if total_ops == 0:
            return 100.0
        return (self.success_count / total_ops) * 100.0
    
    @property
    def sla_compliance(self) -> float:
        """Calculate SLA compliance percentage."""
        if self.operations_count == 0:
            return 100.0
        compliant_ops = self.operations_count - self.sla_violations
        return (compliant_ops / self.operations_count) * 100.0
    
    @property
    def performance_category(self) -> ServiceStatus:
        """Determine performance category based on multiple factors."""
        if self.current_duration == 0:
            return ServiceStatus.PENDING
        
        # Check failure rate
        success_rate = self.success_rate
        sla_compliance = self.sla_compliance
        
        # Critical: High failure rate or very slow
        if success_rate < 80 or self.current_duration > 10.0:
            return ServiceStatus.CRITICAL
        
        # Error: Moderate failures or slow performance  
        elif success_rate < 95 or self.current_duration > 5.0:
            return ServiceStatus.ERROR
        
        # Warning: Some issues but acceptable
        elif success_rate < 99 or sla_compliance < 90 or self.current_duration > self.sla_threshold:
            return ServiceStatus.WARNING
            
        # Degraded: Performance trend is bad
        elif self.trend == "degrading":
            return ServiceStatus.DEGRADED
            
        # Healthy: All good
        else:
            return ServiceStatus.HEALTHY
    
    def update_health_score(self):
        """Calculate comprehensive health score (0-100)."""
        success_weight = 40  # Success rate importance
        performance_weight = 30  # Response time importance  
        sla_weight = 20  # SLA compliance importance
        trend_weight = 10  # Trend importance
        
        # Success rate component (0-40 points)
        success_component = (self.success_rate / 100.0) * success_weight
        
        # Performance component (0-30 points) - inverse of normalized response time
        max_acceptable_time = 5.0
        performance_ratio = min(self.current_duration / max_acceptable_time, 1.0)
        performance_component = (1.0 - performance_ratio) * performance_weight
        
        # SLA compliance component (0-20 points)
        sla_component = (self.sla_compliance / 100.0) * sla_weight
        
        # Trend component (0-10 points)
        trend_scores = {"improving": 1.0, "stable": 0.8, "degrading": 0.3}
        trend_component = trend_scores.get(self.trend, 0.5) * trend_weight
        
        self.health_score = success_component + performance_component + sla_component + trend_component


@dataclass
class ScenarioProgress:
    """Progress tracking for individual test scenarios."""
    name: str
    scenario_id: int
    status: str = "pending"  # pending, running, completed, failed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0
    business_outcome: str = ""
    technical_details: str = ""
    
    @property
    def status_icon(self) -> str:
        """Get status icon for display."""
        icons = {
            "pending": "⏳",
            "running": "🔄", 
            "completed": "✅",
            "failed": "❌"
        }
        return icons.get(self.status, "❓")
    
    @property
    def duration_display(self) -> str:
        """Get formatted duration display."""
        if self.status == "running" and self.start_time:
            duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            return f"{duration:.1f}s"
        elif self.duration > 0:
            return f"{self.duration:.1f}s"
        else:
            return "---"


class EnterpriseDashboard:
    """
    Enterprise-grade CLI dashboard for E2E integration testing.
    
    Features:
    - Progressive status visualization
    - Live performance metrics
    - Business-friendly language
    - Smart log filtering
    - Executive summary mode
    - Hierarchical progress tracking
    """
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize the enterprise dashboard."""
        self.console = console or Console()
        self.phase = TestPhase.INITIALIZING
        self.start_time = datetime.now(timezone.utc)
        
        # Service metrics tracking
        self.services: Dict[str, ServiceMetric] = {
            "azure_key_vault": ServiceMetric("Azure Key Vault"),
            "databricks_pool": ServiceMetric("Databricks Pool"), 
            "ai_foundry": ServiceMetric("AI Foundry"),
            "email_service": ServiceMetric("Email Service"),
            "prompt_manager": ServiceMetric("Prompt Manager")
        }
        
        # Scenario tracking
        self.scenarios: List[ScenarioProgress] = []
        self.current_scenario: Optional[ScenarioProgress] = None
        
        # Performance metrics
        self.total_operations = 0
        self.successful_operations = 0
        self.performance_alerts: List[str] = []
        self.business_outcomes: List[str] = []
        
        # Live display management
        self.live: Optional[Live] = None
        self.layout: Optional[Layout] = None
        self._update_lock = threading.RLock()
        
    def initialize_scenarios(self, scenario_list: List[Dict[str, Any]]) -> None:
        """Initialize scenario progress tracking."""
        with self._update_lock:
            self.scenarios = []
            for i, scenario in enumerate(scenario_list, 1):
                progress = ScenarioProgress(
                    name=scenario.get('name', f'Scenario {i}'),
                    scenario_id=scenario.get('id', i),  # Use actual scenario ID
                    business_outcome=self._get_business_outcome(scenario.get('id', i), scenario.get('name', ''))
                )
                self.scenarios.append(progress)
    
    def _get_business_outcome(self, scenario_id: int, scenario_name: str) -> str:
        """Map scenario IDs to correct business outcomes that match the runner logic."""
        # These outcomes match the actual business outcomes from runner.py execution
        outcome_map = {
            5: "New sales opportunity identified and assigned to expert",        # Positive engagement created
            6: "Customer removed from outreach list and account manager notified",      # Contact removed + Victoria Grant notified
            7: "Customer inquiry forwarded to specialist support team",        # Account team notified
            8: "Customer marked as out of office - follow-up scheduled",            # Contact marked as temporarily away
            9: "Invalid email address identified and contact updated",        # Email marked as invalid
            10: "Customer status updated and account manager notified"       # Contact updated + Victoria Grant notified + Databricks updated
        }
        return outcome_map.get(scenario_id, f"Process customer inquiry #{scenario_id}")
    
    def start_scenario(self, scenario_id: int) -> None:
        """Mark a scenario as started."""
        with self._update_lock:
            for scenario in self.scenarios:
                if scenario.scenario_id == scenario_id:
                    scenario.status = "running"
                    scenario.start_time = datetime.now(timezone.utc)
                    self.current_scenario = scenario
                    break
    
    def complete_scenario(self, scenario_id: int, success: bool = True, 
                         business_outcome: Optional[str] = None) -> None:
        """Mark a scenario as completed."""
        with self._update_lock:
            for scenario in self.scenarios:
                if scenario.scenario_id == scenario_id:
                    scenario.status = "completed" if success else "failed"
                    scenario.end_time = datetime.now(timezone.utc)
                    if scenario.start_time:
                        scenario.duration = (scenario.end_time - scenario.start_time).total_seconds()
                    
                    # Update business outcome if provided
                    if business_outcome:
                        scenario.business_outcome = business_outcome
                        # Clean up and add to business outcomes list for summary display
                        clean_outcome = self._clean_business_outcome(business_outcome)
                        if clean_outcome and clean_outcome not in self.business_outcomes:
                            self.business_outcomes.append(clean_outcome)
                    
                    # If no business outcome provided but scenario has a predefined one, use it
                    elif scenario.business_outcome and scenario.business_outcome not in self.business_outcomes:
                        clean_outcome = self._clean_business_outcome(scenario.business_outcome)
                        if clean_outcome and clean_outcome not in self.business_outcomes:
                            self.business_outcomes.append(clean_outcome)
                    
                    # Clear current scenario
                    if self.current_scenario and self.current_scenario.scenario_id == scenario_id:
                        self.current_scenario = None
                    
                    break
    
    def update_phase(self, phase: TestPhase) -> None:
        """Update current test phase."""
        with self._update_lock:
            self.phase = phase
    
    def update_service_metric(self, service_name: str, duration: float, success: bool = True) -> None:
        """Update service performance metrics."""
        with self._update_lock:
            if service_name in self.services:
                service = self.services[service_name]
                service.current_duration = duration
                service.operations_count += 1
                
                # Calculate running average
                if service.operations_count == 1:
                    service.average_duration = duration
                else:
                    service.average_duration = (
                        (service.average_duration * (service.operations_count - 1) + duration) / 
                        service.operations_count
                    )
                
                # Update status based on performance
                service.status = service.performance_category
                service.last_update = datetime.now(timezone.utc)
                
                # Track performance alerts
                if duration > 10.0:
                    alert = f"{service_name} slow response ({duration:.1f}s)"
                    if alert not in self.performance_alerts:
                        self.performance_alerts.append(alert)
                
                if success:
                    self.successful_operations += 1
                self.total_operations += 1
    
    def create_dashboard(self) -> Panel:
        """Create the main dashboard display."""
        # Create layout sections
        header = self._create_header()
        status_section = self._create_status_section()
        progress_section = self._create_progress_section()
        metrics_section = self._create_metrics_section()
        
        # Combine sections based on current phase
        if self.phase in [TestPhase.INITIALIZING, TestPhase.AUTHENTICATING, TestPhase.CONNECTING]:
            content = Group(header, status_section)
        else:  # TESTING, COMPLETING, FINISHED - all show the testing layout
            content = Group(header, progress_section, metrics_section)
        
        return Panel(
            content,
            title="🚀 E2E Integration Test Suite",
            title_align="center",
            border_style="blue",
            padding=(1, 2)
        )
    
    def _create_header(self) -> Panel:
        """Create dashboard header with key metrics."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        # Calculate scenario-level success instead of confusing internal operations
        completed_scenarios = sum(1 for s in self.scenarios if s.status in ["completed", "failed"])
        successful_scenarios = sum(1 for s in self.scenarios if s.status == "completed")
        failed_scenarios = sum(1 for s in self.scenarios if s.status == "failed")
        total_scenarios = len(self.scenarios)
        scenario_success_rate = (successful_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0
        
        header_table = Table.grid(padding=(0, 2))
        header_table.add_column(justify="left")
        header_table.add_column(justify="center") 
        header_table.add_column(justify="right")
        
        # Phase indicator with appropriate icon
        phase_icons = {
            TestPhase.INITIALIZING: "🔄",
            TestPhase.AUTHENTICATING: "🔐", 
            TestPhase.CONNECTING: "🔗",
            TestPhase.TESTING: "🎯",
            TestPhase.COMPLETING: "📊",
            TestPhase.FINISHED: "✅"
        }
        
        phase_display = f"{phase_icons.get(self.phase, '❓')} {self.phase.value.title()}"
        progress_display = f"📈 {completed_scenarios}/{total_scenarios} scenarios ({elapsed:.0f}s elapsed)"
        success_display = f"✅ {scenario_success_rate:.0f}% success"
        
        header_table.add_row(phase_display, progress_display, success_display)
        
        return Panel(
            header_table,
            style="bold blue",
            box=box.ROUNDED,
            height=3
        )
    
    def _create_status_section(self) -> Panel:
        """Create service status section for initialization phases."""
        status_table = Table(box=box.MINIMAL)
        status_table.add_column("Service", style="bold")
        status_table.add_column("Status", justify="center")
        status_table.add_column("Duration", justify="right")
        status_table.add_column("Health", justify="center")
        
        for service in self.services.values():
            health_icon, health_color = service.status.value
            duration_text = f"{service.current_duration:.1f}s" if service.current_duration > 0 else "---"
            
            status_table.add_row(
                service.name,
                service.status_display,
                duration_text,
                f"[{health_color}]{health_icon}[/{health_color}]"
            )
        
        return Panel(
            status_table,
            title="🔧 Service Status",
            border_style="green"
        )
    
    def _create_progress_section(self) -> Panel:
        """Create scenario progress section for testing phase."""
        progress_tree = Tree("📋 Test Scenarios")
        
        for scenario in self.scenarios:
            status_text = f"{scenario.status_icon} {scenario.name}"
            if scenario.status == "completed":
                status_text += f" [dim]({scenario.duration_display})[/dim]"
            elif scenario.status == "running":
                status_text += f" [yellow]({scenario.duration_display})[/yellow]"
            
            node = progress_tree.add(status_text)
            if scenario.business_outcome:
                outcome_style = "green" if scenario.status == "completed" else "yellow"
                node.add(f"[{outcome_style}]→ {scenario.business_outcome}[/{outcome_style}]")
        
        return Panel(
            progress_tree,
            title="🎯 Business Impact",
            border_style="cyan"
        )
    
    def _create_metrics_section(self) -> Columns:
        """Create performance metrics section."""
        # Performance table
        perf_table = Table(box=box.MINIMAL, title="[bold yellow]⚡ Performance[/bold yellow]")
        perf_table.add_column("Service")
        perf_table.add_column("Current", justify="right")
        perf_table.add_column("Average", justify="right") 
        perf_table.add_column("Status", justify="center")
        
        for service in self.services.values():
            if service.operations_count > 0:
                current = f"{service.current_duration:.1f}s"
                average = f"{service.average_duration:.1f}s" 
                status_icon, status_color = service.performance_category.value
                
                perf_table.add_row(
                    service.name.split()[-1],  # Short name
                    current,
                    average,
                    f"[{status_color}]{status_icon}[/{status_color}]"
                )
        
        # Alerts panel
        alerts_content = []
        if self.performance_alerts:
            for alert in self.performance_alerts[-3:]:  # Show last 3 alerts
                alerts_content.append(f"⚠️  {alert}")
        else:
            alerts_content.append("[green]✅ All systems performing normally[/green]")
        
        alerts_panel = Panel(
            "\n".join(alerts_content),
            title="[bold red]🔍 System Health[/bold red]", 
            border_style="red" if self.performance_alerts else "green"
        )
        
        return Columns([perf_table, alerts_panel], equal=True)
    
    def _create_summary_section(self) -> Panel:
        """Create final results summary section."""
        # Summary statistics
        completed = sum(1 for s in self.scenarios if s.status == "completed")
        failed = sum(1 for s in self.scenarios if s.status == "failed")
        total_duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        # Create summary table
        summary_table = Table.grid(padding=1)
        summary_table.add_column(justify="left")
        summary_table.add_column(justify="center")
        summary_table.add_column(justify="right")
        
        summary_table.add_row(
            f"📊 Results: {completed}✅ {failed}❌",
            f"⏱️  Duration: {total_duration:.0f}s",
            f"📈 Success: {(completed/len(self.scenarios)*100):.0f}%" if self.scenarios else "📈 Success: 100%"
        )
        
        # Business outcomes
        outcomes_text = []
        for outcome in self.business_outcomes[-5:]:  # Show last 5 outcomes
            outcomes_text.append(f"✅ {outcome}")
        
        if not outcomes_text:
            outcomes_text.append("[dim]No business outcomes recorded[/dim]")
        
        # Combine summary and outcomes
        combined_content = Group(
            Panel(summary_table, title="🎯 Executive Summary", style="bold green"),
            Panel(
                "\n".join(outcomes_text),
                title="🚀 Business Impact",
                border_style="green"
            )
        )
        
        return Panel(combined_content, title="📋 Final Results", border_style="blue")
    
    @asynccontextmanager
    async def live_display(self):
        """Context manager for live dashboard display."""
        try:
            self.live = Live(self.create_dashboard(), console=self.console, refresh_per_second=2)
            self.live.start()
            yield self
        finally:
            if self.live:
                self.live.stop()
                self.live = None
    
    def log_business_event(self, message: str, level: str = "info") -> None:
        """Log business-friendly event (filtered intelligently)."""
        # Only show business-relevant events to reduce noise
        business_keywords = [
            "completed successfully", "forwarded", "created", "escalated", 
            "routed", "scheduled", "validated", "processed"
        ]
        
        if any(keyword in message.lower() for keyword in business_keywords):
            if level == "success" and "✅" not in message:
                message = f"✅ {message}"
            elif level == "warning" and "⚠️" not in message:  
                message = f"⚠️  {message}"
            elif level == "error" and "❌" not in message:
                message = f"❌ {message}"
            
            # Add to business outcomes if it's a success
            if level == "success" or "completed successfully" in message:
                outcome = self._extract_business_outcome(message)
                if outcome and outcome not in self.business_outcomes:
                    self.business_outcomes.append(outcome)
    
    def _clean_business_outcome(self, outcome: str) -> Optional[str]:
        """Convert technical outcome codes into user-friendly business language."""
        if not outcome:
            return None
        
        # Handle complex outcomes with multiple parts
        if "Victoria Grant notified" in outcome and "Contact updated" in outcome:
            return "Customer status updated and account manager notified"
        elif "Contact removed" in outcome and "Victoria Grant notified" in outcome:
            return "Customer removed from outreach list and account manager notified"
        elif "Account team notified" in outcome:
            return "Customer inquiry forwarded to specialist support team"
        elif "Contact marked as temporarily away" in outcome:
            return "Customer marked as out of office - follow-up scheduled"
        elif "Email marked as invalid" in outcome:
            return "Invalid email address identified and contact updated"
        elif "Positive engagement created" in outcome:
            return "New sales opportunity identified and assigned to expert"
        
        # Handle simple outcomes
        elif "REAL_ENG_" in outcome:
            return "New sales opportunity identified and assigned to expert"
        elif "REAL_REMOVE_" in outcome:
            return "Customer removed from outreach list"
        elif "REAL_TEAM_EMAIL_" in outcome:
            return "Customer inquiry forwarded to specialist support team"
        elif "REAL_STATUS_temporary_away" in outcome:
            return "Customer marked as out of office - follow-up scheduled"
        elif "REAL_INVALID_SF_" in outcome:
            return "Invalid email address identified and contact updated"
        elif "REAL_STATUS_no_longer_works" in outcome:
            return "Customer status updated and account manager notified"
        
        # If no pattern matches, return the original (cleaned of technical codes)
        import re
        cleaned = re.sub(r'REAL_[A-Z_]+_[a-zA-Z0-9_]+', '', outcome)
        cleaned = re.sub(r'[a-z0-9]{8,}', '', cleaned)  # Remove IDs
        cleaned = cleaned.replace('_', ' ').strip(', ')
        
        return cleaned if cleaned else None
    
    def _extract_business_outcome(self, message: str) -> Optional[str]:
        """Extract business outcome from technical message."""
        if "forwarded" in message:
            return "Customer inquiry routed to appropriate team"
        elif "completed successfully" in message:
            return "Customer interaction processed successfully"  
        elif "escalated" in message:
            return "Issue escalated to specialist support"
        else:
            return None
    
    def show_final_dashboard(self) -> None:
        """Display final results dashboard."""
        self.phase = TestPhase.FINISHED
        final_panel = self.create_dashboard()
        
        # Add celebration for successful completion
        completed_count = sum(1 for s in self.scenarios if s.status == "completed")
        if completed_count == len(self.scenarios):
            celebration = Panel(
                Align.center("🎉 All scenarios completed successfully! 🎉"),
                style="bold green",
                box=box.DOUBLE
            )
            self.console.print()
            self.console.print(celebration)
        
        self.console.print()
        self.console.print(final_panel)
        self.console.print()


# Factory function for easy instantiation
def create_enterprise_dashboard() -> EnterpriseDashboard:
    """Create a new enterprise dashboard instance."""
    return EnterpriseDashboard()


# Integration helpers for existing codebase
class DashboardLogger:
    """Logger adapter that integrates with enterprise dashboard."""
    
    def __init__(self, dashboard: EnterpriseDashboard):
        self.dashboard = dashboard
        
    def info(self, message: str, **kwargs):
        """Log info message through dashboard filter."""
        self.dashboard.log_business_event(message, "info")
        
    def success(self, message: str, **kwargs): 
        """Log success message through dashboard filter."""
        self.dashboard.log_business_event(message, "success")
        
    def warning(self, message: str, **kwargs):
        """Log warning message through dashboard filter.""" 
        self.dashboard.log_business_event(message, "warning")
        
    def error(self, message: str, **kwargs):
        """Log error message through dashboard filter."""
        self.dashboard.log_business_event(message, "error")