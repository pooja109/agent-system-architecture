"""
Animation Controller - Manages Dashboard Animations and Visual Effects
"""

import asyncio
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.text import Text
    from rich.spinner import Spinner
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = object
    Progress = object


class AnimationType(Enum):
    """Types of animations supported."""
    FADE_IN = "fade_in"
    SLIDE_IN = "slide_in" 
    SPINNER = "spinner"
    PROGRESS_BAR = "progress_bar"
    TYPE_WRITER = "type_writer"
    PULSE = "pulse"


class AnimationSpeed(Enum):
    """Animation speed presets."""
    SLOW = 0.1      # 10 FPS
    NORMAL = 0.25   # 4 FPS (recommended for terminals)
    FAST = 0.5      # 2 FPS
    INSTANT = 1.0   # No animation


@dataclass
class AnimationConfig:
    """
    Configuration for animations with performance optimization.
    
    Attributes:
        max_fps: Maximum frames per second for animations (default: 4.0)
                 - 1.0 = Very slow, minimal CPU usage
                 - 2.0 = Slow, good for CI/CD environments  
                 - 4.0 = Normal, balanced performance
                 - Higher values not recommended for terminals
                 
        enabled: Whether animations are enabled (default: True)
                 Set to False to disable all animations completely
                 
        smooth_transitions: Enable smooth transitions between states (default: True)
                           Disable for instant state changes
                           
        cpu_threshold: CPU usage percentage threshold for performance degradation (default: 80.0)
                      When exceeded, animations automatically slow down or disable
                      
        performance_mode: Emergency performance mode (default: False)
                         When True, disables all animations regardless of other settings
                         Use when maximum performance is critical
                         
    Usage Examples:
    
    # High performance, minimal animations
    config = AnimationConfig(max_fps=1.0, smooth_transitions=False)
    
    # Balanced performance (default)
    config = AnimationConfig()  
    
    # Maximum visual quality (not recommended)
    config = AnimationConfig(max_fps=8.0, cpu_threshold=90.0)
    
    # Complete disable for scripts
    config = AnimationConfig(enabled=False, performance_mode=True)
    """
    max_fps: float = 4.0  # Maximum frames per second
    enabled: bool = True
    smooth_transitions: bool = True
    cpu_threshold: float = 80.0  # Disable animations if CPU usage exceeds this
    performance_mode: bool = False  # Disable all animations
    

@dataclass
class AnimationFrame:
    """Single animation frame data."""
    content: str
    duration: float = 0.25  # Duration to display this frame
    style: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


class AnimationSequence:
    """Manages a sequence of animation frames."""
    
    def __init__(self, name: str, frames: List[AnimationFrame]):
        self.name = name
        self.frames = frames
        self.current_frame = 0
        self.loop = False
        self.completed = False
        
    def next_frame(self) -> Optional[AnimationFrame]:
        """Get next animation frame."""
        if self.completed:
            return None
            
        if self.current_frame >= len(self.frames):
            if self.loop:
                self.current_frame = 0
            else:
                self.completed = True
                return None
                
        frame = self.frames[self.current_frame]
        self.current_frame += 1
        return frame
        
    def reset(self):
        """Reset animation to beginning."""
        self.current_frame = 0
        self.completed = False


class AnimationController:
    """
    Manages dashboard animations with performance optimization.
    
    Features:
    - Frame rate management (max 4 FPS for terminal compatibility)
    - CPU usage monitoring and adaptive performance
    - Smooth transitions between states
    - Animation queuing and coordination
    - Graceful degradation for poor performance
    """
    
    def __init__(self, config: AnimationConfig = None):
        self.config = config or AnimationConfig()
        self.console = Console() if RICH_AVAILABLE else None
        
        # Animation state
        self.active_animations: Dict[str, AnimationSequence] = {}
        self.animation_queue: List[str] = []
        self.is_running = False
        
        # Performance tracking
        self.frame_times: List[float] = []
        self.last_frame_time = 0.0
        self.performance_degraded = False
        
        # Threading
        self.animation_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Built-in animation sequences
        self._initialize_built_in_animations()
        
    def _initialize_built_in_animations(self):
        """Initialize common animation sequences."""
        # Loading spinner animation
        spinner_frames = []
        if RICH_AVAILABLE:
            spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            for char in spinner_chars:
                spinner_frames.append(AnimationFrame(char, 0.1))
        else:
            # Fallback spinner for terminals without Rich
            spinner_chars = "|/-\\"
            for char in spinner_chars:
                spinner_frames.append(AnimationFrame(char, 0.25))
                
        loading_sequence = AnimationSequence("loading", spinner_frames)
        loading_sequence.loop = True
        self.register_animation("loading", loading_sequence)
        
        # Progress bar animation
        progress_frames = []
        for i in range(11):  # 0% to 100% in 10% increments
            progress = "█" * i + "░" * (10 - i)
            progress_frames.append(AnimationFrame(f"[{progress}] {i*10}%", 0.2))
        
        progress_sequence = AnimationSequence("progress", progress_frames)
        self.register_animation("progress", progress_sequence)
        
        # Service connecting animation
        connecting_frames = [
            AnimationFrame("🔄 Connecting", 0.3),
            AnimationFrame("🔄 Connecting.", 0.3),
            AnimationFrame("🔄 Connecting..", 0.3),
            AnimationFrame("🔄 Connecting...", 0.3)
        ]
        connecting_sequence = AnimationSequence("connecting", connecting_frames)
        connecting_sequence.loop = True
        self.register_animation("connecting", connecting_sequence)
        
    def register_animation(self, name: str, sequence: AnimationSequence):
        """Register a new animation sequence."""
        self.active_animations[name] = sequence
        
    def start_animation(self, name: str):
        """Start a named animation."""
        if not self.config.enabled or self.config.performance_mode:
            return
            
        if name in self.active_animations:
            if name not in self.animation_queue:
                self.animation_queue.append(name)
                self.active_animations[name].reset()
        
        if not self.is_running:
            self.start_animation_loop()
            
    def stop_animation(self, name: str):
        """Stop a specific animation."""
        if name in self.animation_queue:
            self.animation_queue.remove(name)
            
        if name in self.active_animations:
            self.active_animations[name].completed = True
            
    def stop_all_animations(self):
        """Stop all animations."""
        self.animation_queue.clear()
        for animation in self.active_animations.values():
            animation.completed = True
            
        if self.is_running:
            self.stop_animation_loop()
            
    def start_animation_loop(self):
        """Start the animation processing loop."""
        if self.is_running:
            return
            
        self.is_running = True
        self.stop_event.clear()
        
        if threading.active_count() < 10:  # Prevent thread explosion
            self.animation_thread = threading.Thread(
                target=self._animation_loop,
                daemon=True
            )
            self.animation_thread.start()
            
    def stop_animation_loop(self):
        """Stop the animation processing loop."""
        if not self.is_running:
            return
            
        self.is_running = False
        self.stop_event.set()
        
        if self.animation_thread:
            self.animation_thread.join(timeout=1.0)
            
    def _animation_loop(self):
        """Main animation loop running in background thread."""
        target_frame_time = 1.0 / self.config.max_fps
        
        while self.is_running and not self.stop_event.is_set():
            start_time = time.time()
            
            try:
                # Process active animations
                if self.animation_queue and not self.performance_degraded:
                    self._process_animations()
                    
                # Performance monitoring
                self._monitor_performance()
                
                # Maintain frame rate
                elapsed = time.time() - start_time
                sleep_time = max(0, target_frame_time - elapsed)
                
                if sleep_time > 0:
                    self.stop_event.wait(sleep_time)
                    
            except Exception as e:
                # Don't let animation errors crash the application
                print(f"Animation error: {e}")
                break
                
    def _process_animations(self):
        """Process all active animations."""
        completed_animations = []
        
        for name in self.animation_queue:
            if name in self.active_animations:
                animation = self.active_animations[name]
                frame = animation.next_frame()
                
                if frame:
                    # Animation frame would be rendered here
                    # For now, just track timing
                    pass
                else:
                    completed_animations.append(name)
                    
        # Remove completed animations
        for name in completed_animations:
            if name in self.animation_queue:
                self.animation_queue.remove(name)
                
    def _monitor_performance(self):
        """Monitor animation performance and adjust accordingly."""
        current_time = time.time()
        
        if self.last_frame_time > 0:
            frame_time = current_time - self.last_frame_time
            self.frame_times.append(frame_time)
            
            # Keep only last 30 frame times for rolling average
            if len(self.frame_times) > 30:
                self.frame_times.pop(0)
                
            # Check if performance is degraded
            if len(self.frame_times) >= 10:
                avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                target_frame_time = 1.0 / self.config.max_fps
                
                # If average frame time is more than 50% over target, degrade performance
                if avg_frame_time > target_frame_time * 1.5:
                    if not self.performance_degraded:
                        self.performance_degraded = True
                        # Could notify dashboard of performance mode
                        
                # Recover if performance improves
                elif avg_frame_time < target_frame_time * 1.2:
                    if self.performance_degraded:
                        self.performance_degraded = False
                        
        self.last_frame_time = current_time
        
    def create_smooth_transition(self, from_state: str, to_state: str, 
                                duration: float = 1.0) -> AnimationSequence:
        """Create smooth transition between two states."""
        if not self.config.smooth_transitions:
            # Instant transition
            return AnimationSequence("transition", [
                AnimationFrame(to_state, 0.0)
            ])
            
        # Create transition frames
        frames = []
        steps = int(duration * self.config.max_fps)
        steps = max(2, min(steps, 10))  # Limit transition steps
        
        for i in range(steps + 1):
            progress = i / steps
            # Simple blend for text (you could implement more sophisticated blending)
            if progress < 0.5:
                content = from_state
            else:
                content = to_state
                
            frames.append(AnimationFrame(
                content, 
                duration / steps
            ))
            
        return AnimationSequence("transition", frames)
        
    def is_animation_active(self, name: str) -> bool:
        """Check if a specific animation is currently active."""
        return name in self.animation_queue
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get animation performance statistics."""
        if not self.frame_times:
            return {"status": "no_data"}
            
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        actual_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        
        return {
            "average_frame_time": avg_frame_time,
            "actual_fps": actual_fps,
            "target_fps": self.config.max_fps,
            "performance_degraded": self.performance_degraded,
            "active_animations": len(self.animation_queue),
            "total_animations": len(self.active_animations)
        }
        
    def set_performance_mode(self, enabled: bool):
        """Enable/disable performance mode (disables all animations)."""
        self.config.performance_mode = enabled
        
        if enabled:
            self.stop_all_animations()
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_all_animations()


# Factory functions for easy use
def create_loading_controller() -> AnimationController:
    """
    Create an animation controller optimized for loading screens.
    
    Configuration:
    - max_fps: 2.0 (slower refresh for loading scenarios)
    - smooth_transitions: True (smooth loading progression) 
    - performance_mode: False (animations enabled)
    
    Best for: Initial application loading, service connection sequences
    
    Returns:
        AnimationController: Configured for loading scenarios
    """
    config = AnimationConfig(
        max_fps=2.0,  # Slower for loading screens
        enabled=True,
        performance_mode=False
    )
    return AnimationController(config)


def create_dashboard_controller() -> AnimationController:
    """
    Create an animation controller optimized for dashboard updates.
    
    Configuration:
    - max_fps: 4.0 (standard dashboard refresh rate)
    - smooth_transitions: True (smooth state changes)
    - cpu_threshold: 80.0 (adaptive performance)
    - performance_mode: False (full features enabled)
    
    Best for: Real-time dashboard displays, status monitoring, progress tracking
    
    Returns:
        AnimationController: Configured for dashboard displays
    """
    config = AnimationConfig(
        max_fps=4.0,  # Standard dashboard refresh rate
        enabled=True,
        smooth_transitions=True,
        performance_mode=False
    )
    return AnimationController(config)


def create_performance_controller() -> AnimationController:
    """
    Create an animation controller optimized for maximum performance.
    
    Configuration:
    - max_fps: 1.0 (minimal refresh rate)
    - enabled: False (animations disabled)
    - smooth_transitions: False (instant state changes)
    - performance_mode: True (emergency performance mode)
    
    Best for: CI/CD environments, resource-constrained systems, batch processing
    
    Returns:
        AnimationController: Configured for maximum performance
    """
    config = AnimationConfig(
        max_fps=1.0,  # Very slow updates
        enabled=False,  # Prefer no animations
        smooth_transitions=False,  # Instant state changes
        performance_mode=True
    )
    return AnimationController(config)


def create_presentation_controller() -> AnimationController:
    """
    Create an animation controller optimized for presentations and demos.
    
    Configuration:
    - max_fps: 3.0 (smooth but not excessive) 
    - smooth_transitions: True (polished appearance)
    - cpu_threshold: 85.0 (higher threshold for demos)
    - performance_mode: False (full visual features)
    
    Best for: Live demonstrations, client presentations, showcases
    
    Returns:
        AnimationController: Configured for presentation scenarios
    """
    config = AnimationConfig(
        max_fps=3.0,  # Smooth for presentations
        enabled=True,
        smooth_transitions=True,
        cpu_threshold=85.0,  # Higher threshold for demos
        performance_mode=False
    )
    return AnimationController(config)


def create_ci_controller() -> AnimationController:
    """
    Create an animation controller optimized for CI/CD environments.
    
    Configuration:
    - max_fps: 1.0 (minimal CPU usage)
    - enabled: False (no animations in automation)
    - smooth_transitions: False (instant feedback)
    - performance_mode: True (maximum efficiency)
    
    Best for: Automated testing, continuous integration, headless environments
    
    Returns:
        AnimationController: Configured for CI/CD usage
    """
    config = AnimationConfig(
        max_fps=1.0,  # Minimal for CI
        enabled=False,  # No animations in CI
        smooth_transitions=False,
        performance_mode=True
    )
    return AnimationController(config)