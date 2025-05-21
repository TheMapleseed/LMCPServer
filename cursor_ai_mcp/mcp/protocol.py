# mcp/protocol.py
"""
Model Control Protocol (MCP) Implementation

This module defines the protocol for communication with Cursor AI's
Model Control Protocol (MCP) system.
"""

import json
import struct
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple, Union, Callable
from enum import IntEnum
import uuid
import time
import hmac
import hashlib
import base64

# Configure module logger
logger = logging.getLogger(__name__)


class MCPMessageType(IntEnum):
    """Enum defining MCP message types."""
    HANDSHAKE = 1
    HANDSHAKE_RESPONSE = 2
    OPERATION = 3
    OPERATION_RESPONSE = 4
    STATE_REQUEST = 5
    STATE_RESPONSE = 6
    ERROR = 7
    HEARTBEAT = 8
    HEARTBEAT_RESPONSE = 9


class MCPProtocolError(Exception):
    """Exception raised for errors in the MCP protocol."""
    pass


class MCPMessageHeader:
    """MCP message header structure."""
    FORMAT = "!BBHIIQ"  # Network byte order, magic(2), type(2), length(4), seq(8), timestamp(8)
    MAGIC = (0x4D, 0x43)  # 'MC' in ASCII
    SIZE = struct.calcsize(FORMAT)
    
    def __init__(
        self,
        message_type: MCPMessageType,
        length: int,
        sequence: int,
        timestamp: int = None
    ):
        self.message_type = message_type
        self.length = length
        self.sequence = sequence
        self.timestamp = timestamp or int(time.time() * 1_000_000)  # microseconds
    
    @classmethod
    def unpack(cls, header_bytes: bytes) -> 'MCPMessageHeader':
        """Unpack a header from bytes."""
        if len(header_bytes) < cls.SIZE:
            raise MCPProtocolError(f"Header too short: {len(header_bytes)} < {cls.SIZE}")
        
        magic1, magic2, message_type, length, sequence, timestamp = struct.unpack(
            cls.FORMAT, header_bytes[:cls.SIZE]
        )
        
        if (magic1, magic2) != cls.MAGIC:
            raise MCPProtocolError(f"Invalid magic bytes: {magic1:02x}{magic2:02x}")
        
        try:
            message_type_enum = MCPMessageType(message_type)
        except ValueError:
            raise MCPProtocolError(f"Unknown message type: {message_type}")
        
        return cls(message_type_enum, length, sequence, timestamp)
    
    def pack(self) -> bytes:
        """Pack the header into bytes."""
        return struct.pack(
            self.FORMAT,
            self.MAGIC[0],
            self.MAGIC[1],
            self.message_type.value,
            self.length,
            self.sequence,
            self.timestamp
        )


class MCPMessage:
    """MCP protocol message."""
    
    def __init__(
        self,
        message_type: MCPMessageType,
        sequence: int,
        payload: Dict[str, Any],
        timestamp: int = None
    ):
        self.header = MCPMessageHeader(
            message_type=message_type,
            length=0,  # Will be set during packing
            sequence=sequence,
            timestamp=timestamp
        )
        self.payload = payload
    
    @classmethod
    async def from_reader(cls, reader: asyncio.StreamReader) -> 'MCPMessage':
        """Read a message from an asyncio StreamReader."""
        # Read the header
        header_bytes = await reader.readexactly(MCPMessageHeader.SIZE)
        header = MCPMessageHeader.unpack(header_bytes)
        
        # Read the payload
        payload_bytes = await reader.readexactly(header.length)
        
        try:
            payload = json.loads(payload_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            raise MCPProtocolError(f"Invalid JSON payload: {payload_bytes}")
        
        return cls(header.message_type, header.sequence, payload, header.timestamp)
    
    def pack(self) -> bytes:
        """Pack the message into bytes."""
        payload_bytes = json.dumps(self.payload).encode('utf-8')
        self.header.length = len(payload_bytes)
        
        return self.header.pack() + payload_bytes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the message to a dictionary."""
        return {
            "type": self.header.message_type.name,
            "sequence": self.header.sequence,
            "timestamp": self.header.timestamp,
            "payload": self.payload
        }
    
    @classmethod
    def create_handshake(cls, instance_id: str, version: str) -> 'MCPMessage':
        """Create a handshake message."""
        return cls(
            message_type=MCPMessageType.HANDSHAKE,
            sequence=0,
            payload={
                "instance_id": instance_id,
                "version": version,
                "capabilities": ["undo", "redo", "sync", "reconciliation"]
            }
        )
    
    @classmethod
    def create_operation(
        cls, sequence: int, operation: Dict[str, Any]
    ) -> 'MCPMessage':
        """Create an operation message."""
        return cls(
            message_type=MCPMessageType.OPERATION,
            sequence=sequence,
            payload={
                "operation": operation
            }
        )
    
    @classmethod
    def create_operation_response(
        cls, sequence: int, operation_id: int, success: bool
    ) -> 'MCPMessage':
        """Create an operation response message."""
        return cls(
            message_type=MCPMessageType.OPERATION_RESPONSE,
            sequence=sequence,
            payload={
                "operation_id": operation_id,
                "success": success
            }
        )
    
    @classmethod
    def create_state_request(cls, sequence: int) -> 'MCPMessage':
        """Create a state request message."""
        return cls(
            message_type=MCPMessageType.STATE_REQUEST,
            sequence=sequence,
            payload={}
        )
    
    @classmethod
    def create_state_response(
        cls, sequence: int, state: Dict[str, Any]
    ) -> 'MCPMessage':
        """Create a state response message."""
        return cls(
            message_type=MCPMessageType.STATE_RESPONSE,
            sequence=sequence,
            payload={
                "state": state
            }
        )
    
    @classmethod
    def create_error(
        cls, sequence: int, code: int, message: str
    ) -> 'MCPMessage':
        """Create an error message."""
        return cls(
            message_type=MCPMessageType.ERROR,
            sequence=sequence,
            payload={
                "code": code,
                "message": message
            }
        )
    
    @classmethod
    def create_heartbeat(cls, sequence: int) -> 'MCPMessage':
        """Create a heartbeat message."""
        return cls(
            message_type=MCPMessageType.HEARTBEAT,
            sequence=sequence,
            payload={}
        )
    
    @classmethod
    def create_heartbeat_response(cls, sequence: int) -> 'MCPMessage':
        """Create a heartbeat response message."""
        return cls(
            message_type=MCPMessageType.HEARTBEAT_RESPONSE,
            sequence=sequence,
            payload={}
        )


class MCPConnection:
    """
    Manages an MCP protocol connection.
    
    This class handles the low-level details of the MCP protocol,
    including message serialization, deserialization, and connection
    management.
    """
    
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        instance_id: str,
        version: str,
        on_message: Callable[[MCPMessage], None] = None
    ):
        self.reader = reader
        self.writer = writer
        self.instance_id = instance_id
        self.version = version
        self.on_message = on_message
        self.sequence = 1
        self.connected = False
        self.remote_instance_id = None
        self.remote_capabilities = []
        self.last_received = time.time()
        self.heartbeat_task = None
        self.receiver_task = None
    
    async def send_message(self, message: MCPMessage) -> None:
        """Send a message over the connection."""
        if not self.connected and message.header.message_type != MCPMessageType.HANDSHAKE:
            raise MCPProtocolError("Cannot send messages before handshake is complete")
        
        try:
            data = message.pack()
            self.writer.write(data)
            await self.writer.drain()
            logger.debug(f"Sent {message.header.message_type.name} message, seq={message.header.sequence}")
        except (ConnectionError, asyncio.CancelledError) as e:
            logger.error(f"Error sending message: {str(e)}")
            raise
    
    async def receive_message(self) -> MCPMessage:
        """Receive a message from the connection."""
        try:
            message = await MCPMessage.from_reader(self.reader)
            self.last_received = time.time()
            logger.debug(f"Received {message.header.message_type.name} message, seq={message.header.sequence}")
            return message
        except (ConnectionError, asyncio.IncompleteReadError, asyncio.CancelledError) as e:
            logger.error(f"Error receiving message: {str(e)}")
            raise
    
    async def handshake(self) -> bool:
        """Perform the connection handshake."""
        handshake_msg = MCPMessage.create_handshake(self.instance_id, self.version)
        
        try:
            await self.send_message(handshake_msg)
            response = await self.receive_message()
            
            if response.header.message_type != MCPMessageType.HANDSHAKE_RESPONSE:
                logger.error(f"Expected HANDSHAKE_RESPONSE, got {response.header.message_type.name}")
                return False
            
            self.remote_instance_id = response.payload.get("instance_id")
            self.remote_capabilities = response.payload.get("capabilities", [])
            self.connected = True
            
            logger.info(f"Handshake successful with instance {self.remote_instance_id}")
            logger.debug(f"Remote capabilities: {self.remote_capabilities}")
            
            # Start the heartbeat and receiver tasks
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.receiver_task = asyncio.create_task(self._receiver_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"Handshake failed: {str(e)}")
            return False
    
    async def _heartbeat_loop(self) -> None:
        """Send heartbeats periodically to keep the connection alive."""
        try:
            while self.connected:
                # Send a heartbeat every 30 seconds
                await asyncio.sleep(30)
                
                # Check if we've received anything recently
                if time.time() - self.last_received > 90:
                    logger.warning("No messages received for 90 seconds, closing connection")
                    await self.close()
                    break
                
                # Send a heartbeat
                heartbeat = MCPMessage.create_heartbeat(self.sequence)
                self.sequence += 1
                await self.send_message(heartbeat)
                
        except asyncio.CancelledError:
            logger.debug("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {str(e)}")
            await self.close()
    
    async def _receiver_loop(self) -> None:
        """Receive and process messages in a loop."""
        try:
            while self.connected:
                message = await self.receive_message()
                
                # Handle heartbeats automatically
                if message.header.message_type == MCPMessageType.HEARTBEAT:
                    response = MCPMessage.create_heartbeat_response(message.header.sequence)
                    await self.send_message(response)
                    continue
                
                # Dispatch other messages to the handler
                if self.on_message:
                    try:
                        self.on_message(message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {str(e)}")
                
        except asyncio.CancelledError:
            logger.debug("Receiver loop cancelled")
        except Exception as e:
            logger.error(f"Error in receiver loop: {str(e)}")
            await self.close()
    
    async def close(self) -> None:
        """Close the connection."""
        self.connected = False
        
        # Cancel tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.receiver_task:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
        
        # Close the writer
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error closing writer: {str(e)}") 