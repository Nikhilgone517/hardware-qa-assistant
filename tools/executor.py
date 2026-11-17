import os
import shutil
import subprocess
from typing import Dict, Any

# Strict read-only allow-list. Keys are internal IDs; values are static argument lists.
# No user/LLM arguments are ever interpolated into these commands.
ALLOW_LISTED_COMMANDS: Dict[str, list[str]] = {
    "lscpu": ["lscpu"],
    "free_bytes": ["free", "-b"],
    "dmidecode_memory": ["sudo", "-n", "/usr/sbin/dmidecode", "-t", "memory"],
    "lsblk_json": ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,ROTA,TRAN"],
    "lspci": ["lspci"],
    "uname": ["uname", "-srpi"],
    # Read-only WSL2 hardware inspection fallbacks (used only when Linux runs inside WSL2 VM)
    "wsl_memory_json": [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "$arr = Get-CimInstance Win32_PhysicalMemoryArray | Select-Object MaxCapacity,MemoryDevices; "
            "$sticks = @(Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,Capacity,Speed,SMBIOSMemoryType,PartNumber); "
            "@{Array=$arr; Sticks=$sticks} | ConvertTo-Json -Compress"
        ),
    ],
    "wsl_disk_json": [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,Size | ConvertTo-Json -Compress",
    ],
    "wsl_gpu_json": [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress",
    ],
}


def is_wsl() -> bool:
    """Detects if Linux is running inside a Windows Subsystem for Linux (WSL) VM."""
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def is_binary_available(binary_name: str) -> bool:
    """Checks binary presence across Linux distros."""
    return shutil.which(binary_name) is not None


def run_allowlisted_command(command_key: str) -> Dict[str, Any]:
    """
    Executes a strictly allow-listed read-only command with shell=False and C locale.
    """
    if command_key not in ALLOW_LISTED_COMMANDS:
        raise PermissionError(f"Blocked unauthorized command key: '{command_key}'")

    cmd = list(ALLOW_LISTED_COMMANDS[command_key])
    target_bin = cmd[2] if cmd[0] == "sudo" else cmd[0]

    resolved_bin = shutil.which(target_bin)
    if not resolved_bin:
        return {
            "ok": False,
            "stdout": "",
            "error": f"Binary '{target_bin}' is not installed on this system.",
        }

    # Pin to resolved absolute binary path
    if cmd[0] == "sudo":
        cmd[0] = shutil.which("sudo") or "sudo"
        cmd[2] = resolved_bin
    else:
        cmd[0] = resolved_bin

    # Force standard English/POSIX output so parsers behave identically across distros/locales
    safe_env = {"PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin"), "LC_ALL": "C"}

    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=8,
            env=safe_env,
        )
        if result.returncode != 0:
            return {
                "ok": False,
                "stdout": result.stdout.strip(),
                "error": result.stderr.strip() or f"Exited with code {result.returncode}",
            }
        return {"ok": True, "stdout": result.stdout.strip(), "error": None}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "error": f"Command '{command_key}' timed out."}
    except Exception as exc:
        return {"ok": False, "stdout": "", "error": str(exc)}
