from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from typing import Iterable, TextIO

from .config import Module
from .log import ManagerLogger


class CommandRunner:
    def run(
        self,
        arguments: list[str],
        environment: dict[str, str] | None = None,
        quiet: bool = False,
    ) -> int:
        process_environment = os.environ.copy()
        if environment:
            process_environment.update(environment)
        if quiet:
            result = subprocess.run(
                arguments,
                env=process_environment,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode

        process = subprocess.Popen(
            arguments,
            env=process_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
        threads = [
            threading.Thread(
                target=self._copy_stream,
                args=(process.stdout, sys.stdout),
                daemon=True,
            ),
            threading.Thread(
                target=self._copy_stream,
                args=(process.stderr, sys.stderr),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        try:
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait()
            raise
        finally:
            for thread in threads:
                thread.join()

    @staticmethod
    def _copy_stream(source: Iterable[str] | None, destination: TextIO) -> None:
        if source is None:
            return
        for line in source:
            destination.write(line)
            destination.flush()


class ComposeClient:
    def __init__(self, logger: ManagerLogger, runner: CommandRunner | None = None):
        self.logger = logger
        self.runner = runner or CommandRunner()

    def check_available(self) -> bool:
        if shutil.which("docker") is None:
            self.logger.message("ERROR", "Docker is not installed.")
            return False
        if self.runner.run(["docker", "compose", "version"], quiet=True) != 0:
            self.logger.message("ERROR", "Docker Compose is not available.")
            return False
        if self.runner.run(["docker", "info"], quiet=True) != 0:
            self.logger.message("ERROR", "The Docker daemon is not reachable.")
            return False
        self.logger.message("OK", "Docker and Docker Compose are available.")
        return True

    def compose(
        self, module: Module, arguments: list[str], environment: dict[str, str]
    ) -> int:
        return self.runner.run(
            ["docker", "compose", "--file", str(module.compose), *arguments],
            environment=environment,
        )

    def inspect(
        self, module: Module, environment: dict[str, str], quiet: bool = True
    ) -> int:
        return self.runner.run(
            ["docker", "container", "inspect", module.container],
            environment=environment,
            quiet=quiet,
        )

    def inspect_output(
        self, module: Module, format_value: str, environment: dict[str, str]
    ) -> tuple[int, str]:
        process_environment = os.environ.copy()
        process_environment.update(environment)
        result = subprocess.run(
            [
                "docker",
                "container",
                "inspect",
                "--format",
                format_value,
                module.container,
            ],
            env=process_environment,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout.strip()


class LogFollower:
    def __init__(self, logger: ManagerLogger):
        self.logger = logger
        self.processes: list[subprocess.Popen[str]] = []
        self.threads: list[threading.Thread] = []
        self.signal_number: int | None = None

    def follow(self, modules: list[Module]) -> int:
        previous_handlers = {
            signal_number: signal.getsignal(signal_number)
            for signal_number in (signal.SIGINT, signal.SIGTERM)
        }
        for signal_number in previous_handlers:
            signal.signal(signal_number, self._handle_signal)
        try:
            for module in modules:
                if self.signal_number is not None:
                    break
                process = subprocess.Popen(
                    ["docker", "logs", "--follow", "--tail", "50", module.container],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
                self.processes.append(process)
                thread = threading.Thread(
                    target=self._prefix_output,
                    args=(module.name, process.stdout),
                    daemon=True,
                )
                thread.start()
                self.threads.append(thread)
            for process in self.processes:
                process.wait()
        finally:
            self.stop()
            for signal_number, handler in previous_handlers.items():
                signal.signal(signal_number, handler)
        if self.signal_number is not None:
            return 128 + self.signal_number
        return 0 if all(process.returncode == 0 for process in self.processes) else 1

    def _handle_signal(self, signal_number: int, _frame: object) -> None:
        self.signal_number = signal_number
        for process in self.processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def stop(self) -> None:
        active = [process for process in self.processes if process.poll() is None]
        if active:
            print()
            self.logger.message("INFO", "Stopping log follow.")
        for process in active:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for process in active:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        for thread in self.threads:
            thread.join(timeout=1)

    @staticmethod
    def _prefix_output(name: str, source: Iterable[str] | None) -> None:
        if source is None:
            return
        for line in source:
            print(f"[{name}] {line}", end="")
