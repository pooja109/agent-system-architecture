# ui/progress/indicators.py
from typing import Optional, Any
from rich.console import Console
from rich.spinner import Spinner
from rich.progress import Progress
from rich.text import Text


class ProgressIndicator:
    """Individual progress indicator for operations."""
    
    def __init__(self, console: Console, indicator_type: str = "spinner"):
        self.console = console
        self.indicator_type = indicator_type
        self._active = False
    
    def start(self, message: str) -> None:
        """Start the progress indicator."""
        self._active = True
        if self.indicator_type == "spinner":
            self.console.print(f"⏳ {message}")
    
    def update(self, message: str, progress: Optional[float] = None) -> None:
        """Update the progress indicator."""
        if not self._active:
            return
        
        if progress is not None and progress >= 0:
            percentage = f" ({progress:.0%})" if progress <= 1 else f" ({progress:.0f}%)"
            self.console.print(f"🔄 {message}{percentage}")
        else:
            self.console.print(f"🔄 {message}")
    
    def complete(self, message: str) -> None:
        """Complete the progress indicator."""
        if self._active:
            self.console.print(f"✅ {message}")
            self._active = False
    
    def fail(self, message: str, error: Optional[Exception] = None) -> None:
        """Fail the progress indicator."""
        if self._active:
            error_msg = f": {error}" if error else ""
            self.console.print(f"❌ {message}{error_msg}")
            self._active = False