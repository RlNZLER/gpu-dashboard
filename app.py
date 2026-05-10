import subprocess
import time
from collections import deque
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import os
import psutil

app = FastAPI()

HISTORY_LEN = 120

gpu_history = {
    "util": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "mem_util": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "temp": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "power": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
}

cpu_history = {
    "util": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "ram": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "temp": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
}

latest_gpu = {}
latest_cpu = {}


def safe_float(val, fallback=None):
    if val in ("[N/A]", "N/A", ""):
        return fallback
    try:
        return float(val)
    except ValueError:
        return fallback


def safe_int(val, fallback=None):
    if val in ("[N/A]", "N/A", ""):
        return fallback
    try:
        return int(float(val))
    except ValueError:
        return fallback


def query_nvidia_smi():
    fields = [
        "name", "driver_version",
        "utilization.gpu", "utilization.memory",
        "memory.used", "memory.total",
        "temperature.gpu",
        "power.draw", "power.draw.instant",
        "power.limit", "power.max_limit",
        "fan.speed",
        "clocks.current.graphics", "clocks.current.memory",
        "pcie.link.gen.current",
    ]
    query = ",".join(fields)
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None
        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < len(fields):
                continue
            power_draw  = safe_float(parts[7])  or safe_float(parts[8])  or 0.0
            power_limit = safe_float(parts[9])  or safe_float(parts[10]) or 0.0
            fan_speed   = safe_int(parts[11])
            gpus.append({
                "name":          parts[0],
                "driver":        parts[1],
                "util_gpu":      safe_int(parts[2], 0),
                "util_mem":      safe_int(parts[3], 0),
                "mem_used_mb":   safe_int(parts[4], 0),
                "mem_total_mb":  safe_int(parts[5], 0),
                "temp":          safe_int(parts[6], 0),
                "power_draw":    round(power_draw, 1),
                "power_limit":   round(power_limit, 1),
                "fan_speed":     fan_speed,
                "fan_available": fan_speed is not None,
                "clock_gpu_mhz": safe_int(parts[12], 0),
                "clock_mem_mhz": safe_int(parts[13], 0),
                "pcie_gen":      parts[14] if parts[14] not in ("[N/A]", "N/A") else "N/A",
            })
        return gpus
    except Exception:
        return None


def query_gpu_processes():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []
        procs = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                procs.append({
                    "pid":     parts[0],
                    "name":    os.path.basename(parts[1]),
                    "vram_mb": safe_int(parts[2], 0),
                })
        return procs
    except Exception:
        return []


def query_cpu():
    try:
        cpu_util  = psutil.cpu_percent(interval=None)
        per_core  = psutil.cpu_percent(interval=None, percpu=True)
        freq      = psutil.cpu_freq()
        ram       = psutil.virtual_memory()
        cpu_count = psutil.cpu_count(logical=True)
        phys_count= psutil.cpu_count(logical=False)

        # Temperature — try common sensor keys
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            for key in ["coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"]:
                if key in temps and temps[key]:
                    entries = [e.current for e in temps[key] if e.current and e.current > 0]
                    if entries:
                        cpu_temp = round(sum(entries) / len(entries), 1)
                        break
        except Exception:
            pass

        # Top 5 CPU processes (skip kernel threads with 0% cpu)
        top_procs = []
        try:
            # prime cpu_percent counters first call returns 0 — that's fine
            all_procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
                try:
                    if p.info["status"] != psutil.STATUS_ZOMBIE:
                        all_procs.append(p.info)
                except Exception:
                    pass
            all_procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
            for p in all_procs[:6]:
                if (p.get("cpu_percent") or 0) > 0 or len(top_procs) < 3:
                    top_procs.append({
                        "pid":    p["pid"],
                        "name":   p["name"],
                        "cpu_pct": round(p.get("cpu_percent") or 0, 1),
                        "ram_mb": round((p["memory_info"].rss if p.get("memory_info") else 0) / 1024**2, 1),
                    })
                if len(top_procs) >= 5:
                    break
        except Exception:
            pass

        return {
            "cpu_util":      round(cpu_util, 1),
            "per_core":      [round(c, 1) for c in (per_core or [])],
            "cpu_temp":      cpu_temp,
            "temp_available": cpu_temp is not None,
            "freq_mhz":      round(freq.current) if freq else 0,
            "freq_max_mhz":  round(freq.max)     if freq and freq.max else 0,
            "cpu_count":     cpu_count or 0,
            "phys_count":    phys_count or 0,
            "ram_used_mb":   round(ram.used   / 1024**2),
            "ram_total_mb":  round(ram.total  / 1024**2),
            "ram_avail_mb":  round(ram.available / 1024**2),
            "ram_pct":       round(ram.percent, 1),
            "top_procs":     top_procs,
        }
    except Exception:
        return {}


def poll():
    # ── GPU ──
    gpus = query_nvidia_smi()
    if gpus:
        g = gpus[0]
        latest_gpu.update(g)
        latest_gpu["gpus"]      = gpus
        latest_gpu["processes"] = query_gpu_processes()
        gpu_history["util"].append(g["util_gpu"])
        gpu_history["mem_util"].append(g["util_mem"])
        gpu_history["temp"].append(g["temp"])
        gpu_history["power"].append(g["power_draw"])
    else:
        import math, random
        t = time.time()
        util     = max(0, min(100, int(50 + 30 * math.sin(t * 0.3) + random.randint(-5, 5))))
        mem_used = 7200 + random.randint(-200, 200)
        temp     = 68   + random.randint(-3, 3)
        power    = 170  + random.randint(-10, 20)
        demo = {
            "name": "NVIDIA RTX 4070 Ti (demo)", "driver": "545.23.08",
            "util_gpu": util, "util_mem": int(mem_used / 12288 * 100),
            "mem_used_mb": mem_used, "mem_total_mb": 12288,
            "temp": temp, "power_draw": float(power), "power_limit": 285.0,
            "fan_speed": None, "fan_available": False,
            "clock_gpu_mhz": 2535, "clock_mem_mhz": 10501, "pcie_gen": "4",
        }
        latest_gpu.update(demo)
        latest_gpu["gpus"]      = [demo]
        latest_gpu["processes"] = [
            {"pid": "18432", "name": "python3", "vram_mb": 6144},
            {"pid": "3210",  "name": "firefox",  "vram_mb": 768},
        ]
        gpu_history["util"].append(util)
        gpu_history["mem_util"].append(demo["util_mem"])
        gpu_history["temp"].append(temp)
        gpu_history["power"].append(float(power))

    # ── CPU ──
    cpu = query_cpu()
    if cpu:
        latest_cpu.update(cpu)
        cpu_history["util"].append(cpu["cpu_util"])
        cpu_history["ram"].append(cpu["ram_pct"])
        cpu_history["temp"].append(cpu["cpu_temp"] if cpu["cpu_temp"] else 0)

    latest_gpu["ts"] = time.time()


@app.on_event("startup")
async def startup_event():
    import asyncio
    # Prime psutil cpu_percent counters (first call always returns 0.0)
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)

    async def bg_poll():
        while True:
            poll()
            await asyncio.sleep(1)

    asyncio.create_task(bg_poll())


@app.get("/api/metrics")
def get_metrics():
    return JSONResponse({
        "gpu": latest_gpu,
        "cpu": latest_cpu,
        "gpu_history": {
            "util":     list(gpu_history["util"]),
            "mem_util": list(gpu_history["mem_util"]),
            "temp":     list(gpu_history["temp"]),
            "power":    list(gpu_history["power"]),
        },
        "cpu_history": {
            "util": list(cpu_history["util"]),
            "ram":  list(cpu_history["ram"]),
            "temp": list(cpu_history["temp"]),
        },
        "history_len": HISTORY_LEN,
    })


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__), "dashboard.html")) as f:
        return f.read()


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
