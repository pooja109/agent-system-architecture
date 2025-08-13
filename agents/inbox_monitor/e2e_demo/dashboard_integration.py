"""
Dashboard Integration - Connects Enterprise Dashboard to Demo Runner
"""

import asyncio
import sys
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from enum import Enum
import threading
import queue

# Import Rich components
try:
    from rich.console import Console
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = object
    Live = object

# Import existing dashboard
try:
    from ui.enterprise_dashboard import (
        EnterpriseDashboard,
        TestPhase,
        ServiceStatus,
        ServiceMetric,
        ScenarioProgress
    )
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False
    # Fallback classes
    class TestPhase(Enum):
        INITIALIZING = "initializing"
        RUNNING = "running"
        FINISHED = "finished"
    
    class ServiceStatus(Enum):
        PENDING = "pending"
        CONNECTING = "connecting"
        HEALTHY = "healthy"
        ERROR = "error"

from .config import DemoConfig
from .scenario_loader import Scenario, ScenarioResult
from .terminal_detector import TerminalDetector
from .animation_controller import AnimationController, create_dashboard_controller
from .service_monitor import ServiceMonitor, create_service_monitor


class DashboardState(Enum):
    """Dashboard execution states."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETING = "completing"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class DashboardUpdate:
    """Update message for dashboard."""
    type: str  # 'scenario_start', 'scenario_end', 'service_update', 'phase_change'
    data: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


class DashboardIntegration:
    """Integrates enterprise dashboard with demo runner."""
    
    def __init__(self, config: DemoConfig):
        self.config = config
        self.console = Console() if RICH_AVAILABLE else None
        self.terminal = TerminalDetector()
        
        # Check if dashboard can be used
        self.can_use_dashboard = self._check_dashboard_capability()
        
        if self.can_use_dashboard:
            self.dashboard = EnterpriseDashboard(self.console)
            self.update_queue = queue.Queue()
            self.dashboard_thread = None
            self.live_display = None
            self.state = DashboardState.INITIALIZING
            
            # Initialize animation controller for smooth transitions
            self.animation_controller = create_dashboard_controller()
            
            # Initialize service monitor with dashboard callback
            self.service_monitor = create_service_monitor(
                dashboard_callback=self._service_status_callback
            )
        else:
            self.dashboard = None
            self.animation_controller = None
            self.service_monitor = None
            print("Note: Rich dashboard not available, using simple output")
    
    def _check_dashboard_capability(self) -> bool:
        """Check if terminal supports rich dashboard."""
        # Check dependencies first
        if not RICH_AVAILABLE or not DASHBOARD_AVAILABLE:
            return False
        
        # Skip dashboard in certain conditions
        if self.config.output_file and not sys.stdout.isatty():
            return False
        
        if self.config.output_format != 'dashboard':
            return False
        
        if not self.terminal.supports_rich():
            return False
        
        # Check for CI/CD environment
        if self.terminal.is_ci_environment():
            return False
        
        return True
    
    def _service_status_callback(self, service_name: str, duration: float, success: bool):
        """Callback for service status updates from monitor with comprehensive error recovery."""
        if not self.can_use_dashboard or not self.dashboard:
            return
            
        try:
            # Update dashboard metrics with error handling
            self.dashboard.update_service_metric(service_name, duration, success)
            
            # Let the normal update loop handle dashboard refresh to prevent duplicates
                            
        except Exception as e:
            # Dashboard metric update failed - continue without dashboard updates
            print(f"Dashboard metric update failed: {e}")
            # Don't disable dashboard for metric update failures, just skip this update
    
    async def __aenter__(self):
        """Start dashboard context."""
        if self.can_use_dashboard:
            await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End dashboard context."""
        if self.can_use_dashboard:
            await self.stop()
    
    async def start(self):
        """Start the dashboard display."""
        if not self.can_use_dashboard:
            return
        
        try:
            # Set initial phase with error recovery
            try:
                self.dashboard.update_phase(TestPhase.INITIALIZING)
            except Exception as e:
                print(f"Dashboard phase update failed: {e}")
                self.can_use_dashboard = False
                return
            
            # Start live display with optimized refresh rate for performance
            if self.terminal.is_ci_environment():
                refresh_rate = 1  # Very slow for CI
            else:
                # Adaptive refresh rate based on terminal capabilities
                width = self.terminal.width
                if width < 80:
                    refresh_rate = 2  # Moderate for small terminals
                elif width < 120:
                    refresh_rate = 4  # Good for normal terminals  
                else:
                    refresh_rate = 8  # Smooth for wide terminals
                    
            try:
                self.live_display = Live(
                    self.dashboard.create_dashboard(),
                    console=self.console,
                    refresh_per_second=refresh_rate,
                    transient=False,
                    auto_refresh=True  # Enable auto refresh for responsive updates
                )
                self.live_display.start()
            except Exception as e:
                print(f"Dashboard display failed to start: {e}")
                self.can_use_dashboard = False
                return
            
            # Start update thread with error recovery
            try:
                self.dashboard_thread = threading.Thread(
                    target=self._update_loop,
                    daemon=True
                )
                self.dashboard_thread.start()
            except Exception as e:
                print(f"Dashboard thread failed to start: {e}")
                if self.live_display:
                    self.live_display.stop()
                self.can_use_dashboard = False
                return
            
            # Start service monitoring with error recovery
            if self.service_monitor:
                try:
                    self.service_monitor.start_monitoring()
                    
                    # Simulate initial service connections for demo
                    await self._simulate_service_initialization()
                except Exception as e:
                    print(f"Service monitoring failed to start: {e}")
                    # Continue without service monitoring - not critical
            
            self.state = DashboardState.RUNNING
            
            # Reduced initial delay for better startup performance
            await asyncio.sleep(0.2)
            
        except Exception as e:
            print(f"Dashboard initialization failed: {e}")
            self.can_use_dashboard = False
    
    async def stop(self):
        """Stop the dashboard display."""
        if not self.can_use_dashboard or not self.live_display:
            return
        
        try:
            # Stop animations first
            if self.animation_controller:
                self.animation_controller.stop_all_animations()
            
            # Set completion phase
            self.dashboard.update_phase(TestPhase.FINISHED)
            self.state = DashboardState.FINISHED
            
            # Brief delay for visual completion (reduced for performance)
            await asyncio.sleep(0.2)
            
            # Stop live display
            self.live_display.stop()
            
            # Stop update thread
            if self.dashboard_thread:
                self.update_queue.put(None)  # Sentinel to stop thread
                self.dashboard_thread.join(timeout=1)
            
            # Cleanup animation controller
            if self.animation_controller:
                self.animation_controller.stop_animation_loop()
                
            # Stop service monitoring
            if self.service_monitor:
                self.service_monitor.stop_monitoring()
            
        except Exception as e:
            print(f"Dashboard cleanup error: {e}")
    
    def _update_loop(self):
        """Background thread for dashboard updates with performance optimization."""
        last_refresh = 0.0
        refresh_interval = 0.25  # 4 FPS max for responsive updates
        update_pending = False
        
        while True:
            try:
                # Get update from queue with longer timeout to reduce CPU usage
                update = self.update_queue.get(timeout=0.5)  # Increased timeout
                
                if update is None:  # Sentinel to stop
                    break
                
                # Process update
                self._process_update(update)
                update_pending = True
                    
            except queue.Empty:
                # No updates available
                pass
            except Exception as e:
                print(f"Dashboard update error: {e}")
                continue
                
            # Conservative throttled refresh to prevent duplicate headers
            current_time = time.time()
            if (update_pending and 
                self.live_display and 
                self.state in [DashboardState.RUNNING, DashboardState.COMPLETING, DashboardState.FINISHED] and
                (current_time - last_refresh) >= refresh_interval):
                try:
                    self.live_display.update(self.dashboard.create_dashboard())
                    last_refresh = current_time
                    update_pending = False
                except Exception as e:
                    # Don't let display errors stop the update loop
                    pass
    
    def _process_update(self, update: DashboardUpdate):
        """Process a dashboard update."""
        try:
            if update.type == 'phase_change':
                phase = update.data.get('phase')
                if phase:
                    self.dashboard.update_phase(phase)
            
            elif update.type == 'scenario_start':
                scenario_id = update.data.get('scenario_id')
                if scenario_id:
                    self.dashboard.start_scenario(scenario_id)
            
            elif update.type == 'scenario_progress':
                scenario_id = update.data.get('scenario_id')
                progress = update.data.get('progress')
                if scenario_id and progress is not None:
                    # Update scenario progress in dashboard
                    pass  # Dashboard handles this internally
            
            elif update.type == 'scenario_end':
                scenario_id = update.data.get('scenario_id')
                success = update.data.get('success')
                business_outcome = update.data.get('business_outcome')
                if scenario_id is not None:
                    self.dashboard.complete_scenario(
                        scenario_id, 
                        success=success, 
                        business_outcome=business_outcome
                    )
                    # Let the regular throttled update handle this to prevent duplicate headers
            
            elif update.type == 'service_update':
                service = update.data.get('service')
                duration = update.data.get('duration')
                success = update.data.get('success', True)
                if service and duration is not None:
                    self.dashboard.update_service_metric(service, duration, success)
            
            elif update.type == 'message':
                message = update.data.get('message')
                level = update.data.get('level', 'info')
                if message:
                    self.dashboard.log_business_event(message, level)
                    
        except Exception as e:
            print(f"Update processing error: {e}")
    
    def update_phase(self, phase: TestPhase):
        """Update execution phase."""
        if self.can_use_dashboard:
            self.update_queue.put(
                DashboardUpdate('phase_change', {'phase': phase})
            )
    
    def start_scenario(self, scenario: Scenario):
        """Signal scenario start."""
        if self.can_use_dashboard:
            self.update_queue.put(
                DashboardUpdate('scenario_start', {'scenario_id': scenario.id})
            )
    
    def update_scenario_progress(self, scenario_id: int, progress: float):
        """Update scenario progress (0.0 to 1.0)."""
        if self.can_use_dashboard:
            self.update_queue.put(
                DashboardUpdate('scenario_progress', {
                    'scenario_id': scenario_id,
                    'progress': progress
                })
            )
    
    def end_scenario(self, result: ScenarioResult):
        """Signal scenario completion."""
        if self.can_use_dashboard:
            self.update_queue.put(
                DashboardUpdate('scenario_end', {
                    'scenario_id': result.scenario.id,
                    'success': result.success,
                    'business_outcome': result.business_outcome
                })
            )
    
    def update_service(self, service: str, duration: float, success: bool = True):
        """Update service status."""
        if self.can_use_dashboard:
            self.update_queue.put(
                DashboardUpdate('service_update', {
                    'service': service,
                    'duration': duration,
                    'success': success
                })
            )
    
    def add_message(self, message: str, level: str = 'info'):
        """Add a message to the dashboard."""
        if self.can_use_dashboard:
            self.update_queue.put(
                DashboardUpdate('message', {
                    'message': message,
                    'level': level
                })
            )
    
    def is_active(self) -> bool:
        """Check if dashboard is active."""
        return self.can_use_dashboard and self.state == DashboardState.RUNNING
    
    def initialize_scenarios(self, scenarios: List[Scenario]):
        """Initialize scenario list in dashboard."""
        if self.can_use_dashboard and self.dashboard:
            scenario_data = []
            for scenario in scenarios:
                scenario_data.append({
                    'name': scenario.name,
                    'id': scenario.id
                })
            self.dashboard.initialize_scenarios(scenario_data)
    
    def set_testing_phase(self):
        """Set dashboard to testing phase."""
        if self.can_use_dashboard:
            self.update_phase(TestPhase.TESTING)
    
    async def _simulate_service_initialization(self):
        """Simulate progressive service initialization with error recovery."""
        if not self.service_monitor:
            return
            
        # Reduced delays for better performance while maintaining visual effect
        services = [
            ("prompt_manager", 0.1),   # Fastest - local service
            ("azure_key_vault", 0.2), # Fast - cached authentication  
            ("email_service", 0.3),   # Medium - network service
            ("databricks_pool", 0.4), # Slower - database connection
            ("ai_foundry", 0.5),      # Slowest - AI service startup
        ]
        
        # Simulate each service connecting with error recovery
        for service_name, delay in services:
            try:
                op_id = self.service_monitor.start_operation(service_name, "initialize")
                await asyncio.sleep(delay)  # Simulate connection time
                
                # Simulate occasional service failures (5% chance for realism)
                import random
                success = random.random() > 0.05
                
                if op_id:  # Ensure operation was created successfully
                    self.service_monitor.complete_operation(
                        op_id, 
                        success=success,
                        error_message="Service temporarily unavailable" if not success else None
                    )
                    
            except Exception as e:
                print(f"Service initialization failed for {service_name}: {e}")
                # Continue with other services
            
    def start_service_operation(self, service_name: str, operation_type: str) -> Optional[str]:
        """Start tracking a service operation with error recovery."""
        if not self.service_monitor:
            return None
            
        try:
            return self.service_monitor.start_operation(service_name, operation_type)
        except Exception as e:
            print(f"Failed to start service operation {operation_type} for {service_name}: {e}")
            return None
        
    def complete_service_operation(self, operation_id: str, success: bool = True, 
                                 error_message: Optional[str] = None):
        """Complete a tracked service operation with error recovery."""
        if not self.service_monitor or not operation_id:
            return
            
        try:
            self.service_monitor.complete_operation(
                operation_id, success=success, error_message=error_message
            )
        except Exception as e:
            print(f"Failed to complete service operation {operation_id}: {e}")
            # Continue execution - service tracking failure shouldn't stop the demo
    
    def get_service_health_summary(self) -> Dict[str, Any]:
        """Get overall service health summary with error recovery."""
        if not self.service_monitor:
            return {"status": "monitoring_disabled"}
            
        try:
            return self.service_monitor.get_health_summary()
        except Exception as e:
            print(f"Failed to get service health summary: {e}")
            return {"status": "monitoring_error", "error": str(e)}