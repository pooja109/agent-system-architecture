"""
Customer Analytics Calculator
============================

Calculates real customer interaction analytics based on historical data in the scenario tracking table.
Replaces hardcoded defaults with actual customer metrics.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)


class CustomerAnalyticsCalculator:
    """
    Calculates customer analytics metrics based on historical interaction data.
    
    This service provides real-time calculation of:
    - Customer interaction count
    - Last customer interaction timestamp  
    - Customer scenario history
    
    Used during scenario processing record creation to replace hardcoded defaults
    with actual customer analytics.
    """
    
    def __init__(self, scenario_tracking_client=None):
        """
        Initialize the customer analytics calculator.
        
        Args:
            scenario_tracking_client: Optional pre-configured client.
                                    If None, will use dependency injection.
        """
        self.scenario_tracking_client = scenario_tracking_client
        self._logger = logger.bind(component="customer_analytics")
    
    async def calculate_customer_analytics(
        self, 
        customer_email: str,
        current_scenario_type: str = "unknown",
        lookback_days: int = 365
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive customer analytics based on historical data.
        
        Args:
            customer_email: Customer email address to analyze
            current_scenario_type: Current scenario being processed
            lookback_days: Number of days to look back for history (default: 1 year)
            
        Returns:
            Dict containing calculated analytics:
            {
                'customer_interaction_count': int,
                'last_customer_interaction': datetime,
                'customer_scenario_history': List[str]
            }
        """
        self._logger.info(
            "Calculating customer analytics",
            customer_email=customer_email,
            scenario_type=current_scenario_type,
            lookback_days=lookback_days
        )
        
        try:
            # Get customer interaction history
            history = await self._get_customer_history(customer_email, lookback_days)
            
            if not history or history.total_interactions == 0:
                # First-time customer - return initial values
                return self._build_first_time_customer_analytics(current_scenario_type)
            
            # Calculate analytics from historical data
            analytics = self._calculate_from_history(history, current_scenario_type)
            
            self._logger.info(
                "Customer analytics calculated successfully",
                customer_email=customer_email,
                interaction_count=analytics['customer_interaction_count'],
                scenario_history_length=len(analytics['customer_scenario_history'])
            )
            
            return analytics
            
        except Exception as e:
            self._logger.error(
                "Failed to calculate customer analytics, using fallback",
                customer_email=customer_email,
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Return safe fallback values
            return self._build_fallback_analytics(current_scenario_type)
    
    async def _get_customer_history(self, customer_email: str, lookback_days: int):
        """Get customer interaction history from the tracking service."""
        try:
            # If no client provided, get it through dependency injection
            if self.scenario_tracking_client is None:
                from services.scenario_tracking_client import ScenarioTrackingClient
                async with ScenarioTrackingClient() as client:
                    return await client.get_customer_interaction_history(
                        customer_email=customer_email,
                        days_back=lookback_days,
                        limit=100  # Reasonable limit for analytics calculation
                    )
            else:
                return await self.scenario_tracking_client.get_customer_interaction_history(
                    customer_email=customer_email,
                    days_back=lookback_days,
                    limit=100
                )
                
        except Exception as e:
            self._logger.warning(
                "Failed to retrieve customer history",
                customer_email=customer_email,
                error=str(e)
            )
            return None
    
    def _calculate_from_history(self, history, current_scenario_type: str) -> Dict[str, Any]:
        """Calculate analytics from customer interaction history."""
        
        # Calculate interaction count (total + 1 for current interaction)
        customer_interaction_count = history.total_interactions + 1
        
        # Get last interaction timestamp (most recent from history)
        last_customer_interaction = history.last_interaction
        
        # Build scenario history in chronological order (most recent first)
        # The history.interactions are already ordered by processed_at DESC
        scenario_history = []
        seen_scenarios = set()
        
        # Add current scenario first (most recent)
        if current_scenario_type:
            normalized_current = self._normalize_scenario_type(current_scenario_type)
            scenario_history.append(normalized_current)
            seen_scenarios.add(normalized_current)
        
        # Add scenarios from history in chronological order (most recent first)
        # Skip duplicates to maintain unique list while preserving order
        if hasattr(history, 'interactions') and history.interactions:
            for interaction in history.interactions:
                scenario_type = interaction.get('scenario_type')
                if scenario_type:
                    normalized_scenario = self._normalize_scenario_type(scenario_type)
                    if normalized_scenario not in seen_scenarios:
                        scenario_history.append(normalized_scenario)
                        seen_scenarios.add(normalized_scenario)
        else:
            # Fallback: use scenario_types list but we lose chronological order
            # This preserves existing behavior for older data structures
            for scenario in history.scenario_types:
                normalized_scenario = self._normalize_scenario_type(scenario)
                if normalized_scenario not in seen_scenarios:
                    scenario_history.append(normalized_scenario)
                    seen_scenarios.add(normalized_scenario)
        
        # Limit scenario history to reasonable size (most recent 10 unique scenarios)
        if len(scenario_history) > 10:
            scenario_history = scenario_history[:10]  # Keep first 10 (most recent)
        
        return {
            'customer_interaction_count': customer_interaction_count,
            'last_customer_interaction': last_customer_interaction,
            'customer_scenario_history': scenario_history
        }
    
    def _normalize_scenario_type(self, scenario_type: str) -> str:
        """Normalize scenario type to consistent format."""
        if not scenario_type:
            return "unknown"
        
        scenario_str = str(scenario_type)
        
        # Handle different formats:
        # "ScenarioType.SCENARIO_5" -> "scenario_5"
        # "scenario_5" -> "scenario_5" (already correct)
        # "SCENARIO_5" -> "scenario_5"
        # "unknown" -> "unknown"
        
        if scenario_str.startswith("ScenarioType."):
            # Convert "ScenarioType.SCENARIO_5" to "scenario_5"
            return scenario_str.replace("ScenarioType.", "").lower()
        elif scenario_str.startswith("SCENARIO_"):
            # Convert "SCENARIO_5" to "scenario_5"
            return scenario_str.lower()
        else:
            # Already in correct format or is "unknown"
            return scenario_str.lower()
    
    def _build_first_time_customer_analytics(self, current_scenario_type: str) -> Dict[str, Any]:
        """Build analytics for first-time customers."""
        now = datetime.now(timezone.utc)
        
        # Normalize the current scenario type
        normalized_scenario = self._normalize_scenario_type(current_scenario_type) if current_scenario_type else "unknown"
        
        return {
            'customer_interaction_count': 1,  # First interaction
            'last_customer_interaction': now,  # No previous interaction
            'customer_scenario_history': [normalized_scenario]
        }
    
    def _build_fallback_analytics(self, current_scenario_type: str) -> Dict[str, Any]:
        """Build safe fallback analytics when calculation fails."""
        now = datetime.now(timezone.utc)
        
        # Normalize the current scenario type
        normalized_scenario = self._normalize_scenario_type(current_scenario_type) if current_scenario_type else "unknown"
        
        # Use conservative defaults that indicate limited data availability
        return {
            'customer_interaction_count': 1,  # Conservative estimate
            'last_customer_interaction': now,  # Current time as fallback
            'customer_scenario_history': [normalized_scenario]
        }


class CustomerAnalyticsIntegration:
    """
    Integration wrapper for customer analytics in the scenario processing pipeline.
    
    Provides easy integration with existing scenario data extraction without
    requiring major refactoring.
    """
    
    @classmethod
    async def enhance_record_with_customer_analytics(
        cls,
        record_data: Dict[str, Any],
        scenario_tracking_client=None
    ) -> Dict[str, Any]:
        """
        Enhance a scenario processing record with real customer analytics.
        
        Args:
            record_data: Scenario processing record data (mutable)
            scenario_tracking_client: Optional client for dependency injection
            
        Returns:
            Enhanced record data with calculated customer analytics
        """
        try:
            # Extract customer email and scenario type from record data
            customer_email = record_data.get('sender_email')
            scenario_type = record_data.get('scenario_type', 'unknown')
            
            if not customer_email:
                logger.warning("No customer email found for analytics calculation")
                return record_data
            
            # Create calculator and get analytics
            calculator = CustomerAnalyticsCalculator(scenario_tracking_client)
            analytics = await calculator.calculate_customer_analytics(
                customer_email=customer_email,
                current_scenario_type=scenario_type
            )
            
            # Update record data with calculated analytics
            record_data.update(analytics)
            
            logger.info(
                "Record enhanced with customer analytics",
                customer_email=customer_email,
                interaction_count=analytics['customer_interaction_count']
            )
            
            return record_data
            
        except Exception as e:
            logger.error(
                "Failed to enhance record with customer analytics",
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Return original record data if enhancement fails
            return record_data
    
    @classmethod
    async def batch_enhance_records(
        cls,
        records: List[Dict[str, Any]],
        scenario_tracking_client=None
    ) -> List[Dict[str, Any]]:
        """
        Enhance multiple records with customer analytics in batch.
        
        Args:
            records: List of scenario processing record data
            scenario_tracking_client: Optional shared client
            
        Returns:
            List of enhanced records
        """
        enhanced_records = []
        
        for record_data in records:
            enhanced_record = await cls.enhance_record_with_customer_analytics(
                record_data, scenario_tracking_client
            )
            enhanced_records.append(enhanced_record)
        
        return enhanced_records


# Utility functions for easy integration

async def calculate_customer_analytics(
    customer_email: str,
    current_scenario_type: str = "unknown",
    lookback_days: int = 365
) -> Dict[str, Any]:
    """
    Standalone function to calculate customer analytics.
    
    Convenience function for direct usage without class instantiation.
    """
    calculator = CustomerAnalyticsCalculator()
    return await calculator.calculate_customer_analytics(
        customer_email, current_scenario_type, lookback_days
    )


async def enhance_record_with_analytics(record_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to enhance a record with customer analytics.
    
    Convenience function for direct usage without class instantiation.
    """
    return await CustomerAnalyticsIntegration.enhance_record_with_customer_analytics(record_data)