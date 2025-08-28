# ui/progress/terminal_progress.py
import time
import threading
from typing import Dict, Any, Optional, List
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn
from rich.live import Live
from rich.console import Console
from rich.text import Text

from .progress_manager import ProgressState, ProgressType


class TerminalProgressRenderer:
    """Terminal-specific progress rendering with advanced display options."""
    
    def __init__(self, console: Console):
        self.console = console
        self._active_displays: Dict[str, Live] = {}
        self._display_lock = threading.Lock()
        self._last_update_time = 0
        self._update_throttle_interval = 0.1  # 10Hz rate limiting
    
    def create_progress_display(self, title: Optional[str] = None, 
                              show_percentage: bool = True,
                              show_elapsed: bool = True) -> Progress:
        """Create a customized progress display."""
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}")
        ]
        
        if show_percentage:
            columns.append(BarColumn())
            columns.append(TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))
        
        if show_elapsed:
            columns.append(TimeElapsedColumn())
        
        return Progress(*columns, console=self.console)
    
    def render_operation_status(self, operations: List[ProgressState], 
                              compact: bool = False) -> None:
        """Render current operation status to terminal."""
        current_time = time.time()
        
        # Apply 10Hz rate limiting
        if current_time - self._last_update_time < self._update_throttle_interval:
            return
        
        self._last_update_time = current_time
        
        if not operations:
            return
        
        if compact:
            self._render_compact_status(operations)
        else:
            self._render_detailed_status(operations)
    
    def _render_compact_status(self, operations: List[ProgressState]) -> None:
        """Render compact one-line status."""
        active_ops = [op for op in operations if op.status not in ['completed', 'failed']]
        
        if not active_ops:
            return
        
        status_parts = []
        for op in active_ops[:3]:  # Show max 3 operations
            icon = self._get_status_icon(op.progress_type, op.status)
            status_parts.append(f"{icon} {op.description[:20]}")
        
        if len(active_ops) > 3:
            status_parts.append(f"(+{len(active_ops) - 3} more)")
        
        status_line = " | ".join(status_parts)
        
        # Clear line and print status
        self.console.print(f"\r{status_line}", end="", markup=False)
    
    def _render_detailed_status(self, operations: List[ProgressState]) -> None:
        """Render detailed multi-line status."""
        active_ops = [op for op in operations if op.status not in ['completed', 'failed']]
        
        if not active_ops:
            return
        
        status_text = Text()
        
        for i, op in enumerate(active_ops):
            if i > 0:
                status_text.append("\n")
            
            icon = self._get_status_icon(op.progress_type, op.status)
            status_text.append(f"{icon} ", style="cyan")
            status_text.append(op.description, style="white")
            
            # Add progress information if available
            if op.total and op.current > 0:
                progress_pct = (op.current / op.total) * 100
                status_text.append(f" ({op.current}/{op.total}, {progress_pct:.0f}%)", style="dim")
            
            # Add elapsed time
            elapsed = time.time() - op.started_at
            if elapsed > 2:  # Only show for operations longer than 2 seconds
                status_text.append(f" [{elapsed:.1f}s]", style="dim")
        
        self.console.print(status_text)
    
    def _get_status_icon(self, progress_type: ProgressType, status: str) -> str:
        """Get appropriate icon for operation status."""
        if status == 'failed':
            return "❌"
        elif status == 'completed':
            return "✅"
        elif progress_type == ProgressType.SPINNER:
            return "🔄"
        elif progress_type == ProgressType.BAR:
            return "📊"
        elif progress_type == ProgressType.COUNTER:
            return "🔢"
        else:
            return "⏳"
    
    def show_completion_summary(self, completed_operations: List[ProgressState]) -> None:
        """Show summary of completed operations."""
        if not completed_operations:
            return
        
        successful = [op for op in completed_operations if op.status == 'completed']
        failed = [op for op in completed_operations if op.status == 'failed']
        
        summary_text = Text()
        summary_text.append("\n📋 Operations Summary:\n", style="bold blue")
        
        if successful:
            summary_text.append(f"✅ Completed: {len(successful)}\n", style="green")
            
        if failed:
            summary_text.append(f"❌ Failed: {len(failed)}\n", style="red")
        
        # Show timing information
        total_duration = sum(
            op.updated_at - op.started_at 
            for op in completed_operations 
            if op.updated_at and op.started_at
        )
        
        if total_duration > 0:
            summary_text.append(f"⏱️  Total Duration: {total_duration:.2f}s\n", style="dim")
        
        self.console.print(summary_text)
    
    def clear_progress_display(self, display_id: str) -> None:
        """Clear a specific progress display."""
        with self._display_lock:
            if display_id in self._active_displays:
                self._active_displays[display_id].stop()
                del self._active_displays[display_id]
    
    def cleanup_all_displays(self) -> None:
        """Clean up all active progress displays."""
        with self._display_lock:
            for display in self._active_displays.values():
                display.stop()
            self._active_displays.clear()
    
    def render_error_with_context(self, error: Exception, 
                                operation_context: Optional[ProgressState] = None) -> None:
        """Render error information with operation context."""
        error_text = Text()
        error_text.append("❌ Operation Failed\n", style="bold red")
        
        if operation_context:
            error_text.append(f"Operation: {operation_context.description}\n", style="white")
            error_text.append(f"Duration: {time.time() - operation_context.started_at:.2f}s\n", style="dim")
        
        error_text.append(f"Error: {str(error)}\n", style="red")
        
        if operation_context and operation_context.correlation_id:
            error_text.append(f"Correlation ID: {operation_context.correlation_id}\n", style="dim")
        
        self.console.print(error_text)