"""
Enhanced monitoring and logging for opsechat
Implements structured logging and APM as recommended by Amazon Q Code Review
"""

import logging
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
import traceback

DEFAULT_MEMORY_WARNING_MB = 1024

class StructuredLogger:
    """
    Structured logging implementation that maintains security while providing operational insights
    """
    
    def __init__(self, name: str = "opsechat", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create structured formatter
        formatter = StructuredFormatter()
        
        # Console handler for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for production (if LOG_FILE environment variable is set)
        log_file = os.environ.get('OPSECHAT_LOG_FILE')
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def log_event(self, level: str, event: str, **kwargs):
        """Log a structured event"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event': event,
            'level': level.upper(),
            **kwargs
        }
        
        # Remove sensitive data
        log_data = self._sanitize_log_data(log_data)
        
        getattr(self.logger, level.lower())(json.dumps(log_data))
    
    def _sanitize_log_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from log data"""
        sensitive_keys = {
            'password', 'secret', 'token', 'key', 'auth', 'credential',
            'session_id', 'user_id', 'email', 'ip_address'
        }
        
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_log_data(value)
            else:
                sanitized[key] = value
        
        return sanitized

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record):
        # If the message is already JSON, return as-is
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            # Create structured log entry for non-JSON messages
            log_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            if record.exc_info:
                log_data['exception'] = traceback.format_exception(*record.exc_info)
            
            return json.dumps(log_data)

class ApplicationPerformanceMonitor:
    """
    Application Performance Monitoring (APM) for opsechat
    Tracks key metrics without compromising security or privacy
    """
    
    def __init__(self):
        self.metrics = {
            'requests': {
                'total': 0,
                'by_endpoint': {},
                'response_times': [],
                'errors': 0
            },
            'tor': {
                'connection_attempts': 0,
                'connection_failures': 0,
                'hidden_service_creations': 0,
                'hidden_service_failures': 0
            },
            'chat': {
                'messages_sent': 0,
                'active_sessions': 0,
                'cleanup_operations': 0
            },
            'email': {
                'emails_composed': 0,
                'emails_sent': 0,
                'burner_emails_created': 0,
                'security_scans_performed': 0
            },
            'system': {
                'memory_usage_mb': 0,
                'uptime_seconds': 0,
                'start_time': time.time()
            }
        }
        self.logger = StructuredLogger("opsechat.apm")
    
    def record_request(self, endpoint: str, method: str, response_time: float, status_code: int):
        """Record HTTP request metrics"""
        self.metrics['requests']['total'] += 1
        
        endpoint_key = f"{method} {endpoint}"
        if endpoint_key not in self.metrics['requests']['by_endpoint']:
            self.metrics['requests']['by_endpoint'][endpoint_key] = {
                'count': 0,
                'total_time': 0.0,
                'errors': 0
            }
        
        endpoint_metrics = self.metrics['requests']['by_endpoint'][endpoint_key]
        endpoint_metrics['count'] += 1
        endpoint_metrics['total_time'] += response_time
        
        if status_code >= 400:
            endpoint_metrics['errors'] += 1
            self.metrics['requests']['errors'] += 1
        
        # Keep only last 1000 response times for memory efficiency
        self.metrics['requests']['response_times'].append(response_time)
        if len(self.metrics['requests']['response_times']) > 1000:
            self.metrics['requests']['response_times'] = self.metrics['requests']['response_times'][-1000:]
        
        # Log slow requests
        if response_time > 2.0:
            self.logger.log_event('warning', 'slow_request', 
                                endpoint=endpoint, 
                                method=method, 
                                response_time=response_time,
                                status_code=status_code)
    
    def record_tor_event(self, event_type: str, success: bool = True, details: Optional[Dict] = None):
        """Record Tor-related events"""
        if event_type == 'connection':
            self.metrics['tor']['connection_attempts'] += 1
            if not success:
                self.metrics['tor']['connection_failures'] += 1
        elif event_type == 'hidden_service':
            self.metrics['tor']['hidden_service_creations'] += 1
            if not success:
                self.metrics['tor']['hidden_service_failures'] += 1
        
        self.logger.log_event('info' if success else 'error', 
                            f'tor_{event_type}', 
                            success=success, 
                            **(details or {}))
    
    def record_chat_event(self, event_type: str, details: Optional[Dict] = None):
        """Record chat-related events"""
        if event_type == 'message_sent':
            self.metrics['chat']['messages_sent'] += 1
        elif event_type == 'cleanup':
            self.metrics['chat']['cleanup_operations'] += 1
        
        self.logger.log_event('info', f'chat_{event_type}', **(details or {}))
    
    def record_email_event(self, event_type: str, details: Optional[Dict] = None):
        """Record email-related events"""
        if event_type == 'composed':
            self.metrics['email']['emails_composed'] += 1
        elif event_type == 'sent':
            self.metrics['email']['emails_sent'] += 1
        elif event_type == 'burner_created':
            self.metrics['email']['burner_emails_created'] += 1
        elif event_type == 'security_scan':
            self.metrics['email']['security_scans_performed'] += 1
        
        self.logger.log_event('info', f'email_{event_type}', **(details or {}))
    
    def update_system_metrics(self):
        """Update system-level metrics"""
        try:
            import psutil
            process = psutil.Process()
            self.metrics['system']['memory_usage_mb'] = process.memory_info().rss / 1024 / 1024
        except ImportError:
            # psutil not available, skip memory monitoring
            pass
        
        self.metrics['system']['uptime_seconds'] = time.time() - self.metrics['system']['start_time']
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summarized metrics for reporting"""
        self.update_system_metrics()
        
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': self.metrics['system']['uptime_seconds'],
            'requests': {
                'total': self.metrics['requests']['total'],
                'error_rate': 0.0,
                'avg_response_time': 0.0
            },
            'tor': {
                'connection_success_rate': 0.0,
                'hidden_service_success_rate': 0.0
            },
            'activity': {
                'chat_messages': self.metrics['chat']['messages_sent'],
                'emails_composed': self.metrics['email']['emails_composed'],
                'burner_emails': self.metrics['email']['burner_emails_created']
            }
        }
        
        # Calculate request metrics
        if self.metrics['requests']['total'] > 0:
            summary['requests']['error_rate'] = (
                self.metrics['requests']['errors'] / self.metrics['requests']['total']
            ) * 100
        
        if self.metrics['requests']['response_times']:
            summary['requests']['avg_response_time'] = (
                sum(self.metrics['requests']['response_times']) / 
                len(self.metrics['requests']['response_times'])
            )
        
        # Calculate Tor success rates
        if self.metrics['tor']['connection_attempts'] > 0:
            summary['tor']['connection_success_rate'] = (
                (self.metrics['tor']['connection_attempts'] - self.metrics['tor']['connection_failures']) /
                self.metrics['tor']['connection_attempts']
            ) * 100
        
        if self.metrics['tor']['hidden_service_creations'] > 0:
            summary['tor']['hidden_service_success_rate'] = (
                (self.metrics['tor']['hidden_service_creations'] - self.metrics['tor']['hidden_service_failures']) /
                self.metrics['tor']['hidden_service_creations']
            ) * 100
        
        return summary
    
    def log_metrics_summary(self):
        """Log current metrics summary"""
        summary = self.get_metrics_summary()
        self.logger.log_event('info', 'metrics_summary', **summary)

def monitor_performance(operation_name: str):
    """Decorator to monitor function performance"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log performance if it's slow
                if execution_time > 1.0:
                    logger = StructuredLogger("opsechat.performance")
                    logger.log_event('warning', 'slow_operation',
                                   operation=operation_name,
                                   execution_time=execution_time)
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                logger = StructuredLogger("opsechat.performance")
                logger.log_event('error', 'operation_failed',
                               operation=operation_name,
                               execution_time=execution_time,
                               error=str(e))
                raise
        
        return wrapper
    return decorator

# Global APM instance
apm = ApplicationPerformanceMonitor()

# Health check endpoint data
def _read_version() -> str:
    """Read version from VERSION file, falling back to 'unknown'"""
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VERSION')
    try:
        with open(version_file) as f:
            return f.read().strip()
    except OSError:
        return 'unknown'


def _get_active_rooms_count() -> int:
    """
    Return active simple chat room count.

    Falls back to 0 when simple chat routes are unavailable.
    """
    try:
        from simple_chat_routes import chat_rooms, rooms_lock
        with rooms_lock:
            return len(chat_rooms)
    except Exception:
        return 0


def _check_version() -> Dict[str, Any]:
    """Version check is required for release traceability."""
    version = _read_version()
    if version == 'unknown':
        return {
            "status": "fail",
            "required": True,
            "details": "VERSION file missing or unreadable"
        }
    return {
        "status": "ok",
        "required": True,
        "details": f"version={version}"
    }


def _check_chat_storage() -> Dict[str, Any]:
    """Check that in-memory chat room storage is reachable."""
    try:
        from simple_chat_routes import chat_rooms, rooms_lock
        with rooms_lock:
            count = len(chat_rooms)
        return {
            "status": "ok",
            "required": True,
            "details": f"active_rooms={count}"
        }
    except Exception as exc:
        return {
            "status": "fail",
            "required": True,
            "details": f"chat storage unavailable: {exc}"
        }


def _check_rate_limiter_store() -> Dict[str, Any]:
    """Check that the in-memory rate limit store is accessible."""
    try:
        from simple_chat_routes import _rate_limit_store, _rate_limit_lock
        with _rate_limit_lock:
            session_count = len(_rate_limit_store)
        return {
            "status": "ok",
            "required": True,
            "details": f"tracked_sessions={session_count}"
        }
    except Exception as exc:
        return {
            "status": "fail",
            "required": True,
            "details": f"rate limiter unavailable: {exc}"
        }


def _check_memory_usage() -> Dict[str, Any]:
    """
    Optional memory pressure check.

    Returns unknown when psutil is not installed.
    """
    threshold_raw = os.environ.get("OPSECHAT_HEALTH_MEMORY_WARN_MB", str(DEFAULT_MEMORY_WARNING_MB))
    try:
        threshold_mb = int(threshold_raw)
    except ValueError:
        threshold_mb = DEFAULT_MEMORY_WARNING_MB
    try:
        import psutil
        process = psutil.Process()
        memory_mb = round(process.memory_info().rss / 1024 / 1024, 2)
        if memory_mb > threshold_mb:
            return {
                "status": "warn",
                "required": False,
                "details": f"rss_mb={memory_mb} above threshold_mb={threshold_mb}"
            }
        return {
            "status": "ok",
            "required": False,
            "details": f"rss_mb={memory_mb}"
        }
    except ImportError:
        return {
            "status": "unknown",
            "required": False,
            "details": "psutil not installed"
        }
    except Exception as exc:
        return {
            "status": "warn",
            "required": False,
            "details": f"memory check error: {exc}"
        }


def _evaluate_readiness(checks: Dict[str, Dict[str, Any]]) -> bool:
    """Application is ready only when all required checks are ok."""
    for check in checks.values():
        if check.get("required") and check.get("status") != "ok":
            return False
    return True


def _health_status_from_checks(checks: Dict[str, Dict[str, Any]]) -> str:
    """
    Map checks to health status:
    - unhealthy: any required check failed
    - degraded: readiness is true but an optional warning exists
    - healthy: all required checks are ok and no optional warnings
    """
    if not _evaluate_readiness(checks):
        return "unhealthy"

    has_optional_warn = any(
        (not check.get("required")) and check.get("status") == "warn"
        for check in checks.values()
    )
    if has_optional_warn:
        return "degraded"
    return "healthy"


def get_liveness_status() -> Dict[str, Any]:
    """Liveness probe: process is running and responsive."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": time.time() - apm.metrics['system']['start_time'],
        "version": _read_version(),
    }


def get_readiness_status() -> Dict[str, Any]:
    """Readiness probe: required in-memory subsystems are available."""
    checks = {
        "version": _check_version(),
        "chat_storage": _check_chat_storage(),
        "rate_limiter_store": _check_rate_limiter_store(),
        "memory_usage": _check_memory_usage(),
    }
    ready = _evaluate_readiness(checks)
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


def get_health_status() -> Dict[str, Any]:
    """Get application health status"""
    readiness = get_readiness_status()
    checks = readiness["checks"]

    return {
        'status': _health_status_from_checks(checks),
        'timestamp': datetime.utcnow().isoformat(),
        'uptime_seconds': time.time() - apm.metrics['system']['start_time'],
        'version': _read_version(),
        'active_rooms': _get_active_rooms_count(),
        'ready': readiness["ready"],
        'checks': checks
    }

# Security event logging
class SecurityEventLogger:
    """Log security-related events for audit purposes"""
    
    def __init__(self):
        self.logger = StructuredLogger("opsechat.security")
    
    def log_authentication_attempt(self, success: bool, details: Optional[Dict] = None):
        """Log authentication attempts"""
        self.logger.log_event('info' if success else 'warning',
                            'authentication_attempt',
                            success=success,
                            **(details or {}))
    
    def log_suspicious_activity(self, activity_type: str, details: Optional[Dict] = None):
        """Log suspicious activities"""
        self.logger.log_event('warning', 'suspicious_activity',
                            activity_type=activity_type,
                            **(details or {}))
    
    def log_security_scan(self, scan_type: str, results: Dict[str, Any]):
        """Log security scan results"""
        self.logger.log_event('info', 'security_scan',
                            scan_type=scan_type,
                            results=results)

# Global security logger
security_logger = SecurityEventLogger()