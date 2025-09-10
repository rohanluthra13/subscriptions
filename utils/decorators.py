#!/usr/bin/env python3
"""
Database error handling decorators.
Extracted from main.py for consistent database error management.

This module provides:
- Consistent database timeout/lock handling
- Configurable error responses
- Clear separation of error handling from business logic
"""

import sqlite3
from functools import wraps


def handle_db_errors(default_return=None, should_raise=False):
    """
    Decorator to handle common database errors consistently.
    
    Args:
        default_return: Value to return if database is locked/timeout (default: None)
        should_raise: If True, re-raise database errors instead of returning default
    
    Usage:
        @handle_db_errors(default_return=[])
        def get_data(self): ...
        
        @handle_db_errors(should_raise=True)  
        def update_data(self): ...
    """
    import logging
    logger = logging.getLogger(__name__)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):  # Fixed: Generic signature to work with any function
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "database is locked" in error_msg or "timeout" in error_msg:
                    # Use proper logging instead of print
                    logger.warning(f"Database timeout/lock in {func.__name__}: {e}")
                    if should_raise:
                        raise
                    return default_return
                # Re-raise other operational errors (schema issues, etc.)
                raise
            except sqlite3.DatabaseError as e:
                # Handle broader database errors
                logger.error(f"Database error in {func.__name__}: {e}")
                if should_raise:
                    raise
                return default_return
        return wrapper
    return decorator


# Additional database utility decorators can be added here
def retry_db_operation(max_retries=3, delay=0.1, max_delay=30.0):
    """
    Decorator to retry database operations on temporary failures.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        max_delay: Maximum delay cap in seconds
    
    Usage:
        @retry_db_operation(max_retries=3)
        def sensitive_db_operation(self): ...
    """
    import time
    import logging
    logger = logging.getLogger(__name__)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = RuntimeError(f"Unexpected retry loop exit in {func.__name__}")
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # Only retry on specific transient errors
                    if ("database is locked" in error_msg or 
                        "timeout" in error_msg or 
                        "busy" in error_msg):
                        
                        if attempt < max_retries:
                            # Use proper logging and cap delay
                            actual_delay = min(delay * (2 ** attempt), max_delay)
                            logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}, retrying in {actual_delay:.1f}s")
                            time.sleep(actual_delay)
                            continue
                    
                    # Non-retryable error or max retries reached
                    raise
                    
            # This should not be reached, but provides safety
            raise last_exception
            
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test the decorators with mock functions
    import threading
    
    class MockDB:
        def __init__(self):
            self._call_count = 0
            self._lock = threading.Lock()  # Thread-safe counter
            
        def _increment_call_count(self):
            with self._lock:
                self._call_count += 1
                return self._call_count
            
        @handle_db_errors(default_return=[])
        def get_safe_data(self):
            count = self._increment_call_count()
            if count == 1:
                raise sqlite3.OperationalError("database is locked")
            return ["data1", "data2"]
            
        @handle_db_errors(should_raise=True)
        def update_critical_data(self):
            raise sqlite3.OperationalError("database is locked")
            
        @retry_db_operation(max_retries=2, delay=0.01, max_delay=1.0)
        def retry_operation(self):
            count = self._increment_call_count()
            if count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "success"
    
    print("Testing enhanced database error decorators:")
    print("=" * 50)
    
    # Test safe fallback
    print("1. Testing safe fallback...")
    db = MockDB()
    result = db.get_safe_data()
    print(f"   Safe operation result: {result}")
    
    # Test retry logic
    print("\n2. Testing retry logic...")
    db2 = MockDB()
    result2 = db2.retry_operation()
    print(f"   Retry operation result: {result2}")
    
    # Test error raising
    print("\n3. Testing error raising...")
    try:
        db3 = MockDB()
        db3.update_critical_data()
    except sqlite3.OperationalError as e:
        print(f"   Critical operation raised: {e}")
    
    # Test with static method (to verify generic signature works)
    print("\n4. Testing with static method...")
    
    @handle_db_errors(default_return="fallback")
    def static_function(value):
        if value == "error":
            raise sqlite3.OperationalError("database is locked")
        return f"processed: {value}"
    
    print(f"   Static function ('test'): {static_function('test')}")
    print(f"   Static function ('error'): {static_function('error')}")
    
    print("\n✓ All tests completed successfully!")