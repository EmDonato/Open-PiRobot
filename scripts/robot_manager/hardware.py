from __future__ import annotations

import glob
import shutil
import subprocess
from pathlib import Path

from .config import HardwareCheck


class HardwareChecker:
    def check(self, check: HardwareCheck) -> tuple[bool, str]:
        if check.type == "glob":
            passed = bool(glob.glob(check.pattern or ""))
            default = f"No path matched {check.pattern}."
        elif check.type == "directory":
            passed = Path(check.path or "").is_dir()
            default = f"Directory not found: {check.path}."
        elif check.type == "usb":
            if shutil.which("lsusb") is None:
                return False, "The lsusb command is unavailable; USB hardware cannot be checked."
            result = subprocess.run(
                ["lsusb"], check=False, capture_output=True, text=True
            )
            if result.returncode != 0:
                return False, "The lsusb command failed; USB hardware cannot be checked."
            identifier = f"{check.vid}:{check.pid}".lower()
            passed = identifier in result.stdout.lower()
            default = f"USB device {identifier} was not found."
        else:
            return False, f"Unsupported hardware check type: {check.type}."
        return passed, "" if passed else (check.message or default)
