"""
Cursor AI Coordination Runtime - Python MCP Integration

This package provides integration between the CAICR library and
Cursor AI's Model Control Protocol (MCP).
"""

__version__ = "1.0.0"

from .config.settings import Settings, load_settings
from .service.coordinator import CoordinationService, CoordinatorError
from .binding.caicr_binding import CAICRBindingError, CAICRStatus


__all__ = [
    "Settings",
    "load_settings",
    "CoordinationService",
    "CoordinatorError",
    "CAICRBindingError",
    "CAICRStatus",
    "__version__"
] 