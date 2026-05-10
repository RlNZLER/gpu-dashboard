# GPU Monitor

A modern, real-time GPU dashboard for Ubuntu with NVIDIA GPUs.  
Runs entirely locally — no Grafana, no Prometheus, no bloat.

## Requirements

- Python 3.9+
- NVIDIA GPU with drivers installed
- `nvidia-smi` available in PATH

> **No GPU?** The app runs in demo mode automatically with simulated data.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
python app.py

# 3. Open in browser
# http://localhost:8000
```

## What you get

- Live GPU utilisation chart (120s rolling window)
- Temperature chart (120s rolling window)
- VRAM usage with per-process breakdown
- Power draw vs TDP limit
- Clock speeds (GPU core + memory)
- PCIe gen, fan speed
- All running compute processes with VRAM share

## Polling

Metrics update every 1 second via `nvidia-smi`. The frontend polls `/api/metrics` every 1.5 seconds.

## API

The backend exposes a single JSON endpoint:

```
GET /api/metrics
```

Returns current GPU stats + 120-point history arrays for util, temp, memory util, and power.

## Multi-GPU

If you have multiple GPUs, all are returned in `latest.gpus[]`. The dashboard currently shows GPU 0. PRs welcome.
