# Cursor AI Coordination Runtime - MCP Integration

This package provides integration between the CAICR (Cursor AI Coordination Runtime) C library and Cursor AI's Model Control Protocol (MCP), enabling multiple Cursor AI instances to coordinate changes across projects while maintaining independence.

## Features

- **Seamless Integration**: Connects the C23 CAICR library with Cursor AI's MCP protocol
- **Distributed Coordination**: Enables multiple instances to work simultaneously on independent projects
- **Real-time Change Propagation**: Synchronizes changes between instances in real-time
- **Undo/Redo Functionality**: Leverages LLDB for persistent state management
- **Enterprise-grade Architecture**: Robust error handling, logging, and security features
- **Comprehensive Telemetry**: Detailed metrics and logs for monitoring and diagnostics

## Installation

### Prerequisites

- Python 3.8 or higher
- CAICR C library installed and available in a standard library path

### Installation from PyPI

```bash
pip install cursor-ai-mcp
```

### Installation from Source

```bash
git clone https://github.com/enterprise-solutions/cursor-ai-mcp.git
cd cursor-ai-mcp
pip install -e .
```

## Usage

### Configuration

Create a configuration file (`config.json`):

```json
{
    "project_root": "/path/to/your/project",
    "lldb_database_path": "/path/to/your/project/.caicr/history.db",
    "coordination_port": 15001,
    "cursor_ai_host": "127.0.0.1",
    "cursor_ai_port": 15000,
    "log_level": "INFO",
    "log_file": "/path/to/your/project/.caicr/logs/service.log",
    "metrics_file": "/path/to/your/project/.caicr/metrics/metrics.json"
}
```

### Command-line Interface

Start the service with the configuration file:

```bash
cursor-ai-mcp -c config.json
```

Or specify options directly:

```bash
cursor-ai-mcp --project /path/to/your/project --cursor-host 127.0.0.1 --cursor-port 15000
```

### Programmatic Usage

```python
from cursor_ai_mcp import load_settings, CoordinationService

# Load settings from a file or environment variables
settings = load_settings("config.json")

# Create and start the service
service = CoordinationService(settings)
service.start()

# Use the service
try:
    # Wait for Ctrl+C or other termination signal
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    # Stop the service
    service.stop()
```

## Architecture

The integration follows a layered architecture:

1. **C Library Binding Layer**: Interfaces with the CAICR C library using ctypes
2. **MCP Protocol Layer**: Implements the Model Control Protocol for Cursor AI
3. **Service Orchestration Layer**: Manages lifecycle and coordination between components
4. **Configuration Management**: Handles dynamic configuration and policy enforcement
5. **Telemetry & Diagnostics**: Provides observability across the distributed system

## API Documentation

### CoordinationService

The main service class that coordinates CAICR with Cursor AI instances.

```python
from cursor_ai_mcp import CoordinationService, Settings

# Configure the service
settings = Settings(
    project_root="/path/to/your/project",
    cursor_ai_host="127.0.0.1",
    cursor_ai_port=15000
)

# Create and start the service
service = CoordinationService(settings)
service.start()

# Perform operations
service.undo()  # Undo the last operation
service.redo()  # Redo the last undone operation

# Stop the service
service.stop()
```

### Settings

Configuration settings for the service.

```python
from cursor_ai_mcp import Settings, load_settings

# Create default settings
settings = Settings()

# Load settings from a file
settings = load_settings("config.json")

# Access and modify settings
print(settings.project_root)
settings.log_level = "DEBUG"

# Save settings to a file
settings.to_file("new_config.json")
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 