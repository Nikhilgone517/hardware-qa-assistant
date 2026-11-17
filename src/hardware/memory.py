import json
import re
from typing import Dict, Any
from tools.executor import run_allowlisted_command, is_wsl

SMBIOS_MEMORY_TYPES = {24: "DDR3", 26: "DDR4", 34: "DDR5"}


def _parse_gb(size_str: str) -> float:
    """Converts strings like '16 GB' or '16384 MB' to float GB."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB|KB)", size_str, re.IGNORECASE)
    if not match:
        return 0.0
    val = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "MB":
        return round(val / 1024, 2)
    if unit == "KB":
        return round(val / (1024 ** 2), 2)
    return val


def parse_dmidecode_memory(stdout: str) -> Dict[str, Any]:
    """Parses bare-metal Linux `dmidecode -t memory` output into structured slot data."""
    max_cap_match = re.search(r"Maximum Capacity:\s*(.+)", stdout)
    max_cap_str = max_cap_match.group(1).strip() if max_cap_match else "Unknown"
    max_cap_gb = _parse_gb(max_cap_str)

    # Split by individual Memory Device records for accurate per-slot parsing
    blocks = stdout.split("Memory Device")
    installed_sticks = []
    total_slots = 0
    mem_types = set()
    speeds = set()

    for block in blocks[1:]:
        size_m = re.search(r"^\s*Size:\s*(.+)$", block, re.MULTILINE)
        if not size_m:
            continue
        total_slots += 1
        size_val = size_m.group(1).strip()
        if "No Module Installed" not in size_val and "Unknown" not in size_val:
            installed_sticks.append(size_val)
            type_m = re.search(r"^\s*Type:\s*(.+)$", block, re.MULTILINE)
            speed_m = re.search(r"^\s*Speed:\s*(.+)$", block, re.MULTILINE)
            if type_m and type_m.group(1).strip() != "Unknown":
                mem_types.add(type_m.group(1).strip())
            if speed_m and "Unknown" not in speed_m.group(1):
                speeds.add(speed_m.group(1).strip())

    used_slots = len(installed_sticks)
    free_slots = max(0, total_slots - used_slots)
    installed_gb = sum(_parse_gb(s) for s in installed_sticks)
    headroom_gb = max(0.0, max_cap_gb - installed_gb) if max_cap_gb else None

    return {
        "maximum_supported_capacity": max_cap_str,
        "installed_physical_ram_gb": installed_gb,
        "total_slots": total_slots,
        "used_slots": used_slots,
        "free_slots": free_slots,
        "installed_sticks": installed_sticks,
        "memory_type": ", ".join(sorted(mem_types)) if mem_types else "Unknown",
        "speed": ", ".join(sorted(speeds)) if speeds else "Unknown",
        "can_upgrade": bool(free_slots > 0 or (headroom_gb and headroom_gb > 0)),
        "max_additional_ram_gb": headroom_gb,
        "max_single_stick_per_slot_gb": round(max_cap_gb / total_slots, 2) if (max_cap_gb and total_slots) else None,
    }


def _parse_wsl_host_memory(stdout: str) -> Dict[str, Any]:
    """Parses physical SMBIOS memory data from the Windows host when running inside WSL2."""
    data = json.loads(stdout)
    arr = data.get("Array") or {}
    if isinstance(arr, list):
        arr = arr[0] if arr else {}

    sticks_raw = data.get("Sticks") or []
    if isinstance(sticks_raw, dict):
        sticks_raw = [sticks_raw]

    max_cap_kb = int(arr.get("MaxCapacity") or 0)
    max_cap_gb = round(max_cap_kb / (1024 ** 2), 2) if max_cap_kb else 0.0
    total_slots = int(arr.get("MemoryDevices") or len(sticks_raw))

    installed_sticks = []
    installed_gb = 0.0
    speeds = set()
    mem_types = set()

    for s in sticks_raw:
        cap_bytes = int(s.get("Capacity") or 0)
        if cap_bytes > 0:
            gb = round(cap_bytes / (1024 ** 3), 2)
            installed_gb += gb
            installed_sticks.append(f"{int(gb) if gb.is_integer() else gb} GB")
        if s.get("Speed"):
            speeds.add(f"{s['Speed']} MT/s")
        mtype = SMBIOS_MEMORY_TYPES.get(int(s.get("SMBIOSMemoryType") or 0))
        if mtype:
            mem_types.add(mtype)

    used_slots = len(installed_sticks)
    free_slots = max(0, total_slots - used_slots)
    headroom_gb = max(0.0, max_cap_gb - installed_gb) if max_cap_gb else None

    return {
        "maximum_supported_capacity": f"{int(max_cap_gb) if max_cap_gb.is_integer() else max_cap_gb} GB" if max_cap_gb else "Unknown",
        "installed_physical_ram_gb": installed_gb,
        "total_slots": total_slots,
        "used_slots": used_slots,
        "free_slots": free_slots,
        "installed_sticks": installed_sticks,
        "memory_type": ", ".join(sorted(mem_types)) if mem_types else "Unknown",
        "speed": ", ".join(sorted(speeds)) if speeds else "Unknown",
        "can_upgrade": bool(free_slots > 0 or (headroom_gb and headroom_gb > 0)),
        "max_additional_ram_gb": headroom_gb,
        "max_single_stick_per_slot_gb": round(max_cap_gb / total_slots, 2) if (max_cap_gb and total_slots) else None,
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
        "linux_visible_total_ram_gb": round(total_kb / (1024 ** 2), 2),
        "linux_available_ram_gb": round(avail_kb / (1024 ** 2), 2),
    }


def get_memory_info() -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": "ok"}

    try:
        result["os_memory"] = _read_proc_meminfo()
    except Exception as exc:
        result["os_memory_error"] = str(exc)

    # 1. Primary Linux path: dmidecode -t memory
    dmi = run_allowlisted_command("dmidecode_memory")
    if dmi["ok"] and "Memory Device" in dmi["stdout"]:
        result["physical_slots_source"] = "dmidecode"
        result["physical_slots"] = parse_dmidecode_memory(dmi["stdout"])
        return result

    # 2. WSL2 Fallback: query physical host SMBIOS when Linux runs inside WSL VM
    if is_wsl():
        wsl_mem = run_allowlisted_command("wsl_memory_json")
        if wsl_mem["ok"] and wsl_mem["stdout"]:
            try:
                result["physical_slots_source"] = "wsl_host_smbios"
                result["physical_slots"] = _parse_wsl_host_memory(wsl_mem["stdout"])
                result["environment_note"] = (
                    "Running inside WSL2: 'physical_slots' shows the host laptop's real hardware RAM slots "
                    "and motherboard capacity, while 'os_memory' shows the subset allocated to the WSL2 VM."
                )
                return result
            except Exception as exc:
                result["wsl_fallback_error"] = str(exc)

    result["physical_slots"] = None
    result["slot_details_note"] = (
        "Physical RAM slot count and maximum motherboard capacity could not be read "
        f"({dmi['error']}). Configure passwordless sudo for /usr/sbin/dmidecode on bare-metal Linux."
    )
    return result
