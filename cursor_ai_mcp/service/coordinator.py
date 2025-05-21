# service/coordinator.py
"""
Service Coordination Layer

This module provides high-level coordination services that integrate
the CAICR library with the MCP protocol for Cursor AI instances.
"""

import asyncio
import logging
import threading
import uuid
import time
import os
from typing import Dict, Any, Optional, List, Tuple, Union, Callable, Awaitable

from ..binding.caicr_binding import CAICRBinding, CAICRBindingError, CAICRStatus
from ..binding.caicr_types import CAICRInstancePtr, CAICROperationType
from ..mcp.client import MCPClient, MCPClientError
from ..config.settings import Settings
from ..telemetry.logging import setup_logger
from ..telemetry.metrics import MetricsCollector
from ..utils.security import generate_secure_id

# Configure module logger
logger = logging.getLogger(__name__)


class CoordinatorError(Exception):
    """Exception raised for errors in the coordinator service."""
    pass


class CoordinationService:
    """
    High-level service that coordinates CAICR with Cursor AI instances.
    
    This service manages the lifecycle of the CAICR library and MCP client,
    and provides a unified interface for coordination operations.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the coordination service.
        
        Args:
            settings: Service configuration settings
        """
        self.settings = settings
        self.instance_id = settings.instance_id or generate_secure_id()
        self.caicr_binding = CAICRBinding()
        self.caicr_instance = None
        self.mcp_client = None
        self.callback_id = None
        self.running = False
        self.loop = None
        self.thread = None
        self.metrics = MetricsCollector(self.instance_id)
    
    def _operation_callback(self, operations: List[Dict[str, Any]]) -> None:
        """
        Callback function for CAICR operations.
        
        This function is called when operations are received from other
        CAICR instances and need to be forwarded to the Cursor AI instance.
        """
        if not self.mcp_client:
            logger.warning("Cannot forward operations: MCP client not initialized")
            return
        
        for operation in operations:
            try:
                # Convert CAICR operation to MCP operation
                mcp_operation = {
                    "id": operation["operation_id"],
                    "type": operation["type"].name.lower().replace("caicr_op_", ""),
                    "file_path": operation["file_path"],
                    "line": operation["line_number"],
                    "column": operation["column_number"],
                    "content": operation["content"],
                    "instance_id": operation["instance_id"],
                    "timestamp": operation["timestamp_ns"] // 1000  # ns to μs
                }
                
                # Forward to MCP client in the event loop
                asyncio.run_coroutine_threadsafe(
                    self.mcp_client.send_operation(mcp_operation),
                    self.loop
                )
                
                # Update metrics
                self.metrics.record_operation_forwarded()
                
            except Exception as e:
                logger.error(f"Error forwarding operation: {str(e)}")
    
    def _mcp_operation_handler(self, operation: Dict[str, Any]) -> None:
        """
        Handler for operations from the MCP client.
        
        This function is called when operations are received from the
        Cursor AI instance and need to be forwarded to other CAICR instances.
        """
        if not self.caicr_instance:
            logger.warning("Cannot forward operation: CAICR not initialized")
            return
        
        try:
            # Convert MCP operation to CAICR operation
            op_type_str = operation.get("type", "").upper()
            if op_type_str == "INSERT":
                op_type = CAICROperationType.CAICR_OP_INSERT
            elif op_type_str == "DELETE":
                op_type = CAICROperationType.CAICR_OP_DELETE
            elif op_type_str == "REPLACE":
                op_type = CAICROperationType.CAICR_OP_REPLACE
            elif op_type_str == "META":
                op_type = CAICROperationType.CAICR_OP_META_CHANGE
            elif op_type_str == "RESOURCE":
                op_type = CAICROperationType.CAICR_OP_RESOURCE
            else:
                logger.warning(f"Unknown operation type: {op_type_str}")
                return
            
            caicr_operation = {
                "type": op_type,
                "file_path": operation.get("file_path", ""),
                "line_number": operation.get("line", 0),
                "column_number": operation.get("column", 0),
                "content": operation.get("content", ""),
                "instance_id": self.instance_id
            }
            
            # Submit to CAICR
            self.caicr_binding.submit_operation(self.caicr_instance, caicr_operation)
            
            # Update metrics
            self.metrics.record_operation_received()
            
        except Exception as e:
            logger.error(f"Error submitting operation to CAICR: {str(e)}")
    
    def _mcp_connect_handler(self) -> None:
        """Handler for MCP connection events."""
        logger.info(f"Connected to Cursor AI instance")
        self.metrics.record_connection()
    
    def _mcp_disconnect_handler(self) -> None:
        """Handler for MCP disconnection events."""
        logger.info("Disconnected from Cursor AI instance")
        self.metrics.record_disconnection()
        
        # Attempt to reconnect after a delay
        if self.running and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._reconnect(),
                self.loop
            )
    
    def _mcp_error_handler(self, error: Dict[str, Any]) -> None:
        """Handler for MCP error events."""
        logger.error(f"MCP error: {error.get('message', 'Unknown error')}")
        self.metrics.record_error(error.get("code", 0), error.get("message", ""))
    
    async def _asyncio_main(self) -> None:
        """Main asyncio function for the service thread."""
        try:
            # Initialize MCP client
            self.mcp_client = MCPClient(
                host=self.settings.cursor_ai_host,
                port=self.settings.cursor_ai_port,
                instance_id=self.instance_id
            )
            
            # Register handlers
            self.mcp_client.on_operation(self._mcp_operation_handler)
            self.mcp_client.on_connect(self._mcp_connect_handler)
            self.mcp_client.on_disconnect(self._mcp_disconnect_handler)
            self.mcp_client.on_error(self._mcp_error_handler)
            
            # Connect to Cursor AI
            if not await self.mcp_client.connect():
                logger.error("Failed to connect to Cursor AI")
                return
            
            # Main service loop
            while self.running:
                await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            logger.info("Asyncio main task cancelled")
        except Exception as e:
            logger.error(f"Error in asyncio main: {str(e)}")
        finally:
            # Clean up
            if self.mcp_client:
                await self.mcp_client.disconnect()
                self.mcp_client = None
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect to the Cursor AI instance."""
        if not self.mcp_client or not self.running:
            return
        
        logger.info("Attempting to reconnect to Cursor AI...")
        
        # Wait before reconnecting
        await asyncio.sleep(5)
        
        try:
            if await self.mcp_client.connect():
                logger.info("Reconnected to Cursor AI")
            else:
                logger.error("Failed to reconnect to Cursor AI")
                # Schedule another reconnect attempt
                asyncio.create_task(self._reconnect())
        except Exception as e:
            logger.error(f"Error reconnecting to Cursor AI: {str(e)}")
            # Schedule another reconnect attempt
            asyncio.create_task(self._reconnect())
    
    def _service_thread(self) -> None:
        """Service thread function."""
        # Set up the asyncio event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Create and run the main task
        main_task = self.loop.create_task(self._asyncio_main())
        
        try:
            # Run the event loop
            self.loop.run_until_complete(main_task)
        except Exception as e:
            logger.error(f"Error in service thread: {str(e)}")
        finally:
            # Clean up
            self.loop.close()
            self.loop = None
    
    def start(self) -> None:
        """
        Start the coordination service.
        
        This method initializes the CAICR library, starts the MCP client,
        and begins the service thread.
        
        Raises:
            CoordinatorError: If the service fails to start
        """
        if self.running:
            raise CoordinatorError("Service already running")
        
        try:
            # Configure logging
            setup_logger(self.settings.log_level, self.settings.log_file)
            
            logger.info(f"Starting coordination service with instance ID: {self.instance_id}")
            
            # Create LLDB database directory if it doesn't exist
            os.makedirs(os.path.dirname(self.settings.lldb_database_path), exist_ok=True)
            
            # Initialize CAICR
            caicr_config = {
                "instance_id": self.instance_id,
                "project_root": self.settings.project_root,
                "lldb_database_path": self.settings.lldb_database_path,
                "coordination_port": self.settings.coordination_port,
                "sync_interval_ms": self.settings.sync_interval_ms,
                "max_history_entries": self.settings.max_history_entries,
                "encryption_enabled": self.settings.encryption_enabled
            }
            
            self.caicr_instance = self.caicr_binding.initialize(caicr_config)
            
            # Register operation callback
            self.callback_id = self.caicr_binding.register_operation_callback(
                self.caicr_instance, self._operation_callback
            )
            
            # Start the service thread
            self.running = True
            self.thread = threading.Thread(target=self._service_thread, daemon=True)
            self.thread.start()
            
            logger.info("Coordination service started")
            
        except CAICRBindingError as e:
            raise CoordinatorError(f"Failed to initialize CAICR: {str(e)}")
        except Exception as e:
            raise CoordinatorError(f"Failed to start service: {str(e)}")
    
    def stop(self) -> None:
        """
        Stop the coordination service.
        
        This method stops the service thread, disconnects the MCP client,
        and shuts down the CAICR library.
        """
        if not self.running:
            return
        
        logger.info("Stopping coordination service...")
        
        # Set the running flag to false to stop the thread
        self.running = False
        
        # Wait for the thread to finish
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        
        # Unregister the callback
        if self.callback_id is not None and self.caicr_instance:
            try:
                self.caicr_binding.unregister_operation_callback(self.callback_id)
            except Exception as e:
                logger.error(f"Error unregistering callback: {str(e)}")
        
        # Shutdown CAICR
        if self.caicr_instance:
            try:
                self.caicr_binding.shutdown(self.caicr_instance)
                self.caicr_instance = None
            except Exception as e:
                logger.error(f"Error shutting down CAICR: {str(e)}")
        
        logger.info("Coordination service stopped")
    
    def undo(self) -> None:
        """
        Undo the last operation.
        
        Raises:
            CoordinatorError: If the undo operation fails
        """
        if not self.running or not self.caicr_instance:
            raise CoordinatorError("Service not running")
        
        try:
            self.caicr_binding.undo(self.caicr_instance)
            self.metrics.record_undo()
        except CAICRBindingError as e:
            raise CoordinatorError(f"Undo failed: {str(e)}")
    
    def redo(self) -> None:
        """
        Redo the last undone operation.
        
        Raises:
            CoordinatorError: If the redo operation fails
        """
        if not self.running or not self.caicr_instance:
            raise CoordinatorError("Service not running")
        
        try:
            self.caicr_binding.redo(self.caicr_instance)
            self.metrics.record_redo()
        except CAICRBindingError as e:
            raise CoordinatorError(f"Redo failed: {str(e)}") 