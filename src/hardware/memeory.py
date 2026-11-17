# src/hardware/memory.py
import re
from typing import Dict, Any
from tools.executor import run_allowlisted_command


def parse_dmidecode_memory(stdout: str) -> Dict[str, Any]:
    max_cap_match = re.search(r"Maximum Capacity:\s*(.+)", stdout)
    size_matches = re.findall(r"^\s*Size:\s*(.+)$", stdout, re.MULTILINE)
    speed_matches = re.findall(r"^\s*Speed:\s*(.+)$", stdout, re.MULTILINE)
    type_matches = re.findall(r"^\s*Type:\s*(.+)$", stdout, re.MULTILINE)

    installed_modules = [s.strip() for s in size_matches if "No Module Installed" not in s]
    total_slots = len(size_matches)
    used_slots = len(installed_modules)

    return {
        "maximum_supported_capacity": max_cap_match.group(1).strip() if max_cap_match else "Unknown",
        "total_slots": total_slots,
        "used_slots": used_slots,
        "free_slots": max(0, total_slots - used_slots),
        "installed_sticks": installed_modules,
        "memory_type": next((t.strip() for t in type_matches if t.strip() != "Unknown"), "Unknown"),
        "speed": next((sp.strip() for sp in speed_matches if "Unknown" not in sp), "Unknown"),
    }


def _read_proc_meminfo() -> Dict[str, Any]:
    info = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()

    total_kb = int(info.get("MemTotal", "0 kB").split()[0])
    avail_kb = int(info.get("MemAvailable", "0 kB").split()[0])
    return {
        "total_ram_gb": round(total_kb / (1024 ** 2), 2),
        "available_ram_gb": round(avail_kb / (1024 ** 2), 2),
    }


def get_memory_info() -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": "ok"}

    # 1. Always-available OS memory stats (/proc/meminfo)
    try:
        result["os_memory"] = _read_proc_meminfo()
    except Exception as exc:
        result["os_memory_error"] = str(exc)

    # 2. Privileged SMBIOS hardware slot topology (dmidecode)
    dmi = run_allowlisted_command("dmidecode_memory")
    if dmi["ok"] and "Memory Device" in dmi["stdout"]:
        result["physical_slots"] = parse_dmidecode_memory(dmi["stdout"])
    else:
        result["physical_slots"] = None
        result["slot_details_note"] = (
            "Physical RAM slot count and motherboard max capacity are unavailable "
            f"({dmi['error'] or 'virtualized/WSL environment without SMBIOS tables'}). "
            "Configure passwordless sudo for /usr/sbin/dmidecode on bare-metal Linux."
        )

    return result