# ui/terminal/accessibility.py
import os
from typing import Dict, Any, Optional
from rich.console import Console

from .capability_detector import TerminalCapabilities


class AccessibilityManager:
    """Manages accessibility features and adaptations."""
    
    def __init__(self, console: Console):
        self.console = console
        self.capabilities = TerminalCapabilities()
        self.accessibility_mode = self.capabilities._detect_accessibility_mode()
    
    def is_accessibility_mode_enabled(self) -> bool:
        """Check if accessibility mode is enabled."""
        return self.accessibility_mode
    
    def get_accessibility_settings(self) -> Dict[str, Any]:
        """Get current accessibility settings."""
        return {
            'high_contrast': bool(os.getenv('HIGH_CONTRAST')),
            'no_color': bool(os.getenv('NO_COLOR') or os.getenv('MONOCHROME')),
            'screen_reader': bool(os.getenv('SCREEN_READER')),
            'accessibility_mode': bool(os.getenv('ACCESSIBILITY_MODE')),
            'large_text': bool(os.getenv('LARGE_TEXT')),
            'reduced_motion': bool(os.getenv('REDUCED_MOTION')),
        }
    
    def should_use_screen_reader_format(self) -> bool:
        """Determine if screen reader friendly format should be used."""
        return (
            bool(os.getenv('SCREEN_READER')) or
            bool(os.getenv('ACCESSIBILITY_MODE'))
        )
    
    def should_reduce_visual_effects(self) -> bool:
        """Determine if visual effects should be reduced."""
        return (
            self.accessibility_mode or
            bool(os.getenv('REDUCED_MOTION')) or
            bool(os.getenv('NO_ANIMATION'))
        )
    
    def get_safe_characters(self) -> Dict[str, str]:
        """Get safe character alternatives for accessibility."""
        if self.accessibility_mode or not self.capabilities.should_use_unicode():
            # ASCII alternatives
            return {
                'checkmark': '[OK]',
                'cross': '[ERROR]',
                'warning': '[WARN]',
                'info': '[INFO]',
                'arrow_right': '->',
                'arrow_left': '<-',
                'bullet': '*',
                'progress': '.',
                'separator': '-'
            }
        else:
            # Unicode symbols
            return {
                'checkmark': '✅',
                'cross': '❌',
                'warning': '⚠️',
                'info': 'ℹ️',
                'arrow_right': '→',
                'arrow_left': '←',
                'bullet': '•',
                'progress': '●',
                'separator': '─'
            }
    
    def format_for_accessibility(self, text: str, 
                                include_description: bool = True) -> str:
        """Format text with accessibility considerations."""
        if not self.should_use_screen_reader_format():
            return text
        
        # Replace visual symbols with descriptive text
        replacements = {
            '✅': '[SUCCESS] ',
            '❌': '[ERROR] ',
            '⚠️': '[WARNING] ',
            'ℹ️': '[INFO] ',
            '🔄': '[IN PROGRESS] ',
            '📊': '[STATS] ',
            '⏱️': '[TIME] ',
            '⚡': '[SPEED] ',
            '📧': '[EMAIL] ',
            '🔍': '[CHECKING] '
        }
        
        formatted_text = text
        for symbol, replacement in replacements.items():
            formatted_text = formatted_text.replace(symbol, replacement)
        
        return formatted_text
    
    def get_color_alternatives(self) -> Dict[str, str]:
        """Get color alternatives for accessibility."""
        if self.accessibility_mode:
            # High contrast or no color alternatives
            settings = self.get_accessibility_settings()
            
            if settings['high_contrast']:
                return {
                    'success': 'bright_white',
                    'error': 'bright_white',
                    'warning': 'bright_white',
                    'info': 'bright_white',
                    'accent': 'bright_white',
                    'muted': 'bright_black'
                }
            else:
                return {
                    'success': 'white',
                    'error': 'white',
                    'warning': 'white',
                    'info': 'white',
                    'accent': 'white',
                    'muted': 'white'
                }
        
        # Standard colors for normal operation
        return {
            'success': 'bright_green',
            'error': 'bright_red',
            'warning': 'bright_yellow',
            'info': 'bright_blue',
            'accent': 'bright_cyan',
            'muted': 'bright_black'
        }
    
    def format_screen_reader_text(self, content: str, 
                                 element_type: str = "text",
                                 context: Optional[Dict[str, Any]] = None) -> str:
        """Format text specifically for screen reader compatibility."""
        if not self.should_use_screen_reader_format():
            return content
        
        # Add structural information for screen readers
        context = context or {}
        
        # Create screen reader friendly structure
        sr_text = []
        
        # Add heading level if provided
        if element_type == "heading":
            level = context.get('level', 1)
            sr_text.append(f"HEADING LEVEL {level}: ")
        elif element_type == "table":
            sr_text.append("TABLE: ")
        elif element_type == "list":
            sr_text.append("LIST: ")
        elif element_type == "progress":
            sr_text.append("PROGRESS INDICATOR: ")
        elif element_type == "status":
            sr_text.append("STATUS: ")
        elif element_type == "error":
            sr_text.append("ERROR MESSAGE: ")
        elif element_type == "warning":
            sr_text.append("WARNING: ")
        
        # Format the actual content
        formatted_content = self.format_for_accessibility(content)
        sr_text.append(formatted_content)
        
        # Add context information
        if context.get('total'):
            sr_text.append(f" ITEM {context.get('current', 1)} OF {context['total']}")
        
        if context.get('percentage'):
            sr_text.append(f" {context['percentage']}% COMPLETE")
        
        # Add navigation hints if provided
        if context.get('next_action'):
            sr_text.append(f" NEXT: {context['next_action']}")
        
        return "".join(sr_text)
    
    def create_alternative_progress_text(self, current: int, total: int, 
                                       operation: str = "operation") -> str:
        """Create text-based progress alternative for screen readers."""
        if not self.should_use_screen_reader_format():
            return f"{current}/{total}"
        
        percentage = int((current / total) * 100) if total > 0 else 0
        return f"PROGRESS: {operation} {current} of {total} items complete, {percentage} percent done"
    
    def format_table_for_accessibility(self, headers: list, rows: list) -> str:
        """Format tabular data for screen reader accessibility."""
        if not self.should_use_screen_reader_format():
            return "TABLE DATA"  # Fallback for normal display
        
        # Create screen reader friendly table description
        sr_table = [f"TABLE WITH {len(headers)} COLUMNS AND {len(rows)} ROWS"]
        
        # Add column headers
        sr_table.append(f"COLUMN HEADERS: {', '.join(headers)}")
        
        # Add each row with clear structure
        for i, row in enumerate(rows[:10]):  # Limit to first 10 rows
            row_text = f"ROW {i+1}: "
            for j, cell in enumerate(row):
                if j < len(headers):
                    row_text += f"{headers[j]} is {cell}, "
            sr_table.append(row_text.rstrip(', '))
        
        if len(rows) > 10:
            sr_table.append(f"AND {len(rows) - 10} MORE ROWS")
        
        return " ".join(sr_table)
    
    def create_keyboard_navigation_hints(self, available_actions: list) -> str:
        """Create keyboard navigation hints for screen readers."""
        if not self.should_use_screen_reader_format():
            return ""
        
        if not available_actions:
            return ""
        
        hints = ["KEYBOARD NAVIGATION: "]
        for action in available_actions:
            hints.append(f"{action}, ")
        
        return "".join(hints).rstrip(', ')
    
    def format_error_for_accessibility(self, error: Exception, 
                                     context: Optional[Dict[str, Any]] = None) -> str:
        """Format error messages for accessibility."""
        context = context or {}
        
        error_parts = []
        
        if self.should_use_screen_reader_format():
            error_parts.append("ERROR OCCURRED: ")
            error_parts.append(f"ERROR TYPE: {type(error).__name__}, ")
            error_parts.append(f"ERROR MESSAGE: {str(error)}")
            
            if context.get('operation'):
                error_parts.append(f", DURING OPERATION: {context['operation']}")
            
            if context.get('correlation_id'):
                error_parts.append(f", REFERENCE ID: {context['correlation_id']}")
            
            if context.get('suggestion'):
                error_parts.append(f", SUGGESTION: {context['suggestion']}")
            
        else:
            # Standard error format
            error_parts.append(f"❌ {type(error).__name__}: {str(error)}")
            
            if context.get('correlation_id'):
                error_parts.append(f" (ID: {context['correlation_id']})")
        
        return "".join(error_parts)
    
    def should_skip_animations(self) -> bool:
        """Determine if animations should be skipped for accessibility."""
        return (
            self.accessibility_mode or
            bool(os.getenv('REDUCED_MOTION')) or
            bool(os.getenv('NO_ANIMATION')) or
            bool(os.getenv('SCREEN_READER'))
        )
    
    def get_motion_preferences(self) -> Dict[str, bool]:
        """Get motion and animation preferences."""
        return {
            'skip_animations': self.should_skip_animations(),
            'reduce_motion': bool(os.getenv('REDUCED_MOTION')),
            'no_blinking': bool(os.getenv('NO_BLINKING')),
            'static_progress': self.should_use_screen_reader_format()
        }
    
    def create_status_announcement(self, status_type: str, message: str,
                                 additional_info: Optional[Dict[str, Any]] = None) -> str:
        """Create status announcements suitable for screen readers."""
        additional_info = additional_info or {}
        
        if not self.should_use_screen_reader_format():
            return message
        
        announcement_parts = []
        
        # Add status type announcement
        status_announcements = {
            'success': "SUCCESS ANNOUNCEMENT: ",
            'error': "ERROR ANNOUNCEMENT: ",
            'warning': "WARNING ANNOUNCEMENT: ",
            'info': "INFORMATION ANNOUNCEMENT: ",
            'progress': "PROGRESS UPDATE: ",
            'completion': "COMPLETION ANNOUNCEMENT: "
        }
        
        announcement_parts.append(status_announcements.get(status_type, "STATUS: "))
        announcement_parts.append(self.format_for_accessibility(message))
        
        # Add timing information if available
        if additional_info.get('timestamp'):
            announcement_parts.append(f" AT TIME {additional_info['timestamp']}")
        
        if additional_info.get('duration'):
            announcement_parts.append(f" DURATION {additional_info['duration']} SECONDS")
        
        return "".join(announcement_parts)
    
    def get_accessibility_summary(self) -> Dict[str, Any]:
        """Get summary of current accessibility settings and capabilities."""
        settings = self.get_accessibility_settings()
        
        return {
            **settings,
            'safe_characters_active': self.accessibility_mode or not self.capabilities.should_use_unicode(),
            'screen_reader_format_active': self.should_use_screen_reader_format(),
            'visual_effects_reduced': self.should_reduce_visual_effects(),
            'animations_skipped': self.should_skip_animations(),
            'color_alternatives_active': self.accessibility_mode,
            'terminal_accessibility_score': self._calculate_accessibility_score()
        }
    
    def _calculate_accessibility_score(self) -> int:
        """Calculate an accessibility score based on current settings."""
        score = 0
        settings = self.get_accessibility_settings()
        
        if settings['screen_reader']:
            score += 30
        if settings['high_contrast']:
            score += 25
        if settings['no_color']:
            score += 20
        if settings['accessibility_mode']:
            score += 15
        if settings['reduced_motion']:
            score += 10
        
        return min(score, 100)  # Cap at 100