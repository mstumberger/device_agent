# CyberGrid Device Agent

An edge/IoT device agent that simulates a photovoltaic power sensor, publishing periodic measurements via MQTT with robust connection management and runtime configuration reload.

## Scope

This implementation focuses on core edge device responsibilities:
- **Async I/O** - Non-blocking MQTT communication with concurrent tasks
- **Reliable messaging** - Last Will Testament, exponential backoff reconnection, and thread-safe client access
- **Runtime configurability** - Hot-reload of settings without restart
- **Clean lifecycle management** - Graceful shutdown on SIGINT/SIGTERM

### Design Trade-offs

| Aspect | Approach | Rationale |
|--------|----------|-----------|
| Config reload | Polling (1s interval) | Filesystem modification time polling works reliably across all deployment environments (bare metal, Docker, VMs). Minimal overhead with 1-second check interval. |
| Business logic | Python-based | Clarity and maintainability; compiled modules reserved for performance-critical paths |
| Concurrency | `asyncio.Lock` for MQTT client | Prevents race conditions during reconnection; ensures clean state transitions |

### Operational Considerations

The agent is designed to:
- Start cleanly with minimal assumptions (fails fast if `device.json` is missing)
- Handle malformed `config.yaml` without crashing (graceful degradation)
- Shut down gracefully on signals (publishes LWT, cancels tasks, closes connections)
- Resume operation after network interruption (sleep/wake scenarios)

## Features

| Feature | Description |
|---------|-------------|
| **MQTT Communication** | QoS 1 for status (with retain), QoS 0 for measurements |
| **Last Will Testament** | Automatic `offline` status on unexpected disconnect |
| **Periodic Heartbeat** | Configurable interval (default: 30s) |
| **Power Simulation** | Configurable ±5% variation from base power rating |
| **Hot-Reload Config** | Runtime changes to MQTT, timing, and readings settings |
| **Auto Reconnection** | Exponential backoff (5s → 60s max) on connection failure |
| **Thread-Safe Client** | Locked access prevents race conditions during reconnect |
| **Graceful Shutdown** | Proper cleanup on Ctrl+C/SIGTERM |
| **CLI Interface** | Command-line argument parsing with help/version |

## Installation

### Prerequisites

- Python 3.11+
- pip
- Docker & Docker Compose (optional, for containerized deployment)

### Method 1: Editable Install (Recommended for Development)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install in editable mode
pip install -e .

# Verify installation
cybergrid-agent --version
```

### Method 2: Production Install

```bash
pip install .
```

### Method 3: With Development Tools

```bash
pip install -e ".[dev]"  # Includes pytest, mypy, black, flake8
```

## Quick Start

### Using CLI (After Installation)

```bash
# Basic usage
cybergrid-agent run

# With custom config
cybergrid-agent run -c /path/to/config.yaml

# Debug logging
cybergrid-agent run --log-level DEBUG

# JSON log format
cybergrid-agent run --log-format json
```

### Using Python Module (Without Installation)

```bash
PYTHONPATH=src python -m cybergrid.cli run
PYTHONPATH=src python -m cybergrid.cli run --log-level DEBUG
```

### Using Docker Compose

```bash
# Start all services (broker + agent)
cd docker && docker compose up -d --build

# View logs
docker compose logs -f agent

# Stop services
docker compose down

# Local development (broker only)
cd docker && docker compose up -d mqtt
cd .. && cybergrid-agent run
```

## Configuration

### `device.json` - Static Device Settings

Loaded at startup; changes require restart:

```json
{
  "device_id": "pv-sim-001",
  "power": 1000
}
```

**Error handling**: Missing or malformed file causes immediate startup failure with clear error message.

### `config.yaml` - Runtime Settings (Hot-Reloadable)

Changes detected via polling and applied within 1 second:

```yaml
mqtt:
  host: localhost
  port: 1883
  username: cybergrid
  password: cybergrid

app:
  poll_interval: 5          # Seconds between measurements
  heartbeat_interval: 30    # Seconds between heartbeat messages

readings:
  faker:
    enabled: true
    variation: 0.05         # ±5% variation
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `mqtt.host` | string | `localhost` | Broker hostname |
| `mqtt.port` | integer | `1883` | Broker port |
| `mqtt.username` | string | *(required)* | Authentication username |
| `mqtt.password` | string | *(required)* | Authentication password |
| `app.poll_interval` | integer | `5` | Measurement interval (seconds) |
| `app.heartbeat_interval` | integer | `30` | Heartbeat interval (seconds) |
| `readings.faker.enabled` | boolean | `true` | Enable faker service |
| `readings.faker.variation` | float | `0.05` | Power variation (±5%) |

**Error handling**: Malformed YAML is logged; configuration retains previous valid values.

## MQTT Topics

| Topic | QoS | Retain | Payload | Description |
|-------|-----|--------|---------|-------------|
| `device/{id}/status` | 1 | yes | `{"status": "online"\|"offline"}` | Device heartbeat with LWT |
| `device/{id}/state` | 0 | no | `{"timestamp": "...", "power": 1234.5}` | Power measurement |

Example for `device_id: "pv-sim-001"`:
- `device/pv-sim-001/status`
- `device/pv-sim-001/state`

## CLI Usage

```bash
usage: cybergrid-agent [-h] [-c FILE] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                       [--log-format {text,json}] [-v]
                       {run} ...

CyberGrid Device Agent - IoT power measurement simulator

commands:
  run                  Start the device agent

options:
  -h, --help            Show help message and exit
  -c FILE, --config FILE
                        Path to configuration file (default: config.yaml)
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set logging level (default: INFO)
  --log-format {text,json}
                        Log output format (default: text)
  -v, --version         Show version information and exit
```

## Architecture

```
src/cybergrid/
├── __init__.py           # Package metadata
├── main.py               # Application entry point and orchestrator
├── cli.py                # CLI argument parsing
├── config/
│   └── __init__.py       # Configuration manager with hot-reload
├── mqtt/
│   ├── __init__.py
│   └── client.py         # MQTT client wrapper with LWT and reconnection
├── readings/
│   ├── __init__.py       # Readings module exports
│   ├── base.py           # Abstract ReadingsSource interface
│   └── fake_readings.py  # Fake reading service implementation
└── helpers/
    ├── __init__.py
    └── logging.py        # Structured logging helper
```

### Key Design Decisions

1. **Abstract `ReadingsSource` interface** - Enables swapping data sources (faker, Modbus, HTTP) without modifying `DeviceAgent`
2. **Thread-safe MQTT client** - `asyncio.Lock` prevents race conditions when concurrent tasks publish during reconnect
3. **Separation of concerns** - Config, MQTT, and readings are isolated for testability
4. **Exception isolation** - Publish failures are logged but don't crash the agent

## Development

### Code Style

This project follows PEP 8:

```bash
# Format code
black src/

# Check linting
flake8 src/

# Type checking
mypy src/
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `aiomqtt` | `2.4.0` | Async MQTT client |
| `pyyaml` | `6.0.1` | YAML configuration parsing |

## Troubleshooting

### Connection refused (MQTT)

Ensure MQTT broker is running:

```bash
cd docker && docker compose up -d mqtt
```

### Verify MQTT Messages

```bash
# Subscribe to device topics
mosquitto_sub -h localhost -p 1883 -u cybergrid -P cybergrid -t "device/#" -v
```

## License

MIT License

---

**Note**: This is an assignment deliverable focused on demonstrating async I/O, MQTT correctness, error handling, and config reload reliability. Production deployments would require additional security (TLS), offline buffering, and fleet management capabilities.