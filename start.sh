#!/bin/bash
set -e

# Run gunicorn
exec gunicorn pantau_tular.wsgi:application --bind 0.0.0.0:${PORT:-8000} 