#!/usr/bin/env python3
"""
Test script to validate customer analytics integration.
This script tests the new customer analytics calculation functionality.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test imports
try:
    from utils.customer_analytics import CustomerAnalyticsCalculator, calculate_customer_analytics
    from database.scenario_tracking_models import ScenarioProcessingRecord
    print("✅ Imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)


class MockEmail:
    """Mock email data for testing."""
    def __init__(self, sender_email: str = "test.customer@example.com"):
        self.id = "test-email-123"
        self.sender_email = sender_email
        self.subject = "Test Email Subject"
        self.received_datetime = datetime.now(timezone.utc)
        self.body = "Test email body content"
        self.recipient_emails = ["support@company.com"]


class MockProcessingResult:
    """Mock processing result for testing."""
    def __init__(self):
        self.process_id = "test-process-123"
        self.success = True
        self.processing_duration_ms = 25000


class MockScenarioResult:
    """Mock scenario result for testing."""
    def __init__(self):
        self.scenario_type = "scenario_5"
        self.success = True
        self.expert_assigned = "Test Expert"
        self.case_created = "SF-TEST-123"


async def test_customer_analytics_calculator():
    """Test the customer analytics calculator directly."""
    print("\n🔍 Testing CustomerAnalyticsCalculator...")
    
    calculator = CustomerAnalyticsCalculator()
    
    # Test with a mock customer
    try:
        analytics = await calculator.calculate_customer_analytics(
            customer_email="test.customer@example.com",
            current_scenario_type="scenario_5",
            lookback_days=90
        )
        
        print(f"✅ Analytics calculated successfully:")
        print(f"   - Customer interaction count: {analytics['customer_interaction_count']}")
        print(f"   - Last interaction: {analytics['last_customer_interaction']}")
        print(f"   - Scenario history: {analytics['customer_scenario_history']}")
        
        # Validate expected fields
        required_fields = ['customer_interaction_count', 'last_customer_interaction', 'customer_scenario_history']
        for field in required_fields:
            if field not in analytics:
                print(f"❌ Missing required field: {field}")
                return False
            
        return True
        
    except Exception as e:
        print(f"❌ Customer analytics calculation failed: {e}")
        return False


async def test_scenario_record_creation():
    """Test that scenario record creation includes real customer analytics."""
    print("\n🔍 Testing ScenarioProcessingRecord creation with customer analytics...")
    
    try:
        # Create mock data
        email_data = MockEmail("integration.test@example.com")
        processing_result = MockProcessingResult()
        scenario_result = MockScenarioResult()
        
        # Test the new async record creation
        record = await ScenarioProcessingRecord.from_processing_results(
            email_data=email_data,
            processing_result=processing_result,
            scenario_result=scenario_result
        )
        
        print(f"✅ Record created successfully:")
        print(f"   - Processing ID: {record.processing_id}")
        print(f"   - Sender email: {record.sender_email}")
        print(f"   - Customer interaction count: {record.customer_interaction_count}")
        print(f"   - Last interaction: {record.last_customer_interaction}")
        print(f"   - Scenario history: {record.customer_scenario_history}")
        
        # Validate customer analytics fields
        if record.customer_interaction_count is None:
            print("❌ Customer interaction count is None")
            return False
            
        if record.last_customer_interaction is None:
            print("❌ Last customer interaction is None")
            return False
            
        if not record.customer_scenario_history:
            print("❌ Customer scenario history is empty")
            return False
            
        print("✅ All customer analytics fields populated correctly")
        return True
        
    except Exception as e:
        print(f"❌ Record creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_fallback_behavior():
    """Test fallback behavior when customer lookup fails."""
    print("\n🔍 Testing fallback behavior...")
    
    try:
        # Test with invalid email to trigger fallback
        calculator = CustomerAnalyticsCalculator()
        analytics = await calculator.calculate_customer_analytics(
            customer_email="",  # Invalid email should trigger fallback
            current_scenario_type="scenario_5"
        )
        
        print(f"✅ Fallback analytics:")
        print(f"   - Customer interaction count: {analytics['customer_interaction_count']}")
        print(f"   - Scenario history: {analytics['customer_scenario_history']}")
        
        # Fallback should provide safe defaults
        if analytics['customer_interaction_count'] != 1:
            print("❌ Fallback interaction count should be 1")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Fallback test failed: {e}")
        return False


async def test_integration_end_to_end():
    """Test the complete integration end-to-end."""
    print("\n🔍 Testing end-to-end integration...")
    
    try:
        from utils.data_transformation import ScenarioDataTransformer
        
        # Create transformer and test async record creation
        transformer = ScenarioDataTransformer()
        
        email_data = MockEmail("endtoend.test@example.com")
        processing_result = MockProcessingResult()
        scenario_result = MockScenarioResult()
        
        # This should now use the new async customer analytics
        record = await transformer.create_tracking_record(
            email_data=email_data,
            processing_result=processing_result,
            scenario_result=scenario_result,
            correlation_id="test-correlation-123"
        )
        
        print(f"✅ End-to-end record creation successful:")
        print(f"   - Customer: {record.sender_email}")
        print(f"   - Interactions: {record.customer_interaction_count}")
        print(f"   - History: {record.customer_scenario_history}")
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting Customer Analytics Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Customer Analytics Calculator", test_customer_analytics_calculator),
        ("Scenario Record Creation", test_scenario_record_creation),
        ("Fallback Behavior", test_fallback_behavior),
        ("End-to-End Integration", test_integration_end_to_end)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests PASSED! Customer analytics integration is working correctly.")
        return True
    else:
        print("⚠️  Some tests FAILED. Please review the implementation.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)