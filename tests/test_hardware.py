import pytest
from tools.executor import run_allowlisted_command
from src.hardware.cpu import parse_lscpu
from src.hardware.memory import parse_dmidecode_memory
from src.hardware.storage import parse_lsblk_json


def test_blocks_unlisted_command():
    with pytest.raises(PermissionError):
        run_allowlisted_command("rm -rf /")


def test_parse_dmidecode_memory_and_upgrade_math():
    sample_stdout = """
Physical Memory Array
	Maximum Capacity: 64 GB
	Number Of Devices: 2

Memory Device
	Size: 16 GB
	Type: DDR5
	Speed: 4800 MT/s

Memory Device
	Size: No Module Installed
	Type: Unknown
	Speed: Unknown
"""
    parsed = parse_dmidecode_memory(sample_stdout)
    assert parsed["maximum_supported_capacity"] == "64 GB"
    assert parsed["installed_physical_ram_gb"] == 16.0
    assert parsed["total_slots"] == 2
    assert parsed["used_slots"] == 1
    assert parsed["free_slots"] == 1
    assert parsed["can_upgrade"] is True
    assert parsed["max_additional_ram_gb"] == 48.0
    assert parsed["max_single_stick_per_slot_gb"] == 32.0


def test_parse_lsblk_nvme():
    sample_lsblk = """
    {
       "blockdevices": [
          {"name": "nvme0n1", "size": 512110190592, "type": "disk", "mountpoint": null, "model": "WD PC SN740", "rota": false, "tran": "nvme"}
       ]
    }
    """
    disks = parse_lsblk_json(sample_lsblk)
    assert len(disks) == 1
    assert disks[0]["drive_type"] == "NVMe SSD"
    assert disks[0]["size"] == "476.9 GB"


def test_parse_lscpu():
    sample_lscpu = """
Architecture:             x86_64
CPU(s):                   12
Model name:               12th Gen Intel(R) Core(TM) i5-12450H
Core(s) per socket:       8
Thread(s) per core:       2
CPU max MHz:              4400.0000
"""
    cpu = parse_lscpu(sample_lscpu)
    assert cpu["model_name"] == "12th Gen Intel(R) Core(TM) i5-12450H"
    assert cpu["logical_cpus"] == "12"
    assert cpu["cores_per_socket"] == "8"
