"""
pt_backend package
"""

from .prome_metrics import API_ERRORS, API_SUCCESS, DB_ERRORS, start_metrics_collection

# Initialize metrics for Prometheus
def initialize_metrics():
    try:
        # Pre-initialize error metrics for all endpoints
        endpoints = ["disease_severity", "location_severity", "city_severity"]
        error_types = ["service_error", "exception"]
        
        for endpoint in endpoints:
            for error_type in error_types:
                # Initialize with zero value
                API_ERRORS.labels(error_type=error_type, endpoint=endpoint)
                
            # Initialize success counter
            API_SUCCESS.labels(endpoint=endpoint)
        
        # Pre-initialize database error metrics
        db_error_types = ["query_error", "connection_error", "timeout"]
        db_operations = ["select", "insert", "update", "delete", "get_entity_severity_stats"]
        
        for error_type in db_error_types:
            for operation in db_operations:
                DB_ERRORS.labels(error_type=error_type, operation=operation)
        
        start_metrics_collection()
                
    except Exception as e:
        # Don't fail app startup if metrics initialization fails
        print(f"Error initializing metrics: {e}")

# Call initialization
initialize_metrics()