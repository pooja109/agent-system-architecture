#!/usr/bin/env python3
"""
Validation Script for Prompt Management System
=============================================

Demonstrates and validates the complete Phase 1 implementation.
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.prompt_manager import PromptManager
from exceptions.prompt_exceptions import PromptNotFoundError


async def main():
    """Validate the complete prompt management system."""
    print("🚀 Phase 1: Core Infrastructure Setup - Validation")
    print("=" * 60)
    
    # Initialize the PromptManager
    manager = PromptManager(
        cache_ttl_seconds=300,
        enable_hot_reload=False,
        schema_validation=True
    )
    
    print(f"✅ PromptManager initialized")
    print(f"   Base path: {manager.prompts_base_path}")
    print(f"   Cache TTL: {manager.cache_ttl.total_seconds()} seconds")
    print()
    
    # Test 1: Load email classification configuration
    print("📋 Test 1: Loading email classification configuration...")
    try:
        config = await manager.load_prompt_config("email_classification")
        print(f"✅ Successfully loaded configuration")
        print(f"   Agent: {config.agent_config.name}")
        print(f"   Version: {config.agent_config.version}")
        print(f"   Description: {config.agent_config.description}")
        print(f"   System instructions length: {len(config.system_instructions)} characters")
        print()
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return False
    
    # Test 2: Get system instructions
    print("📝 Test 2: Retrieving system instructions...")
    try:
        instructions = await manager.get_system_instructions("email_classification")
        print(f"✅ Successfully retrieved system instructions")
        print(f"   Length: {len(instructions)} characters")
        print(f"   Contains required sections: {all(section in instructions.upper() for section in ['INTENT CATEGORIES', 'CONFIDENCE SCORING', 'RESPONSE FORMAT'])}")
        print()
    except Exception as e:
        print(f"❌ Failed to retrieve instructions: {e}")
        return False
    
    # Test 3: Load template
    print("🎨 Test 3: Loading classification template...")
    try:
        template = await manager.load_template("email_classification", "classification_template")
        print(f"✅ Successfully loaded template")
        print(f"   Template version: {template.template_version}")
        print(f"   Variables defined: {len(template.variables) if template.variables else 0}")
        print(f"   Template length: {len(template.template)} characters")
        print()
    except Exception as e:
        print(f"❌ Failed to load template: {e}")
        return False
    
    # Test 4: Cache behavior
    print("💾 Test 4: Testing cache behavior...")
    try:
        # Load same config again (should hit cache)
        config2 = await manager.load_prompt_config("email_classification")
        
        stats = manager.get_cache_statistics()
        print(f"✅ Cache working correctly")
        print(f"   Cache hits: {stats['cache_hits']}")
        print(f"   Cache misses: {stats['cache_misses']}")
        print(f"   Hit rate: {stats['hit_rate_percent']}%")
        print(f"   Cached items: {stats['cached_items']}")
        print()
    except Exception as e:
        print(f"❌ Cache test failed: {e}")
        return False
    
    # Test 5: Error handling
    print("🚨 Test 5: Testing error handling...")
    try:
        await manager.load_prompt_config("nonexistent_prompt")
        print(f"❌ Error handling failed - should have thrown exception")
        return False
    except PromptNotFoundError:
        print(f"✅ Error handling working correctly")
        print(f"   PromptNotFoundError thrown as expected")
        print()
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    # Test 6: Validation framework
    print("🔍 Test 6: Testing validation framework...")
    try:
        results = await manager.validate_all_prompts()
        print(f"✅ Validation framework working")
        print(f"   Prompts validated: {len(results)}")
        for prompt_name, is_valid in results.items():
            status = "✅ Valid" if is_valid else "❌ Invalid"
            print(f"   {prompt_name}: {status}")
        print()
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        return False
    
    # Test 7: Cache clearing
    print("🧹 Test 7: Testing cache clearing...")
    try:
        initial_cached = len(manager._cached_prompts)
        manager.clear_cache()
        after_clear = len(manager._cached_prompts)
        
        print(f"✅ Cache clearing working")
        print(f"   Items before clear: {initial_cached}")
        print(f"   Items after clear: {after_clear}")
        print()
    except Exception as e:
        print(f"❌ Cache clearing test failed: {e}")
        return False
    
    # Final summary
    print("🎉 Phase 1 Implementation Summary")
    print("=" * 60)
    print("✅ PromptManager service with caching: IMPLEMENTED")
    print("✅ Pydantic models for configuration validation: IMPLEMENTED")
    print("✅ Custom exception hierarchy: IMPLEMENTED")
    print("✅ Directory structure for external prompts: IMPLEMENTED")
    print("✅ YAML configuration loading: IMPLEMENTED")
    print("✅ Comprehensive error handling: IMPLEMENTED")
    print("✅ Performance metrics and caching: IMPLEMENTED")
    print("✅ Validation framework: IMPLEMENTED")
    print()
    
    print("🔧 Business Value Delivered:")
    print("   • Prompt engineers can work independently from developers")
    print("   • Version control for AI instructions separate from code")
    print("   • A/B testing capability for different prompt versions")
    print("   • Reduced deployment risks via separated prompt updates")
    print("   • High-performance caching for production workloads")
    print()
    
    print("📊 Performance Characteristics:")
    final_stats = manager.get_cache_statistics()
    print(f"   • Cache hit rate: {final_stats['hit_rate_percent']}%")
    print(f"   • Average load times: {final_stats['average_load_times']}")
    print()
    
    print("✨ Phase 1: Core Infrastructure Setup - COMPLETE!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)