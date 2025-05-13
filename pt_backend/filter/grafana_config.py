from prometheus_client import start_http_server, Counter, Histogram, Gauge
import time
import os

# Define custom metrics
# Request metrics
REQUEST_COUNT = Counter('django_http_requests_total', 'Total HTTP requests')
REQUEST_LATENCY = Histogram('django_http_requests_latency_seconds', 'HTTP request latency')

# Case-related metrics
CASE_CREATED = Counter('django_cases_created_total', 'Total cases created')
CASE_UPDATED = Counter('django_cases_updated_total', 'Total cases updated')
CASE_SEARCHED = Counter('django_cases_searched_total', 'Total case searches')
CASE_DETAIL_VIEWED = Counter('django_case_details_viewed_total', 'Total case details viewed')

# Location metrics
LOCATION_SEARCHED = Counter('django_locations_searched_total', 'Total location searches')
LOCATION_STATS_VIEWED = Counter('django_location_stats_viewed_total', 'Total location statistics viewed')

# Disease metrics
DISEASE_SEARCHED = Counter('django_diseases_searched_total', 'Total disease searches')
DISEASE_STATS_VIEWED = Counter('django_disease_stats_viewed_total', 'Total disease statistics viewed')

# Performance metrics
DB_QUERY_TIME = Histogram('django_db_query_time_seconds', 'Database query execution time')
CACHE_HIT_RATE = Gauge('django_cache_hit_rate', 'Cache hit rate percentage')
API_RESPONSE_TIME = Histogram('django_api_response_time_seconds', 'API response time')

# Error metrics
API_ERRORS = Counter('django_api_errors_total', 'Total API errors', ['error_type'])
DB_ERRORS = Counter('django_db_errors_total', 'Total database errors', ['error_type'])

def setup_grafana_metrics():
    """Setup local Prometheus metrics endpoint"""
    try:
        # Start Prometheus HTTP server on port 8000
        start_http_server(8000)
        print("Local Prometheus metrics server started on port 8000")
    except Exception as e:
        print(f"Error setting up metrics server: {str(e)}")

# Decorator untuk mengukur waktu eksekusi fungsi
def measure_time(metric):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            metric.observe(duration)
            return result
        return wrapper
    return decorator

# Decorator untuk menghitung jumlah pemanggilan fungsi
def count_calls(metric):
    def decorator(func):
        def wrapper(*args, **kwargs):
            metric.inc()
            return func(*args, **kwargs)
        return wrapper
    return decorator 