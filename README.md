# Ubuntu GPU-CPU Monitor Dashboard

A modern, real-time GPU + CPU dashboard for Ubuntu. Runs as a native desktop app — click the icon, browser opens, done. No Grafana, no Prometheus, no bloat.

![Python](https://img.shields.io/badge/Python-3.9+-4ade80?style=flat&labelColor=111417&color=4ade80)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-4ade80?style=flat&labelColor=111417&color=4ade80)
![License](https://img.shields.io/badge/License-MIT-4ade80?style=flat&labelColor=111417&color=4ade80)

## Dashboard

![GPU/CPU Monitor Dashboard](docs/dashboard.png)

Live monitoring dashboard showing GPU and CPU utilisation, temperature, VRAM, RAM, per-core utilisation grid, and a unified process table. Built with FastAPI + nvidia-smi + psutil.

## Features

**GPU**
- Live GPU utilisation chart — 120 second rolling window
- GPU temperature chart — 120 second rolling window
- VRAM usage with per-process breakdown
- Power draw vs TDP limit
- Subsystem bars — CUDA cores, memory bandwidth, VRAM used, power, temperature
- Clock speeds — GPU core and memory
- PCIe generation and driver version

**CPU**
- Live CPU utilisation chart — 120 second rolling window
- RAM usage chart — 120 second rolling window
- Per-core utilisation grid (all logical cores)
- CPU clock speed, physical/logical core count, RAM total and available
- CPU temperature via lm-sensors

**Processes**
- Unified process table — GPU and CPU processes in one view
- Per-process GPU VRAM, CPU RAM, and type (GPU/CPU)

**General**
- Demo mode — works without a GPU for testing
- Auto-refreshes every 1.5 seconds
- No build step, no npm, no Grafana

## Requirements

- Ubuntu 20.04 or later
- Python 3.9+
- NVIDIA GPU with drivers installed (`nvidia-smi` in PATH)
- `lm-sensors` for CPU temperature (`sudo apt install lm-sensors && sudo sensors-detect`)

## Desktop app install (recommended)

One command sets everything up — creates a venv, installs dependencies, registers the icon and app menu entry, and drops a shortcut on your Desktop.

```bash
git clone https://github.com/RlNZLER/gpu-dashboard.git
cd gpu-dashboard
bash install.sh
```

After that, launch it from your Desktop icon or search **GPU Monitor** in your app menu.

## Manual / headless usage

```bash
# Create and activate a venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python app.py

# Open in browser
# http://localhost:8000
```

## How it works

```
nvidia-smi (1s poll)  ─┐
                        ├──▶  FastAPI /api/metrics  ──▶  Browser dashboard (Chart.js, 1.5s refresh)
psutil (1s poll)      ─┘
```

`app.py` polls `nvidia-smi` and `psutil` every second, keeping a 120-point rolling history for GPU utilisation, temperature, VRAM, power, CPU utilisation, and RAM. The frontend is a single `dashboard.html` served directly by FastAPI — no build step, no npm.

`launch.sh` starts the server in the background, waits for it to be ready, then opens `http://localhost:8000` in your default browser. Re-launching kills any previous instance automatically so there are no port conflicts.

## Project structure

```
gpu-dashboard/
├── app.py            # FastAPI backend — polls nvidia-smi + psutil, serves metrics JSON
├── dashboard.html    # Frontend — dark dashboard UI with live charts
├── launch.sh         # Desktop launcher script
├── install.sh        # One-time installer (venv + desktop entry + icon)
├── icon.png          # App icon
├── requirements.txt  # Python dependencies
├── docs/
│   └── dashboard.png # Dashboard screenshot
└── README.md
```

## API

Single JSON endpoint — useful if you want to pipe metrics elsewhere.

```
GET /api/metrics
```

Response shape:

```json
{
  "latest": {
    "name": "NVIDIA RTX 3050 Laptop GPU",
    "util_gpu": 74,
    "temp": 80,
    "mem_used_mb": 2400,
    "mem_total_mb": 4096,
    "power_draw": 60.0,
    "power_limit": 75.0,
    "clock_gpu_mhz": 1695,
    "clock_mem_mhz": 6000,
    "processes": [...],
    "cpu_util": 37.8,
    "cpu_temp": 57.8,
    "ram_used_gb": 11.1,
    "ram_total_gb": 15.0,
    "cpu_clock_mhz": 2133,
    "logical_cores": 16,
    "physical_cores": 8,
    "per_core_util": [26.5, 22.4, "..."]
  },
  "history": {
    "util": [0, 12, 45, "..."],
    "temp": [65, 66, 68, "..."],
    "mem_util": ["..."],
    "power": ["..."],
    "cpu_util": ["..."],
    "ram_util": ["..."]
  },
  "history_len": 120
}
```

## Uninstall

```bash
rm ~/.local/share/applications/gpu-monitor.desktop
rm ~/.local/share/icons/hicolor/256x256/apps/gpu-monitor.png
rm ~/Desktop/gpu-monitor.desktop   # if it exists
rm -rf venv/
```

## Multi-GPU

All GPUs are returned in `latest.gpus[]`. The dashboard currently displays GPU 0. PRs welcome.
