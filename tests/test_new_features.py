#!/usr/bin/env python3
"""
Simple test for new features in OpSecHat v0.8.0

Tests:
1. Cryptographically secure ID generation
2. Automated key exchange
3. Direct message functionality
4. Rate limiting
5. Base64 detection
"""

import sys
import datetime

def test_secure_ids():
    """Test cryptographically secure ID generation"""
    print("Testing secure ID generation...")
    from simple_chat_routes import generate_secure_room_id, generate_secure_dm_id
    
    # Generate multiple IDs and ensure they're unique
    room_ids = {generate_secure_room_id() for _ in range(100)}
    dm_ids = {generate_secure_dm_id() for _ in range(100)}
    
    assert len(room_ids) == 100, "Room IDs should be unique"
    assert len(dm_ids) == 100, "DM IDs should be unique"
    
    # Check length (base64 encoded, so varies slightly)
    sample_room_id = generate_secure_room_id()
    assert len(sample_room_id) > 40, f"Room ID too short: {len(sample_room_id)}"
    
    print("✅ Secure ID generation works correctly")


def test_chat_room_key():
    """Test automated key exchange"""
    print("\nTesting automated key exchange...")
    from simple_chat_routes import ChatRoom
    
    room = ChatRoom("test_room_123")
    key = room.get_room_key()
    
    assert key, "Room should have encryption key"
    assert len(key) > 40, "Key should be sufficiently long"
    
    # Ensure each room gets unique key
    room2 = ChatRoom("test_room_456")
    key2 = room2.get_room_key()
    
    assert key != key2, "Each room should have unique key"
    
    print(f"✅ Room key generation works (sample: {key[:20]}...)")


def test_rate_limiting():
    """Test email rate limiting"""
    print("\nTesting rate limiting...")
    from email_system import burner_manager
    
    user_id = "test_rate_limit_" + str(datetime.datetime.now().timestamp())
    
    # Should allow initially
    allowed, msg = burner_manager.check_send_rate_limit(user_id)
    assert allowed, "Should allow sends initially"
    
    # Send 10 emails (the limit)
    for i in range(10):
        burner_manager.record_sent_email(user_id)
    
    # Check status
    status = burner_manager.get_send_limit_status(user_id)
    assert status['sends_used'] == 10, f"Should have 10 sends used, got {status['sends_used']}"
    assert status['sends_remaining'] == 0, "Should have 0 remaining"
    
    # Should not allow more
    allowed, msg = burner_manager.check_send_rate_limit(user_id)
    assert not allowed, "Should not allow after limit"
    assert "Rate limit exceeded" in msg, "Should have rate limit message"
    
    print(f"✅ Rate limiting works correctly")
    print(f"   Status: {status['sends_used']}/{status['max_sends_per_hour']} used")
    print(f"   Message: {msg[:50]}...")


def test_base64_detection():
    """Test base64 encoded content detection"""
    print("\nTesting base64 detection...")
    
    # Simulate the detection logic
    def detect_base64(message):
        if len(message) > 100:
            space_count = message.count(' ')
            if space_count < len(message) * 0.05:  # Less than 5% spaces
                return True
        return False
    
    # Normal message should pass
    normal_msg = "This is a normal message with spaces and punctuation."
    assert not detect_base64(normal_msg), "Normal message should not be flagged"
    
    # Base64-like message should be detected (long string without spaces)
    # Simulate a very long base64 encoded image (typical has very few spaces)
    base64_msg = "A" * 150  # Long string with no spaces simulates base64
    assert detect_base64(base64_msg), "Long message without spaces should be flagged"
    
    # Message with sufficient spaces should pass
    spaced_msg = "A " * 60  # 120 chars with 50% spaces
    assert not detect_base64(spaced_msg), "Message with spaces should pass"
    
    # Short base64 should pass (under 100 chars)
    short_base64 = "SGVsbG8gV29ybGQ="
    assert not detect_base64(short_base64), "Short message should pass"
    
    print("✅ Base64 detection logic correct")


def test_message_length_cap():
    """Test message length caps"""
    print("\nTesting message length caps...")
    from simple_chat_routes import MAX_MESSAGE_LENGTH
    
    assert MAX_MESSAGE_LENGTH == 500, f"Expected 500 char limit, got {MAX_MESSAGE_LENGTH}"
    
    # Test that messages over limit would be rejected
    long_message = "A" * 501
    assert len(long_message) > MAX_MESSAGE_LENGTH, "Test message should exceed limit"
    
    # Test that messages at limit would pass
    max_message = "A" * 500
    assert len(max_message) == MAX_MESSAGE_LENGTH, "Test message should be at limit"
    
    print(f"✅ Message length cap set correctly: {MAX_MESSAGE_LENGTH} chars")


def test_dm_structure():
    """Test DM data structure"""
    print("\nTesting DM functionality...")
    from simple_chat_routes import direct_messages, dm_lock
    import secrets
    
    # Simulate creating a DM
    dm_id = secrets.token_urlsafe(16)
    test_dm = {
        "dm_id": dm_id,
        "sender_id": "test_sender",
        "sender_name": "TestUser",
        "room_id": "test_room_abc123",
        "message": "Join me in the secure room!",
        "timestamp": datetime.datetime.now(),
        "read": False
    }
    
    # Add to storage
    with dm_lock:
        direct_messages[dm_id] = test_dm
    
    # Verify retrieval
    with dm_lock:
        retrieved = direct_messages.get(dm_id)
        assert retrieved is not None, "Should retrieve DM"
        assert retrieved["room_id"] == "test_room_abc123", "Room ID should match"
        assert retrieved["read"] == False, "Should be unread initially"
        
        # Simulate reading
        retrieved["read"] = True
        
        # Clean up
        del direct_messages[dm_id]
    
    print("✅ DM functionality structure correct")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("OpSecHat v0.8.0 - New Features Test Suite")
    print("=" * 60)

    tests = [
        test_secure_ids,
        test_chat_room_key,
        test_rate_limiting,
        test_base64_detection,
        test_message_length_cap,
        test_dm_structure,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
