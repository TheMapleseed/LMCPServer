# binding/caicr_types.py
"""
CAICR C Library Type Definitions

This module defines the C types and structures required for interfacing
with the CAICR C library through ctypes.
"""

import ctypes
from enum import IntEnum
from typing import Optional, List, Dict, Any, Callable


class CAICRStatus(IntEnum):
    """Status codes returned by CAICR library functions."""
    CAICR_SUCCESS = 0
    CAICR_ERROR_INVALID_PARAMETER = 1
    CAICR_ERROR_OUT_OF_MEMORY = 2
    CAICR_ERROR_LLDB_INITIALIZATION = 3
    CAICR_ERROR_LLDB_QUERY = 4
    CAICR_ERROR_NETWORK_INITIALIZATION = 5
    CAICR_ERROR_INSTANCE_DISCOVERY = 6
    CAICR_ERROR_OPERATION_EXECUTION = 7
    CAICR_ERROR_PERSISTENCE = 8
    CAICR_ERROR_UNKNOWN = 9


class CAICROperationType(IntEnum):
    """Operation types for change tracking."""
    CAICR_OP_INSERT = 0
    CAICR_OP_DELETE = 1
    CAICR_OP_REPLACE = 2
    CAICR_OP_META_CHANGE = 3
    CAICR_OP_RESOURCE = 4


class CAICROperation(ctypes.Structure):
    """C structure representing an operation in the CAICR library."""
    pass


# Forward reference for linked list
CAICROperation._fields_ = [
    ("type", ctypes.c_int),
    ("file_path", ctypes.c_char_p),
    ("line_number", ctypes.c_uint32),
    ("column_number", ctypes.c_uint32),
    ("content", ctypes.c_char_p),
    ("content_length", ctypes.c_size_t),
    ("timestamp_ns", ctypes.c_uint64),
    ("instance_id", ctypes.c_char_p),
    ("operation_id", ctypes.c_uint64),
    ("next", ctypes.POINTER(CAICROperation))
]


class CAICRConfig(ctypes.Structure):
    """Configuration structure for CAICR initialization."""
    _fields_ = [
        ("instance_id", ctypes.c_char_p),
        ("project_root", ctypes.c_char_p),
        ("lldb_database_path", ctypes.c_char_p),
        ("coordination_port", ctypes.c_uint16),
        ("sync_interval_ms", ctypes.c_uint32),
        ("max_history_entries", ctypes.c_size_t),
        ("encryption_enabled", ctypes.c_bool)
    ]


# Define callback function type for operations
CAICR_OPERATION_CALLBACK = ctypes.CFUNCTYPE(
    None,  # Return type (void)
    ctypes.POINTER(CAICROperation),  # operations parameter
    ctypes.c_void_p  # user_data parameter
)


# Opaque handle for the CAICR instance
class CAICRInstance(ctypes.Structure):
    """Opaque handle for the CAICR instance."""
    pass


CAICRInstancePtr = ctypes.POINTER(CAICRInstance) 