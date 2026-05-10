import subprocess
import time
from collections import deque
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import os

app = FastAPI()

HISTORY_LEN = 120

history = {
    "util": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "mem_util": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "temp": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
    "power": deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN),
}

latest = {}


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
    # power.draw.instant is more reliable on some laptop GPUs.
    # power.max_limit is a fallback when power.limit returns N/A (common on mobile GPUs).
    fields = [
        "name",
        "driver_version",
        "utilization.gpu",
        "utilization.memory",
        "memory.used",
        "memory.total",
        "temperature.gpu",
        "power.draw",
        "power.draw.instant",
        "power.limit",
        "power.max_limit",
        "fan.speed",
        "clocks.current.graphics",
        "clocks.current.memory",
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
        lines = result.stdout.strip().split("\n")
        gpus = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < len(fields):
                continue

            # Power draw: prefer power.draw, fall back to power.draw.instant
            power_draw = safe_float(parts[7]) or safe_float(parts[8]) or 0.0
            # Power limit: prefer power.limit, fall back to power.max_limit
            power_limit = safe_float(parts[9]) or safe_float(parts[10]) or 0.0
            # Fan: None means not exposed by driver (most laptop GPUs)
            fan_speed = safe_int(parts[11])

            gpus.append({
                "name": parts[0],
                "driver": parts[1],
                "util_gpu": safe_int(parts[2], 0),
                "util_mem": safe_int(parts[3], 0),
                "mem_used_mb": safe_int(parts[4], 0),
                "mem_total_mb": safe_int(parts[5], 0),
                "temp": safe_int(parts[6], 0),
                "power_draw": round(power_draw, 1),
                "power_limit": round(power_limit, 1),
                "fan_speed": fan_speed,
                "fan_available": fan_speed is not None,
                "clock_gpu_mhz": safe_int(parts[12], 0),
                "clock_mem_mhz": safe_int(parts[13], 0),
                "pcie_gen": parts[14] if parts[14] not in ("[N/A]", "N/A") else "N/A",
            })
        return gpus
    except Exception:
        return None


def query_processes():
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
                    "pid": parts[0],
                    "name": os.path.basename(parts[1]),
                    "vram_mb": safe_int(parts[2], 0),
                })
        return procs
    except Exception:
        return []


def poll():
    gpus = query_nvidia_smi()
    if gpus:
        g = gpus[0]
        latest.update(g)
        latest["gpus"] = gpus
        latest["processes"] = query_processes()
        latest["ts"] = time.time()
        history["util"].append(g["util_gpu"])
        history["mem_util"].append(g["util_mem"])
        history["temp"].append(g["temp"])
        history["power"].append(g["power_draw"])
    else:
        import math, random
        t = time.time()
        util = max(0, min(100, int(50 + 30 * math.sin(t * 0.3) + random.randint(-5, 5))))
        mem_used = 7200 + random.randint(-200, 200)
        temp = 68 + random.randint(-3, 3)
        power = 170 + random.randint(-10, 20)
        demo = {
            "name": "NVIDIA RTX 4070 Ti (demo)",
            "driver": "545.23.08",
            "util_gpu": util,
            "util_mem": int(mem_used / 12288 * 100),
            "mem_used_mb": mem_used,
            "mem_total_mb": 12288,
            "temp": temp,
            "power_draw": float(power),
            "power_limit": 285.0,
            "fan_speed": 55,
            "fan_available": True,
            "clock_gpu_mhz": 2535,
            "clock_mem_mhz": 10501,
            "pcie_gen": "4",
        }
        latest.update(demo)
        latest["gpus"] = [demo]
        latest["processes"] = [
            {"pid": "18432", "name": "python3", "vram_mb": 6144},
            {"pid": "3210",  "name": "firefox",  "vram_mb": 768},
            {"pid": "4087",  "name": "code",     "vram_mb": 384},
        ]
        latest["ts"] = t
        history["util"].append(util)
        history["mem_util"].append(demo["util_mem"])
        history["temp"].append(temp)
        history["power"].append(float(power))


@app.on_event("startup")
async def startup_event():
    import asyncio

    async def bg_poll():
        while True:
            poll()
            await asyncio.sleep(1)

    asyncio.create_task(bg_poll())


@app.get("/api/metrics")
def get_metrics():
    return JSONResponse({
        "latest": latest,
        "history": {
            "util": list(history["util"]),
            "mem_util": list(history["mem_util"]),
            "temp": list(history["temp"]),
            "power": list(history["power"]),
        },
        "history_len": HISTORY_LEN,
    })


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__), "dashboard.html")) as f:
        return f.read()


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
