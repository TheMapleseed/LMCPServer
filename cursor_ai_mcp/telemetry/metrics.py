# telemetry/metrics.py
"""
Metrics Collection

This module provides metrics collection for the Cursor AI
coordination service.
"""

import os
import json
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field, asdict

# Set up module logger
logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Metrics data structure."""
    
    instance_id: str
    
    # Connection metrics
    connection_count: int = 0
    disconnection_count: int = 0
    last_connection_time: Optional[float] = None
    last_disconnection_time: Optional[float] = None
    
    # Operation metrics
    operations_received: int = 0
    operations_forwarded: int = 0
    undos: int = 0
    redos: int = 0
    
    # Error metrics
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Performance metrics
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a dictionary."""
        return asdict(self)


class MetricsCollector:
    """
    Collects and manages metrics for the service.
    
    This class provides thread-safe metrics collection and periodic
    writing to a metrics file.
    """
    
    def __init__(
        self,
        instance_id: str,
        metrics_file: Optional[str] = None,
        write_interval: int = 60
    ):
        """
        Initialize the metrics collector.
        
        Args:
            instance_id: Instance identifier
            metrics_file: Path to the metrics file (optional)
            write_interval: Interval in seconds for writing metrics to file
        """
        self.metrics = Metrics(instance_id=instance_id)
        self.metrics_file = metrics_file
        self.write_interval = write_interval
        self.lock = threading.Lock()
        self.writer_thread = None
        self.running = False
        
        # Start the writer thread if a metrics file is specified
        if self.metrics_file:
            self._start_writer_thread()
    
    def _start_writer_thread(self) -> None:
        """Start the metrics writer thread."""
        if self.writer_thread is not None and self.writer_thread.is_alive():
            return
        
        self.running = True
        self.writer_thread = threading.Thread(target=self._writer_thread_func, daemon=True)
        self.writer_thread.start()
    
    def _writer_thread_func(self) -> None:
        """Metrics writer thread function."""
        while self.running:
            try:
                # Sleep first to allow some metrics to be collected
                time.sleep(self.write_interval)
                
                # Write metrics to file
                self._write_metrics()
                
            except Exception as e:
                logger.error(f"Error writing metrics: {str(e)}")
    
    def _write_metrics(self) -> None:
        """Write metrics to the metrics file."""
        if not self.metrics_file:
            return
        
        try:
            # Create directory if it doesn't exist
            metrics_dir = os.path.dirname(self.metrics_file)
            if metrics_dir and not os.path.exists(metrics_dir):
                os.makedirs(metrics_dir, exist_ok=True)
            
            # Get a copy of the metrics with the lock
            with self.lock:
                metrics_dict = self.metrics.to_dict()
            
            # Write to file
            with open(self.metrics_file, "w") as f:
                json.dump(metrics_dict, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to write metrics to {self.metrics_file}: {str(e)}")
    
    def record_connection(self) -> None:
        """Record a connection event."""
        with self.lock:
            self.metrics.connection_count += 1
            self.metrics.last_connection_time = time.time()
    
    def record_disconnection(self) -> None:
        """Record a disconnection event."""
        with self.lock:
            self.metrics.disconnection_count += 1
            self.metrics.last_disconnection_time = time.time()
    
    def record_operation_received(self) -> None:
        """Record an operation received event."""
        with self.lock:
            self.metrics.operations_received += 1
    
    def record_operation_forwarded(self) -> None:
        """Record an operation forwarded event."""
        with self.lock:
            self.metrics.operations_forwarded += 1
    
    def record_undo(self) -> None:
        """Record an undo event."""
        with self.lock:
            self.metrics.undos += 1
    
    def record_redo(self) -> None:
        """Record a redo event."""
        with self.lock:
            self.metrics.redos += 1
    
    def record_error(self, code: int, message: str) -> None:
        """
        Record an error event.
        
        Args:
            code: Error code
            message: Error message
        """
        with self.lock:
            self.metrics.errors.append({
                "time": time.time(),
                "code": code,
                "message": message
            })
            
            # Limit the number of stored errors
            if len(self.metrics.errors) > 100:
                self.metrics.errors = self.metrics.errors[-100:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get the current metrics.
        
        Returns:
            Dict[str, Any]: Current metrics
        """
        with self.lock:
            return self.metrics.to_dict()
    
    def stop(self) -> None:
        """Stop the metrics collector."""
        self.running = False
        
        if self.writer_thread and self.writer_thread.is_alive():
            self.writer_thread.join(timeout=5)
            self.writer_thread = None
        
        # Write final metrics
        self._write_metrics() 