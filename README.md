# CyberGrid Device Agent

IoT device simulator for CyberGrid platform. Publishes power measurements and status via MQTT.

## Features

- MQTT communication with Last Will Testament (LWT)
- Periodic heartbeat (online status every 30s)
- Simulated power measurements (±5% variation)
- Runtime settings change via MQTT or config.yaml hot-reload
- Graceful shutdown with Ctrl+C

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start MQTT broker
cd docker && docker compose up -d

# Run agent
PYTHONPATH=src python -m cybergrid.main
```

## Configuration

**device.json** - Static device settings (requires restart):
```json
{
  "device_id": "pv-sim-001",
  "power": 1000
}
```

**config.yaml** - Runtime settings (hot-reload without restart):
```yaml
mqtt:
  host: localhost
  port: 1883

app:
  poll_interval: 5
  heartbeat_interval: 30
```

## MQTT Topics

| Topic | Payload | QoS |
|-------|---------|-----|
| `device/{id}/status` | `{"status": "online\|offline"}` | 1, retain |
| `device/{id}/measurement` | `{"timestamp": "...", "power": 1234.5}` | 0 |

## Project Structure

```
src/cybergrid/
├── __init__.py
├── main.py           # Agent entry point
├── config.py         # Configuration manager with hot-reload
├── mqtt/             # MQTT client wrapper
└── helpers/          # Logging utilities
```
