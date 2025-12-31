#!/usr/bin/env python3
"""
Installation and Import Test Script for opsechat
Tests all core modules can be imported successfully
"""

import sys
import traceback

def test_imports():
    """Test all core module imports"""
    modules_to_test = [
        'runserver',
        'email_system', 
        'email_transport',
        'email_security_tools',
        'domain_manager'
    ]
    
    results = {}
    
    for module in modules_to_test:
        try:
            __import__(module)
            results[module] = "✅ SUCCESS"
            print(f"✅ {module}: Import successful")
        except Exception as e:
            results[module] = f"❌ FAILED: {str(e)}"
            print(f"❌ {module}: Import failed - {str(e)}")
            traceback.print_exc()
    
    return results

def test_basic_functionality():
    """Test basic functionality of core modules"""
    print("\n=== Testing Basic Functionality ===")
    
    try:
        # Test runserver helpers
        import runserver
        print("✅ runserver: Module loaded")
        
        # Test if main functions exist
        if hasattr(runserver, 'id_generator'):
            test_id = runserver.id_generator(10)
            print(f"✅ runserver: ID generator works - {test_id}")
        
        if hasattr(runserver, 'check_older_than'):
            print("✅ runserver: check_older_than function exists")
            
    except Exception as e:
        print(f"❌ runserver functionality test failed: {e}")
    
    try:
        # Test email system
        from email_system import EmailStorage
        storage = EmailStorage()
        print("✅ email_system: EmailStorage instantiated")
        
    except Exception as e:
        print(f"❌ email_system functionality test failed: {e}")
    
    try:
        # Test domain manager
        from domain_manager import DomainRotationManager
        manager = DomainRotationManager()
        print("✅ domain_manager: DomainRotationManager instantiated")
        
    except Exception as e:
        print(f"❌ domain_manager functionality test failed: {e}")

def main():
    print("=== opsechat Import and Basic Functionality Test ===\n")
    
    # Test imports
    print("=== Testing Module Imports ===")
    import_results = test_imports()
    
    # Test basic functionality
    test_basic_functionality()
    
    # Summary
    print("\n=== Test Summary ===")
    success_count = sum(1 for result in import_results.values() if "SUCCESS" in result)
    total_count = len(import_results)
    
    print(f"Import Tests: {success_count}/{total_count} passed")
    
    if success_count == total_count:
        print("🎉 All core modules import successfully!")
        return 0
    else:
        print("⚠️  Some modules failed to import")
        return 1

if __name__ == "__main__":
    sys.exit(main())