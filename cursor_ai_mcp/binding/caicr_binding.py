# binding/caicr_binding.py
"""
CAICR C Library Binding

This module provides a Python interface to the CAICR C library
through ctypes bindings.
"""

import ctypes
import os
import platform
import threading
from typing import Optional, Callable, Dict, List, Any, Tuple

from .caicr_types import (
    CAICRStatus, CAICROperationType, CAICROperation, CAICRConfig,
    CAICR_OPERATION_CALLBACK, CAICRInstancePtr
)


class CAICRBindingError(Exception):
    """Exception raised for errors in the CAICR binding layer."""
    def __init__(self, status: CAICRStatus, message: str):
        self.status = status
        self.message = message
        super().__init__(f"CAICR Error {status.name}: {message}")


class CAICRBinding:
    """
    Binds to the CAICR C library and provides a Pythonic interface.
    
    This class follows the singleton pattern to ensure only one binding
    exists per process.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CAICRBinding, cls).__new__(cls)
                cls._instance._initialize_library()
            return cls._instance
    
    def _initialize_library(self) -> None:
        """Initialize the CAICR library binding."""
        # Determine the library path based on the platform
        lib_path = self._get_library_path()
        
        try:
            # Load the C library
            self.lib = ctypes.cdll.LoadLibrary(lib_path)
            
            # Set function argument and return types
            self._configure_function_signatures()
            
            # Initialize callback registry
            self._callback_registry = {}
            self._callback_counter = 0
            self._callback_lock = threading.Lock()
            
        except OSError as e:
            raise CAICRBindingError(
                CAICRStatus.CAICR_ERROR_UNKNOWN,
                f"Failed to load CAICR library from {lib_path}: {str(e)}"
            )
    
    def _get_library_path(self) -> str:
        """Determine the library path based on the platform."""
        system = platform.system()
        
        # Look for the library in common locations
        if system == "Darwin":  # macOS
            lib_name = "libcaicr.dylib"
            search_paths = [
                os.path.join(os.path.dirname(__file__), '..', '..', 'lib'),
                "/usr/local/lib",
                "/usr/lib",
                "/opt/homebrew/lib"
            ]
        elif system == "Linux":
            lib_name = "libcaicr.so"
            search_paths = [
                os.path.join(os.path.dirname(__file__), '..', '..', 'lib'),
                "/usr/local/lib",
                "/usr/lib"
            ]
        elif system == "Windows":
            lib_name = "caicr.dll"
            search_paths = [
                os.path.join(os.path.dirname(__file__), '..', '..', 'lib'),
                os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "CAICR", "bin")
            ]
        else:
            raise CAICRBindingError(
                CAICRStatus.CAICR_ERROR_UNKNOWN,
                f"Unsupported platform: {system}"
            )
        
        # Check if the library exists in any of the search paths
        for path in search_paths:
            lib_path = os.path.join(path, lib_name)
            if os.path.exists(lib_path):
                return lib_path
        
        # Check if library path is specified in environment variable
        env_lib_path = os.environ.get("CAICR_LIBRARY_PATH")
        if env_lib_path and os.path.exists(env_lib_path):
            return env_lib_path
        
        # If not found, return a default path and let the loader handle the error
        return lib_name
    
    def _configure_function_signatures(self) -> None:
        """Configure function signatures for the C library."""
        # caicr_initialize
        self.lib.caicr_initialize.argtypes = [
            ctypes.POINTER(CAICRConfig),
            ctypes.POINTER(CAICRInstancePtr)
        ]
        self.lib.caicr_initialize.restype = ctypes.c_int  # CAICRStatus
        
        # caicr_register_operation_callback
        self.lib.caicr_register_operation_callback.argtypes = [
            CAICRInstancePtr,
            CAICR_OPERATION_CALLBACK,
            ctypes.c_void_p
        ]
        self.lib.caicr_register_operation_callback.restype = ctypes.c_int
        
        # caicr_submit_operation
        self.lib.caicr_submit_operation.argtypes = [
            CAICRInstancePtr,
            ctypes.POINTER(CAICROperation)
        ]
        self.lib.caicr_submit_operation.restype = ctypes.c_int
        
        # caicr_undo
        self.lib.caicr_undo.argtypes = [CAICRInstancePtr]
        self.lib.caicr_undo.restype = ctypes.c_int
        
        # caicr_redo
        self.lib.caicr_redo.argtypes = [CAICRInstancePtr]
        self.lib.caicr_redo.restype = ctypes.c_int
        
        # caicr_free_operation
        self.lib.caicr_free_operation.argtypes = [ctypes.POINTER(CAICROperation)]
        self.lib.caicr_free_operation.restype = None
        
        # caicr_shutdown
        self.lib.caicr_shutdown.argtypes = [CAICRInstancePtr]
        self.lib.caicr_shutdown.restype = ctypes.c_int
    
    def _check_status(self, status: int, operation: str) -> None:
        """Check the status returned by a C library function and raise an error if needed."""
        if status != CAICRStatus.CAICR_SUCCESS:
            try:
                status_enum = CAICRStatus(status)
                status_name = status_enum.name
            except ValueError:
                status_name = f"UNKNOWN_STATUS_{status}"
            
            raise CAICRBindingError(
                status,
                f"Operation '{operation}' failed with status {status_name}"
            )
    
    def _operation_callback_trampoline(self, operations_ptr, user_data) -> None:
        """
        Trampoline function that converts C callback to Python callback.
        
        This function processes the linked list of operations and invokes
        the registered Python callback.
        """
        # Extract the callback ID from user_data
        callback_id = ctypes.cast(user_data, ctypes.POINTER(ctypes.c_int)).contents.value
        
        # Get the Python callback function
        with self._callback_lock:
            callback_entry = self._callback_registry.get(callback_id)
            if callback_entry is None:
                return
            
            callback_func = callback_entry["callback"]
        
        # Convert linked list of operations to Python list
        operations = []
        current = operations_ptr
        
        while current and current.contents:
            op = current.contents
            
            # Convert C structure to Python dict
            operation = {
                "type": CAICROperationType(op.type),
                "file_path": op.file_path.decode('utf-8') if op.file_path else None,
                "line_number": op.line_number,
                "column_number": op.column_number,
                "content": op.content.decode('utf-8') if op.content else None,
                "content_length": op.content_length,
                "timestamp_ns": op.timestamp_ns,
                "instance_id": op.instance_id.decode('utf-8') if op.instance_id else None,
                "operation_id": op.operation_id
            }
            
            operations.append(operation)
            current = op.next
        
        # Call the Python callback
        try:
            callback_func(operations)
        except Exception as e:
            # Log the exception but don't propagate it to C code
            import logging
            logging.exception(f"Exception in operation callback: {str(e)}")
    
    def initialize(self, config: Dict[str, Any]) -> CAICRInstancePtr:
        """
        Initialize the CAICR runtime.
        
        Args:
            config: Configuration dictionary with the following keys:
                - instance_id: Unique identifier for this instance
                - project_root: Path to the project root directory
                - lldb_database_path: Path to the LLDB database file
                - coordination_port: Network port for instance coordination
                - sync_interval_ms: State synchronization interval in milliseconds
                - max_history_entries: Maximum number of history entries to maintain
                - encryption_enabled: Whether to enable E2E encryption
        
        Returns:
            CAICRInstancePtr: Opaque pointer to the CAICR instance
        
        Raises:
            CAICRBindingError: If initialization fails
        """
        # Create the configuration structure
        c_config = CAICRConfig(
            instance_id=config["instance_id"].encode('utf-8'),
            project_root=config["project_root"].encode('utf-8'),
            lldb_database_path=config["lldb_database_path"].encode('utf-8'),
            coordination_port=config["coordination_port"],
            sync_interval_ms=config["sync_interval_ms"],
            max_history_entries=config["max_history_entries"],
            encryption_enabled=config["encryption_enabled"]
        )
        
        # Create a pointer to receive the instance
        instance_ptr = CAICRInstancePtr()
        instance_ptr_ptr = ctypes.byref(instance_ptr)
        
        # Call the C function
        status = self.lib.caicr_initialize(ctypes.byref(c_config), instance_ptr_ptr)
        self._check_status(status, "initialize")
        
        return instance_ptr
    
    def register_operation_callback(
        self, instance: CAICRInstancePtr, callback: Callable[[List[Dict[str, Any]]], None]
    ) -> int:
        """
        Register a callback for operation notifications.
        
        Args:
            instance: CAICR instance pointer
            callback: Python function to call when operations are received
        
        Returns:
            int: Callback ID that can be used to unregister the callback
        
        Raises:
            CAICRBindingError: If registration fails
        """
        # Create a new callback ID
        with self._callback_lock:
            callback_id = self._callback_counter
            self._callback_counter += 1
            
            # Store the callback in the registry
            self._callback_registry[callback_id] = {
                "callback": callback,
                "c_callback": CAICR_OPERATION_CALLBACK(self._operation_callback_trampoline)
            }
        
        # Create a user_data pointer with the callback ID
        user_data = ctypes.pointer(ctypes.c_int(callback_id))
        
        # Call the C function
        status = self.lib.caicr_register_operation_callback(
            instance,
            self._callback_registry[callback_id]["c_callback"],
            ctypes.cast(user_data, ctypes.c_void_p)
        )
        
        self._check_status(status, "register_operation_callback")
        return callback_id
    
    def unregister_operation_callback(self, callback_id: int) -> None:
        """
        Unregister a previously registered callback.
        
        Args:
            callback_id: Callback ID returned by register_operation_callback
        """
        with self._callback_lock:
            if callback_id in self._callback_registry:
                del self._callback_registry[callback_id]
    
    def submit_operation(
        self, instance: CAICRInstancePtr, operation: Dict[str, Any]
    ) -> None:
        """
        Submit an operation for execution and distribution.
        
        Args:
            instance: CAICR instance pointer
            operation: Operation dictionary with the following keys:
                - type: Operation type (CAICROperationType)
                - file_path: Path to the affected file
                - line_number: Affected line number
                - column_number: Affected column number
                - content: Operation content
                - instance_id: ID of the initiating instance
        
        Raises:
            CAICRBindingError: If submission fails
        """
        # Convert operation dictionary to C structure
        c_operation = CAICROperation(
            type=operation["type"].value,
            file_path=operation["file_path"].encode('utf-8') if operation["file_path"] else None,
            line_number=operation["line_number"],
            column_number=operation["column_number"],
            content=operation["content"].encode('utf-8') if operation["content"] else None,
            content_length=len(operation["content"]) if operation["content"] else 0,
            timestamp_ns=0,  # Will be set by the runtime
            instance_id=operation["instance_id"].encode('utf-8') if operation["instance_id"] else None,
            operation_id=0,  # Will be set by the runtime
            next=None
        )
        
        # Call the C function
        status = self.lib.caicr_submit_operation(instance, ctypes.byref(c_operation))
        self._check_status(status, "submit_operation")
    
    def undo(self, instance: CAICRInstancePtr) -> None:
        """
        Undo the last operation.
        
        Args:
            instance: CAICR instance pointer
        
        Raises:
            CAICRBindingError: If undo fails
        """
        status = self.lib.caicr_undo(instance)
        self._check_status(status, "undo")
    
    def redo(self, instance: CAICRInstancePtr) -> None:
        """
        Redo the last undone operation.
        
        Args:
            instance: CAICR instance pointer
        
        Raises:
            CAICRBindingError: If redo fails
        """
        status = self.lib.caicr_redo(instance)
        self._check_status(status, "redo")
    
    def shutdown(self, instance: CAICRInstancePtr) -> None:
        """
        Shutdown the CAICR runtime and free resources.
        
        Args:
            instance: CAICR instance pointer
        
        Raises:
            CAICRBindingError: If shutdown fails
        """
        status = self.lib.caicr_shutdown(instance)
        self._check_status(status, "shutdown") 