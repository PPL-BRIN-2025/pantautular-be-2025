from functools import wraps
import time
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge, Summary

# Existing metrics
CASE_SEARCHED = Counter('case_searched', 'Number of case search requests')

# metrics for disease severity stats
DISEASE_SEVERITY_REQUESTS = Counter('disease_severity_requests_total', 'Number of disease severity stats requests')
DISEASE_SEVERITY_RESPONSE_TIME = Histogram('disease_severity_response_time_seconds', 
                                          'Disease severity response time',
                                          buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10])
DISEASE_SEVERITY_ERRORS = Counter('disease_severity_errors_total', 'Disease severity API errors')
DISEASE_SEVERITY_DATA_COUNT = Histogram('disease_severity_data_count', 'Number of disease severity items returned')

# metrics for location severity stats
LOCATION_SEVERITY_REQUESTS = Counter('location_severity_requests_total', 'Number of location severity stats requests')
LOCATION_SEVERITY_RESPONSE_TIME = Histogram('location_severity_response_time_seconds', 
                                           'Location severity response time',
                                           buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10])
LOCATION_SEVERITY_ERRORS = Counter('location_severity_errors_total', 'Location severity API errors')
LOCATION_SEVERITY_DATA_COUNT = Histogram('location_severity_data_count', 'Number of location severity items returned')

# metrics for city severity stats
CITY_SEVERITY_REQUESTS = Counter('city_severity_requests_total', 'Number of city severity stats requests')
CITY_SEVERITY_RESPONSE_TIME = Histogram('city_severity_response_time_seconds', 
                                       'City severity response time',
                                       buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10])
CITY_SEVERITY_ERRORS = Counter('city_severity_errors_total', 'City severity API errors')
CITY_SEVERITY_DATA_COUNT = Histogram('city_severity_data_count', 'Number of city severity items returned')

# Performance metrics
DB_QUERY_TIME = Histogram('django_db_query_time_seconds', 'Database query execution time')
API_RESPONSE_TIME = Histogram('django_api_response_time_seconds', 'API response time')
API_REQUEST_SIZE = Histogram('django_api_request_size_bytes', 'Size of API requests in bytes')
API_RESPONSE_SIZE = Histogram('django_api_response_size_bytes', 'Size of API responses in bytes')

# Error metrics
API_ERRORS = Counter('django_api_errors_total', 'Total API errors', ['error_type', 'endpoint'])
DB_ERRORS = Counter('django_db_errors_total', 'Total database errors', ['error_type', 'operation'])

# Success rate metrics
API_SUCCESS = Counter('django_api_success_total', 'Total successful API calls', ['endpoint'])

# Resource usage metrics
MEMORY_USAGE = Gauge('django_memory_usage_bytes', 'Memory usage in bytes')
ACTIVE_REQUESTS = Gauge('django_active_requests', 'Number of active requests being processed')

# Severity level distribution metrics
SEVERITY_LEVEL_DISTRIBUTION = Counter('severity_level_distribution_total', 
                                     'Distribution of severity levels', 
                                     ['level', 'disease', 'location_type'])

# Decorator functions
def measure_time(histogram):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            response = view_func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            histogram.observe(elapsed_time)
            return response
        return wrapper
    return decorator

def count_calls(counter):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            counter.inc()
            return view_func(*args, **kwargs)
        return wrapper
    return decorator

def track_data_count(histogram, get_count_func=len):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            response = view_func(*args, **kwargs)
            try:
                # Extract data from response and count items
                if hasattr(response, 'data') and 'data' in response.data:
                    count = get_count_func(response.data['data'])
                    histogram.observe(count)
            except Exception:
                # Don't fail if metrics collection fails
                pass
            return response
        return wrapper
    return decorator

@contextmanager
def database_timer():
    """Context manager for timing database operations"""
    start_time = time.time()
    try:
        yield
    finally:
        DB_QUERY_TIME.observe(time.time() - start_time)

def track_active_requests(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        ACTIVE_REQUESTS.inc()
        try:
            return view_func(*args, **kwargs)
        finally:
            ACTIVE_REQUESTS.dec()
    return wrapper