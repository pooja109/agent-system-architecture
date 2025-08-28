# utils/logging/http_client_config.py
import logging
from typing import Dict, Any, Optional, List
import urllib3
import warnings

from .config import LoggingConfig


class HTTPClientLogSuppressor:
    """Manages HTTP client logging suppression and configuration."""
    
    def __init__(self, config: LoggingConfig):
        self.config = config
        self._original_levels: Dict[str, int] = {}
        self._configured = False
    
    def configure_http_client_logging(self) -> None:
        """Configure HTTP client logging based on configuration."""
        if self._configured:
            return
        
        try:
            self._suppress_azure_sdk_logging()
            self._suppress_urllib3_logging()
            self._suppress_requests_logging()
            self._suppress_http_client_logging()
            self._configure_debug_mode_exceptions()
            
            self._configured = True
            
        except Exception as e:
            # Don't let HTTP client configuration break the application
            logging.getLogger('utils.custom_logging.http_client_config').warning(
                f"Failed to configure HTTP client logging: {e}"
            )
    
    def _suppress_azure_sdk_logging(self) -> None:
        """Suppress Azure SDK HTTP logging."""
        if not getattr(self.config, 'suppress_azure_sdk', True):
            return
        
        azure_loggers = [
            'azure',
            'azure.core',
            'azure.core.pipeline',
            'azure.core.pipeline.policies',
            'azure.core.pipeline.policies.http_logging_policy',
            'azure.identity',
            'azure.identity._internal',
            'azure.identity._credentials',
            'azure.keyvault',
            'azure.keyvault.secrets',
            'azure.storage',
            'msal',
            'msal.token_cache',
            'msal.authority'
        ]
        
        for logger_name in azure_loggers:
            logger = logging.getLogger(logger_name)
            if logger.level == logging.NOTSET or logger.level < logging.WARNING:
                self._original_levels[logger_name] = logger.level
                logger.setLevel(logging.WARNING)
                logger.propagate = False
    
    def _suppress_urllib3_logging(self) -> None:
        """Suppress urllib3 HTTP logging."""
        if not getattr(self.config, 'suppress_urllib3', True):
            return
        
        urllib3_loggers = [
            'urllib3',
            'urllib3.connectionpool',
            'urllib3.poolmanager',
            'urllib3.util.retry'
        ]
        
        for logger_name in urllib3_loggers:
            logger = logging.getLogger(logger_name)
            if logger.level == logging.NOTSET or logger.level < logging.WARNING:
                self._original_levels[logger_name] = logger.level
                logger.setLevel(logging.WARNING)
                logger.propagate = False
        
        # Disable urllib3 warnings about unverified HTTPS requests if needed
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _suppress_requests_logging(self) -> None:
        """Suppress requests library logging."""
        if not getattr(self.config, 'disable_http_logging', True):
            return
        
        requests_loggers = [
            'requests',
            'requests.packages',
            'requests.packages.urllib3',
            'requests.adapters'
        ]
        
        for logger_name in requests_loggers:
            logger = logging.getLogger(logger_name)
            if logger.level == logging.NOTSET or logger.level < logging.WARNING:
                self._original_levels[logger_name] = logger.level
                logger.setLevel(logging.WARNING)
                logger.propagate = False
    
    def _suppress_http_client_logging(self) -> None:
        """Suppress other HTTP client logging."""
        if not getattr(self.config, 'disable_http_logging', True):
            return
        
        http_loggers = [
            'httpx',
            'httpcore',
            'aiohttp',
            'aiohttp.access'
        ]
        
        for logger_name in http_loggers:
            logger = logging.getLogger(logger_name)
            if logger.level == logging.NOTSET or logger.level < logging.WARNING:
                self._original_levels[logger_name] = logger.level
                logger.setLevel(logging.WARNING)
                logger.propagate = False
    
    def _configure_debug_mode_exceptions(self) -> None:
        """Configure exceptions for debug mode."""
        # In debug mode, we want to see HTTP details
        if (hasattr(self.config, 'console') and 
            hasattr(self.config.console, 'level') and 
            str(self.config.console.level).upper() == 'DEBUG'):
            
            # Re-enable critical HTTP loggers at INFO level for debug mode
            debug_http_loggers = [
                'azure.core.pipeline.policies.http_logging_policy',
                'urllib3.connectionpool'
            ]
            
            for logger_name in debug_http_loggers:
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.INFO)
                logger.propagate = True
    
    def restore_original_logging(self) -> None:
        """Restore original logging levels."""
        for logger_name, original_level in self._original_levels.items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(original_level)
            logger.propagate = True
        
        self._original_levels.clear()
        self._configured = False


def configure_azure_sdk_logging(verbose: bool = False) -> None:
    """Configure Azure SDK logging for clean output."""
    if verbose:
        # In verbose mode, show some Azure SDK info but not debug details
        logging.getLogger('azure').setLevel(logging.INFO)
        logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    else:
        # In normal mode, suppress most Azure SDK logging
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.getLogger('azure.identity').setLevel(logging.ERROR)  # Only errors from auth
    
    # Always suppress the most verbose Azure loggers
    verbose_azure_loggers = [
        'azure.core.pipeline.policies.http_logging_policy',
        'msal.token_cache',
        'azure.identity._internal'
    ]
    
    for logger_name in verbose_azure_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
        logging.getLogger(logger_name).propagate = False


def configure_graph_api_logging(verbose: bool = False) -> None:
    """Configure Microsoft Graph API logging."""
    # The Graph API calls use requests/urllib3, so this is covered by general HTTP suppression
    # But we can add specific Graph API logging if needed
    
    if verbose:
        # In verbose mode, show Graph API operations but not HTTP details
        logging.getLogger('services.graph_api_client').setLevel(logging.INFO)
    else:
        # In normal mode, show only important Graph API events
        logging.getLogger('services.graph_api_client').setLevel(logging.WARNING)


# Convenience function for quick setup
def quick_suppress_http_logging(debug_mode: bool = False) -> None:
    """Quickly suppress HTTP logging for clean CLI output."""
    if debug_mode:
        # In debug mode, show some HTTP info but suppress the most verbose
        logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
        logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.INFO)
    else:
        # Normal suppression
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)