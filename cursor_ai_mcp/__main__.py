"""
Command-line interface for the Cursor AI Coordination Runtime.

This module provides a command-line interface for starting and
managing the coordination service.
"""

import os
import sys
import argparse
import logging
import signal
import time
from typing import Optional, Dict, Any, List

from . import __version__, load_settings, CoordinationService, CoordinatorError


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Cursor AI Coordination Runtime MCP Integration"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    parser.add_argument(
        "-c", "--config",
        dest="config_file",
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "-p", "--project",
        dest="project_root",
        help="Path to project root directory"
    )
    
    parser.add_argument(
        "--cursor-host",
        dest="cursor_ai_host",
        help="Cursor AI host address"
    )
    
    parser.add_argument(
        "--cursor-port",
        dest="cursor_ai_port",
        type=int,
        help="Cursor AI port"
    )
    
    parser.add_argument(
        "--coordination-port",
        dest="coordination_port",
        type=int,
        help="Coordination port"
    )
    
    parser.add_argument(
        "-d", "--database",
        dest="lldb_database_path",
        help="Path to LLDB database file"
    )
    
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level"
    )
    
    parser.add_argument(
        "--log-file",
        dest="log_file",
        help="Path to log file"
    )
    
    parser.add_argument(
        "--metrics-file",
        dest="metrics_file",
        help="Path to metrics file"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the command-line interface.
    
    Returns:
        int: Exit code
    """
    # Parse command-line arguments
    args = parse_args()
    
    # Load settings
    settings = load_settings(config_file=args.config_file)
    
    # Override settings with command-line arguments
    for arg_name, arg_value in vars(args).items():
        if arg_value is not None and arg_name != "config_file":
            setattr(settings, arg_name, arg_value)
    
    # Create and start the service
    service = CoordinationService(settings)
    
    try:
        service.start()
        
        # Set up signal handlers
        def handle_signal(signum, frame):
            print("\nShutting down...")
            service.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except CoordinatorError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nShutting down...")
        service.stop()
        return 0
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 