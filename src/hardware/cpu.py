# src/hardware/cpu.py
from typing import Dict, Any
from tools.executor import run_allowlisted_command


def parse_lscpu(stdout: str) -> Dict[str, Any]:
    data = {}
    for line in stdout.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip()

    return {
        "model_name": data.get("Model name", "Unknown"),
        "architecture": data.get("Architecture", "Unknown"),
        "logical_cpus": data.get("CPU(s)", "Unknown"),
        "cores_per_socket": data.get("Core(s) per socket", "Unknown"),
        "threads_per_core": data.get("Thread(s) per core", "Unknown"),
        "max_mhz": data.get("CPU max MHz", data.get("CPU MHz", "Unknown")),
    }


def get_cpu_info() -> Dict[str, Any]:
    res = run_allowlisted_command("lscpu")
    if res["ok"]:
        return {"status": "ok", "source": "lscpu", "cpu": parse_lscpu(res["stdout"])}

    # Portable fallback via /proc/cpuinfo
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            lines = f.readlines()
        models = [l.split(":", 1)[1].strip() for l in lines if l.startswith("model name")]
        return {
            "status": "ok",
            "source": "/proc/cpuinfo",
            "cpu": {
                "model_name": models[0] if models else "Unknown",
                "logical_cpus": len(models) if models else "Unknown",
            },
        }
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}