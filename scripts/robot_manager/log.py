from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO


class TeeStream:
    def __init__(self, terminal: TextIO, logfile: TextIO):
        self.terminal = terminal
        self.logfile = logfile

    def write(self, text: str) -> int:
        self.terminal.write(text)
        self.logfile.write(text)
        self.flush()
        return len(text)

    def flush(self) -> None:
        self.terminal.flush()
        self.logfile.flush()

    def isatty(self) -> bool:
        return self.terminal.isatty()


class ManagerLogger:
    def __init__(self, project_root: Path):
        log_dir = project_root / "script_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._stdout_file = (log_dir / "debug_info.txt").open(
            "a", encoding="utf-8", buffering=1
        )
        self._stderr_file = (log_dir / "warnings_errors.txt").open(
            "a", encoding="utf-8", buffering=1
        )
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = TeeStream(sys.stdout, self._stdout_file)
        sys.stderr = TeeStream(sys.stderr, self._stderr_file)

    def close(self) -> None:
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self._stdout_file.close()
        self._stderr_file.close()

    def message(self, level: str, message: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {message}"
        stream = sys.stderr if level in {"WARNING", "ERROR"} else sys.stdout
        print(line, file=stream)
