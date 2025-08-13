"""
Progress Tracking System - Monitors and Reports Execution Progress
"""

import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ProgressStage(Enum):
    """Execution stages for progress tracking."""
    INITIALIZING = "Initializing services"
    AUTHENTICATING = "Authenticating"
    FETCHING_EMAIL = "Fetching email"
    CLASSIFYING = "Classifying intent"
    PROCESSING = "Processing scenario"
    COMPLETING = "Completing"


@dataclass
class ProgressEvent:
    """Progress event data."""
    stage: ProgressStage
    scenario_id: Optional[int] = None
    progress: float = 0.0  # 0.0 to 1.0
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0


class ProgressTracker:
    """Tracks execution progress and provides updates."""
    
    def __init__(self, callback: Optional[Callable] = None, total_scenarios: int = 6):
        self.callback = callback
        self.stages = {}
        self.scenario_timings = {}
        self.current_scenario = None
        self.start_time = None
        self.events = []
        self.total_scenarios = total_scenarios
        self.completed_scenarios = 0
        
        # Historical timing data for estimation (from live mode analysis)
        self.estimated_scenario_times = {
            5: 12.0,  # Positive response - Salesforce case creation
            6: 9.0,   # Negative response - Email forwarding  
            7: 9.0,   # Service inquiry - Email forwarding
            8: 8.0,   # Out of office - Contact update
            9: 12.0,  # Invalid email - Case creation (similar to scenario 5)
            10: 8.0,  # No longer works - Contact removal
        }
    
    def start_execution(self):
        """Mark execution start."""
        self.start_time = time.time()
        self._emit_event(ProgressEvent(
            stage=ProgressStage.INITIALIZING,
            progress=0.0
        ))
    
    def start_scenario(self, scenario_id: int):
        """Mark scenario start."""
        self.current_scenario = scenario_id
        self.scenario_timings[scenario_id] = {
            'start': time.time(),
            'stages': {}
        }
        
        self._emit_event(ProgressEvent(
            stage=ProgressStage.FETCHING_EMAIL,
            scenario_id=scenario_id,
            progress=0.1
        ))
    
    def update_stage(self, stage: ProgressStage, progress: float = None):
        """Update current execution stage."""
        if self.current_scenario:
            timing = self.scenario_timings[self.current_scenario]
            timing['stages'][stage] = time.time()
            
            # Calculate automatic progress if not provided
            if progress is None:
                progress = self._calculate_progress(stage)
            
            self._emit_event(ProgressEvent(
                stage=stage,
                scenario_id=self.current_scenario,
                progress=progress
            ))
    
    def complete_scenario(self, scenario_id: int, success: bool = True):
        """Mark scenario completion."""
        if scenario_id in self.scenario_timings:
            timing = self.scenario_timings[scenario_id]
            timing['end'] = time.time()
            timing['duration'] = timing['end'] - timing['start']
            timing['success'] = success
        
        self.completed_scenarios += 1
        
        self._emit_event(ProgressEvent(
            stage=ProgressStage.COMPLETING,
            scenario_id=scenario_id,
            progress=1.0,
            message="Success" if success else "Failed"
        ))
        
        self.current_scenario = None
    
    def _calculate_progress(self, stage: ProgressStage) -> float:
        """Calculate progress based on stage."""
        stage_progress = {
            ProgressStage.INITIALIZING: 0.05,
            ProgressStage.AUTHENTICATING: 0.1,
            ProgressStage.FETCHING_EMAIL: 0.2,
            ProgressStage.CLASSIFYING: 0.5,
            ProgressStage.PROCESSING: 0.8,
            ProgressStage.COMPLETING: 1.0
        }
        return stage_progress.get(stage, 0.5)
    
    def estimate_remaining_time(self, pending_scenarios: List[int]) -> float:
        """Estimate remaining execution time in seconds."""
        if not pending_scenarios:
            return 0.0
        
        total_estimated = 0.0
        
        # Use historical data if available, otherwise use defaults
        for scenario_id in pending_scenarios:
            if scenario_id in self.estimated_scenario_times:
                total_estimated += self.estimated_scenario_times[scenario_id]
            else:
                total_estimated += 8.0  # Default scenario time
        
        # Adjust based on actual performance if we have data
        if self.scenario_timings:
            actual_durations = [
                t.get('duration', 0) for t in self.scenario_timings.values()
                if 'duration' in t
            ]
            if actual_durations:
                avg_actual = sum(actual_durations) / len(actual_durations)
                # Get average of estimated times for completed scenarios
                completed_scenario_ids = list(self.scenario_timings.keys())
                estimated_for_completed = [
                    self.estimated_scenario_times.get(sid, 8.0)
                    for sid in completed_scenario_ids
                ]
                if estimated_for_completed:
                    avg_estimated = sum(estimated_for_completed) / len(estimated_for_completed)
                    # Apply correction factor
                    correction_factor = avg_actual / avg_estimated if avg_estimated > 0 else 1.0
                    total_estimated *= correction_factor
        
        return total_estimated
    
    def get_progress_summary(self, pending_scenarios: List[int] = None) -> Dict[str, Any]:
        """Get comprehensive progress summary with time estimates."""
        if pending_scenarios is None:
            pending_scenarios = []
            
        remaining_time = self.estimate_remaining_time(pending_scenarios)
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        
        overall_progress = self.completed_scenarios / max(self.total_scenarios, 1)
        
        return {
            'elapsed_time': elapsed_time,
            'estimated_remaining_time': remaining_time,
            'estimated_total_time': elapsed_time + remaining_time,
            'overall_progress': overall_progress,
            'completed_scenarios': self.completed_scenarios,
            'total_scenarios': self.total_scenarios,
            'pending_scenarios': len(pending_scenarios),
            'current_scenario': self.current_scenario
        }
    
    def _emit_event(self, event: ProgressEvent):
        """Emit progress event."""
        self.events.append(event)
        
        if self.callback:
            try:
                self.callback(event)
            except Exception as e:
                # Don't let callback errors stop execution
                print(f"Progress callback error: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        if not self.start_time:
            return {}
        
        total_duration = time.time() - self.start_time
        scenarios_run = len(self.scenario_timings)
        scenarios_passed = sum(
            1 for t in self.scenario_timings.values()
            if t.get('success', False)
        )
        
        avg_duration = 0
        if scenarios_run > 0:
            avg_duration = sum(
                t.get('duration', 0)
                for t in self.scenario_timings.values()
            ) / scenarios_run
        
        return {
            'total_duration': total_duration,
            'scenarios_run': scenarios_run,
            'scenarios_passed': scenarios_passed,
            'success_rate': (scenarios_passed / max(scenarios_run, 1)) * 100,
            'avg_scenario_duration': avg_duration,
            'events_logged': len(self.events)
        }
    
    def get_scenario_metrics(self, scenario_id: int) -> Dict[str, Any]:
        """Get metrics for specific scenario."""
        if scenario_id not in self.scenario_timings:
            return {}
        
        timing = self.scenario_timings[scenario_id]
        stages = timing.get('stages', {})
        
        # Calculate stage durations
        stage_durations = {}
        prev_time = timing['start']
        for stage in sorted(stages.keys(), key=lambda s: stages[s]):
            stage_time = stages[stage]
            stage_durations[stage.value] = stage_time - prev_time
            prev_time = stage_time
        
        return {
            'duration': timing.get('duration', 0),
            'success': timing.get('success', False),
            'stage_durations': stage_durations
        }