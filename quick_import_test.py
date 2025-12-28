#!/usr/bin/env python3
"""
Quick import test without running the full application
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, '/workspace')

def test_core_imports():
    """Test core module imports"""
    print("Testing core module imports...")
    
    try:
        print("Testing runserver...")
        import runserver
        print("✅ runserver imported successfully")
        
        # Test key functions exist
        if hasattr(runserver, 'id_generator'):
            test_id = runserver.id_generator(10)
            print(f"✅ id_generator works: {test_id}")
        
        print("Testing email_system...")
        import email_system
        print("✅ email_system imported successfully")
        
        print("Testing email_transport...")
        import email_transport  
        print("✅ email_transport imported successfully")
        
        print("Testing email_security_tools...")
        import email_security_tools
        print("✅ email_security_tools imported successfully")
        
        print("Testing domain_manager...")
        import domain_manager
        print("✅ domain_manager imported successfully")
        
        print("Testing review_routes...")
        import review_routes
        print("✅ review_routes imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== opsechat Core Module Import Test ===\n")
    
    success = test_core_imports()
    
    if success:
        print("\n🎉 All core modules imported successfully!")
        print("✅ Basic functionality verification: PASSED")
    else:
        print("\n❌ Some imports failed")
        print("❌ Basic functionality verification: FAILED")
        sys.exit(1)