import json
from typing import Dict, Any
from tools.executor import run_allowlisted_command, is_wsl


def _format_bytes_gb(val: Any) -> str:
    try:
        b = int(val)
        return f"{round(b / (1024 ** 3), 1)} GB"
    except (ValueError, TypeError):
        return str(val)


def parse_lsblk_json(stdout: str) -> list[Dict[str, Any]]:
    raw = json.loads(stdout)
    disks = []
    for dev in raw.get("blockdevices", []):
        if dev.get("type") == "disk":
            name = str(dev.get("name", ""))
            model = (dev.get("model") or "Unknown").strip()
            transport = (dev.get("tran") or "").lower()
            rota = dev.get("rota")

            if "virtual disk" in model.lower():
                drive_kind = "WSL2 Virtual Disk (VHDX)"
            elif transport == "nvme" or name.startswith("nvme"):
                drive_kind = "NVMe SSD"
            elif rota in (False, 0, "0"):
                drive_kind = "SATA/AHCI SSD"
            else:
                drive_kind = "HDD (Rotational)"

            disks.append(
                {
                    "name": name,
                    "model": model,
                    "size": _format_bytes_gb(dev.get("size")),
                    "transport": transport or "virtual/unknown",
                    "drive_type": drive_kind,
                    "partitions": [
                        {
                            "name": c.get("name"),
                            "size": _format_bytes_gb(c.get("size")),
                            "mountpoint": c.get("mountpoint"),
                        }
                        for c in dev.get("children", [])
                    ],
                }
            )
    return disks


def get_storage_info() -> Dict[str, Any]:
    res = run_allowlisted_command("lsblk_json")
    output: Dict[str, Any] = {"status": "ok"}

    if res["ok"]:
        try:
            output["linux_block_devices"] = parse_lsblk_json(res["stdout"])
        except json.JSONDecodeError as exc:
            output["lsblk_error"] = str(exc)
    else:
        output["lsblk_error"] = res["error"]

    # If inside WSL2, also fetch the physical laptop's NVMe/SATA drives
    if is_wsl():
        wsl_disk = run_allowlisted_command("wsl_disk_json")
        if wsl_disk["ok"] and wsl_disk["stdout"]:
            try:
                raw_disks = json.loads(wsl_disk["stdout"])
                if isinstance(raw_disks, dict):
                    raw_disks = [raw_disks]
                output["physical_host_disks"] = [
                    {
                        "model": d.get("FriendlyName"),
                        "media_type": d.get("MediaType"),
                        "bus_type": d.get("BusType"),
                        "is_nvme": str(d.get("BusType", "")).upper() == "NVME",
                        "size": _format_bytes_gb(d.get("Size")),
                    }
                    for d in raw_disks
                ]
            except Exception as exc:
                output["wsl_disk_error"] = str(exc)

    return output
