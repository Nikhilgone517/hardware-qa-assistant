import json
import os
from typing import Dict, Any
from tools.executor import run_allowlisted_command, is_wsl


def _read_sysfs_dmi() -> Dict[str, str]:
    """Reads non-root motherboard and laptop identity from /sys/class/dmi/id/."""
    dmi_dir = "/sys/class/dmi/id"
    fields = ["sys_vendor", "product_name", "product_version", "board_vendor", "board_name", "bios_version"]
    data = {}
    for field in fields:
        path = os.path.join(dmi_dir, field)
        try:
            with open(path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val:
                    data[field] = val
        except OSError:
            continue
    return data


def get_gpu_and_system_info() -> Dict[str, Any]:
    pci_res = run_allowlisted_command("lspci")
    uname_res = run_allowlisted_command("uname")

    gpus = []
    if pci_res["ok"]:
        for line in pci_res["stdout"].splitlines():
            lower = line.lower()
            if any(tag in lower for tag in ("vga", "3d controller", "display controller")):
                gpus.append(line.strip())

    result: Dict[str, Any] = {
        "status": "ok",
        "kernel": uname_res["stdout"] if uname_res["ok"] else "Unknown",
        "sysfs_dmi": _read_sysfs_dmi(),
        "pci_gpus": gpus,
    }

    if is_wsl():
        wsl_gpu = run_allowlisted_command("wsl_gpu_json")
        if wsl_gpu["ok"] and wsl_gpu["stdout"]:
            try:
                raw_gpus = json.loads(wsl_gpu["stdout"])
                if isinstance(raw_gpus, dict):
                    raw_gpus = [raw_gpus]
                result["physical_host_gpus"] = [
                    {
                        "name": g.get("Name"),
                        "driver_version": g.get("DriverVersion"),
                    }
                    for g in raw_gpus
                ]
            except Exception:
                pass

    return result
