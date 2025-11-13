"""
Test suite for pt_backend application.
This package contains all test modules for the pt_backend application.
"""

import builtins

try:
	from pt_backend.views import FiltersView as _FiltersView
except Exception:  # pragma: no cover - defensive for partial imports during tests
	_FiltersView = None

if _FiltersView is not None:
	builtins.FiltersView = _FiltersView

