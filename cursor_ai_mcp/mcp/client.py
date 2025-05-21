# mcp/client.py
"""
MCP Client Implementation

This module provides a client for the Model Control Protocol (MCP)
that connects to a Cursor AI instance.
"""

import asyncio
import logging
import uuid
import time
from typing import Dict, Any, Optional, List, Tuple, Union, Callable, Awaitable

from .protocol import MCPConnection, MCPMessage, MCPMessageType, MCPProtocolError

# Configure module logger
logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Exception raised for errors in the MCP client."""
    pass


class MCPClient:
    """
    Client for the Model Control Protocol (MCP).
    
    This class provides a high-level interface for connecting to and
    communicating with a Cursor AI instance using the MCP protocol.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        instance_id: str,
        version: str = "1.0.0"
    ):
        self.host = host
        self.port = port
        self.instance_id = instance_id
        self.version = version
        self.connection = None
        self.sequence = 1
        self.pending_requests = {}
        self.operation_handlers = []
        self.state_handlers = []
        self.connection_handlers = []
        self.disconnect_handlers = []
        self.error_handlers = []
    
    async def connect(self) -> bool:
        """
        Connect to the MCP server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            
            self.connection = MCPConnection(
                reader=reader,
                writer=writer,
                instance_id=self.instance_id,
                version=self.version,
                on_message=self._handle_message
            )
            
            success = await self.connection.handshake()
            
            if success:
                # Notify connection handlers
                for handler in self.connection_handlers:
                    try:
                        handler()
                    except Exception as e:
                        logger.error(f"Error in connection handler: {str(e)}")
            
            return success
            
        except (ConnectionError, OSError) as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {str(e)}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.connection:
            await self.connection.close()
            self.connection = None
            
            # Notify disconnect handlers
            for handler in self.disconnect_handlers:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error in disconnect handler: {str(e)}")
    
    def _handle_message(self, message: MCPMessage) -> None:
        """
        Handle an incoming message.
        
        This method dispatches messages to the appropriate handlers
        based on the message type.
        """
        try:
            if message.header.message_type == MCPMessageType.OPERATION:
                # Dispatch to operation handlers
                operation = message.payload.get("operation", {})
                for handler in self.operation_handlers:
                    try:
                        handler(operation)
                    except Exception as e:
                        logger.error(f"Error in operation handler: {str(e)}")
                
                # Send response
                self._send_operation_response(message.header.sequence, operation.get("operation_id", 0), True)
                
            elif message.header.message_type == MCPMessageType.STATE_RESPONSE:
                # Dispatch to state handlers
                state = message.payload.get("state", {})
                for handler in self.state_handlers:
                    try:
                        handler(state)
                    except Exception as e:
                        logger.error(f"Error in state handler: {str(e)}")
                
                # Complete any pending request
                self._complete_request(message.header.sequence, state)
                
            elif message.header.message_type == MCPMessageType.OPERATION_RESPONSE:
                # Complete any pending request
                success = message.payload.get("success", False)
                operation_id = message.payload.get("operation_id", 0)
                self._complete_request(message.header.sequence, {"success": success, "operation_id": operation_id})
                
            elif message.header.message_type == MCPMessageType.ERROR:
                # Dispatch to error handlers
                error = {
                    "code": message.payload.get("code", 0),
                    "message": message.payload.get("message", "Unknown error")
                }
                
                for handler in self.error_handlers:
                    try:
                        handler(error)
                    except Exception as e:
                        logger.error(f"Error in error handler: {str(e)}")
                
                # Complete any pending request with an error
                self._complete_request(message.header.sequence, None, error)
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    def _send_operation_response(self, sequence: int, operation_id: int, success: bool) -> None:
        """Send an operation response message."""
        if not self.connection:
            logger.error("Cannot send operation response: not connected")
            return
        
        try:
            response = MCPMessage.create_operation_response(sequence, operation_id, success)
            asyncio.create_task(self.connection.send_message(response))
        except Exception as e:
            logger.error(f"Error sending operation response: {str(e)}")
    
    def _complete_request(
        self, sequence: int, result: Any = None, error: Dict[str, Any] = None
    ) -> None:
        """Complete a pending request with a result or error."""
        future = self.pending_requests.pop(sequence, None)
        if future and not future.done():
            if error:
                future.set_exception(MCPClientError(error["message"]))
            else:
                future.set_result(result)
    
    async def send_operation(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send an operation to the Cursor AI instance.
        
        Args:
            operation: Operation dictionary
        
        Returns:
            Dict[str, Any]: Response from the server
        
        Raises:
            MCPClientError: If the operation fails
        """
        if not self.connection:
            raise MCPClientError("Not connected")
        
        sequence = self.sequence
        self.sequence += 1
        
        message = MCPMessage.create_operation(sequence, operation)
        future = asyncio.Future()
        
        self.pending_requests[sequence] = future
        
        try:
            await self.connection.send_message(message)
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            self.pending_requests.pop(sequence, None)
            raise MCPClientError("Operation timed out")
        except Exception as e:
            self.pending_requests.pop(sequence, None)
            raise MCPClientError(f"Failed to send operation: {str(e)}")
    
    async def request_state(self) -> Dict[str, Any]:
        """
        Request the current state from the Cursor AI instance.
        
        Returns:
            Dict[str, Any]: Current state
        
        Raises:
            MCPClientError: If the request fails
        """
        if not self.connection:
            raise MCPClientError("Not connected")
        
        sequence = self.sequence
        self.sequence += 1
        
        message = MCPMessage.create_state_request(sequence)
        future = asyncio.Future()
        
        self.pending_requests[sequence] = future
        
        try:
            await self.connection.send_message(message)
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            self.pending_requests.pop(sequence, None)
            raise MCPClientError("State request timed out")
        except Exception as e:
            self.pending_requests.pop(sequence, None)
            raise MCPClientError(f"Failed to request state: {str(e)}")
    
    def on_operation(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a handler for incoming operations."""
        self.operation_handlers.append(handler)
    
    def on_state(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a handler for state responses."""
        self.state_handlers.append(handler)
    
    def on_connect(self, handler: Callable[[], None]) -> None:
        """Register a handler for connection events."""
        self.connection_handlers.append(handler)
    
    def on_disconnect(self, handler: Callable[[], None]) -> None:
        """Register a handler for disconnection events."""
        self.disconnect_handlers.append(handler)
    
    def on_error(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a handler for error events."""
        self.error_handlers.append(handler) 