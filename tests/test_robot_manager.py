from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts.robot_manager.config import ConfigError, HardwareCheck, load_registry
from scripts.robot_manager.hardware import HardwareChecker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGER = PROJECT_ROOT / "Open-PiRobot.sh"
FAKE_BIN = PROJECT_ROOT / "tests" / "fake_bin"


class ManagerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary_directory.name)
        self.docker_log = self.temp / "docker.jsonl"
        self.environment = os.environ.copy()
        self.environment.update(
            {
                "PATH": f"{FAKE_BIN}{os.pathsep}{self.environment['PATH']}",
                "FAKE_DOCKER_LOG": str(self.docker_log),
            }
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_manager(
        self,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(MANAGER), *arguments],
            cwd=PROJECT_ROOT,
            env=environment or self.environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def records(self) -> list[dict[str, object]]:
        if not self.docker_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.docker_log.read_text(encoding="utf-8").splitlines()
        ]

    def compose_actions(self) -> list[dict[str, object]]:
        return [
            record
            for record in self.records()
            if record["argv"][:1] == ["compose"]
            and record["argv"][:2] != ["compose", "version"]
            and "config" not in record["argv"]
        ]

    def write_config(self, body: str) -> Path:
        path = self.temp / "registry.yaml"
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return path

    def simple_config(self, modules: str) -> Path:
        document = "version: 1\nhardware_checks: {}\nmodules:\n"
        document += textwrap.indent(textwrap.dedent(modules).strip(), "  ")
        return self.write_config(document + "\n")

    def test_build_without_targets_uses_seven_default_modules_in_yaml_order(self) -> None:
        result = self.run_manager("build")
        self.assertEqual(result.returncode, 0, result.stderr)
        services = [record["argv"][-1] for record in self.compose_actions()]
        self.assertEqual(
            services,
            [
                "stm32_driver",
                "lidar_driver",
                "realsense_driver",
                "open-pi-sensor-fusion",
                "slam",
                "open-pi-voice-ia",
                "open_pi_robot",
            ],
        )

    def test_alias_order_deduplication_all_and_explicit_teleoperation(self) -> None:
        result = self.run_manager(
            "build", "main", "stm32_driver", "main", "joystick"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        services = [record["argv"][-1] for record in self.compose_actions()]
        self.assertEqual(
            services, ["open_pi_robot", "stm32_driver", "open-pi-joystick"]
        )

        self.docker_log.unlink()
        result = self.run_manager("build", "all")
        self.assertEqual(result.returncode, 0, result.stderr)
        services = [record["argv"][-1] for record in self.compose_actions()]
        self.assertNotIn("open-pi-joystick", services)
        self.assertEqual(len(services), 7)

    def test_default_command_and_command_compose_arguments(self) -> None:
        config = self.simple_config(
            """
            alpha:
              compose: compose.yaml
              service: alpha-service
              container: alpha-container
            hidden:
              compose: compose.yaml
              service: hidden-service
              container: hidden-container
              default_selected: false
            """
        )
        result = self.run_manager("--config", str(config))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.compose_actions()[0]["argv"][-4:],
            ["up", "--detach", "--no-build", "alpha-service"],
        )

        cases = {
            "build": ["build", "alpha-service"],
            "create": ["up", "--detach", "--build", "alpha-service"],
            "start": ["start", "alpha-service"],
            "stop": ["stop", "alpha-service"],
            "restart": [
                "up",
                "--detach",
                "--no-build",
                "--force-recreate",
                "alpha-service",
            ],
            "remove": ["rm", "--stop", "--force", "alpha-service"],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.docker_log.unlink(missing_ok=True)
                result = self.run_manager("--config", str(config), command, "alpha")
                self.assertEqual(result.returncode, 0, result.stderr)
                actions = self.compose_actions()
                self.assertEqual(actions[0]["argv"][-len(expected) :], expected)

    def test_disabled_module_and_empty_default_fail_before_docker(self) -> None:
        config = self.simple_config(
            """
            disabled:
              compose: compose.yaml
              service: disabled-service
              container: disabled-container
              enabled: false
            """
        )
        result = self.run_manager("--config", str(config), "build", "disabled")
        self.assertEqual(result.returncode, 2)
        self.assertIn("is disabled", result.stderr)
        self.assertEqual(self.records(), [])

        result = self.run_manager("--config", str(config), "build")
        self.assertEqual(result.returncode, 2)
        self.assertIn("No enabled default components", result.stderr)
        self.assertEqual(self.records(), [])

    def test_required_failure_stops_and_optional_failure_continues(self) -> None:
        config = self.simple_config(
            """
            optional:
              compose: compose.yaml
              service: optional-service
              container: optional-container
            required:
              compose: compose.yaml
              service: required-service
              container: required-container
              required: true
            later:
              compose: compose.yaml
              service: later-service
              container: later-container
            """
        )
        environment = self.environment | {
            "FAKE_DOCKER_FAIL_SERVICE": "optional-service",
            "FAKE_DOCKER_FAIL_ACTION": "build",
        }
        result = self.run_manager(
            "--config", str(config), "build", environment=environment
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("optional skipped", result.stderr)
        self.assertIn("later-service", [r["argv"][-1] for r in self.compose_actions()])

        self.docker_log.unlink()
        environment["FAKE_DOCKER_FAIL_SERVICE"] = "required-service"
        result = self.run_manager(
            "--config", str(config), "build", environment=environment
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("later-service", [r["argv"][-1] for r in self.compose_actions()])

    def test_build_skips_hardware_but_create_enforces_it(self) -> None:
        config = self.write_config(
            """
            version: 1
            hardware_checks:
              absent:
                type: glob
                pattern: /definitely/not/present/*
            modules:
              required:
                compose: compose.yaml
                service: required-service
                container: required-container
                required: true
                checks: [absent]
            """
        )
        result = self.run_manager("--config", str(config), "build")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.docker_log.unlink()
        result = self.run_manager("--config", str(config), "create")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.compose_actions(), [])

    def test_slam_variants_and_environment_isolation(self) -> None:
        result = self.run_manager("build", "slam", "--slam_toolbox")
        self.assertEqual(result.returncode, 0, result.stderr)
        action = self.compose_actions()[0]
        self.assertEqual(
            action["environment"],
            {
                "SLAM_PACKAGE": "slam_toolbox_bringup",
                "SLAM_LAUNCH_FILE": "slam_toolbox_online_async.launch.py",
                "SLAM_CONFIG_FILE": "/ws/config/slam_toolbox_config.yaml",
            },
        )

        self.docker_log.unlink()
        result = self.run_manager(
            "build", "voice", "slam", "--variant", "slam=toolbox"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        actions = self.compose_actions()
        self.assertEqual(actions[0]["environment"], {})
        self.assertEqual(actions[1]["environment"]["SLAM_PACKAGE"], "slam_toolbox_bringup")

        self.docker_log.unlink()
        result = self.run_manager(
            "build", "slam", "--slam_toolbox", "--slam__rtab"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Incompatible variants", result.stderr)
        self.assertEqual(self.records(), [])

    def test_invalid_configuration_has_no_docker_effects(self) -> None:
        invalid_documents = {
            "duplicate": """
                version: 1
                version: 1
                modules: {}
            """,
            "unknown field": """
                version: 1
                unexpected: true
                modules:
                  item:
                    compose: compose.yaml
                    service: item
                    container: item
            """,
            "bad reference": """
                version: 1
                modules:
                  item:
                    compose: compose.yaml
                    service: item
                    container: item
                    checks: [missing]
            """,
            "ambiguous alias": """
                version: 1
                modules:
                  first:
                    compose: compose.yaml
                    service: first
                    container: first
                    aliases: [shared]
                  second:
                    compose: compose.yaml
                    service: second
                    container: second
                    aliases: [shared]
            """,
            "wrong type": """
                version: 1
                modules:
                  item:
                    compose: compose.yaml
                    service: item
                    container: item
                    enabled: 1
            """,
        }
        for name, document in invalid_documents.items():
            with self.subTest(name=name):
                self.docker_log.unlink(missing_ok=True)
                config = self.write_config(document)
                result = self.run_manager("--config", str(config), "build")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.records(), [])

    def test_yaml_only_component_and_path_with_spaces(self) -> None:
        config = self.simple_config(
            """
            dummy:
              compose: tests/fixtures/path with spaces/compose.yaml
              service: dummy-service
              container: dummy-container
              aliases: [extra]
            """
        )
        result = self.run_manager("--config", str(config), "build", "extra")
        self.assertEqual(result.returncode, 0, result.stderr)
        action = self.compose_actions()[0]
        compose_path = action["argv"][action["argv"].index("--file") + 1]
        self.assertEqual(
            compose_path,
            str(PROJECT_ROOT / "tests" / "fixtures" / "path with spaces" / "compose.yaml"),
        )
        self.assertEqual(action["argv"][-2:], ["build", "dummy-service"])

    def test_validate_config_needs_no_docker(self) -> None:
        result = self.run_manager("validate-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records(), [])

    def test_list_includes_teleoperation_without_docker(self) -> None:
        result = self.run_manager("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        teleoperation = next(
            line for line in result.stdout.splitlines() if line.startswith("teleoperation")
        )
        self.assertIn("true", teleoperation)
        self.assertIn("false", teleoperation)
        self.assertEqual(self.records(), [])

    def test_log_interrupt_terminates_descendants(self) -> None:
        config = self.simple_config(
            """
            logger:
              compose: compose.yaml
              service: logger-service
              container: logger-container
            """
        )
        child_file = self.temp / "children"
        environment = self.environment | {"FAKE_DOCKER_CHILD_PIDS": str(child_file)}
        process = subprocess.Popen(
            [str(MANAGER), "--config", str(config), "logs", "logger"],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not child_file.exists():
            time.sleep(0.05)
        self.assertTrue(child_file.exists(), "fake log child did not start")
        child_pid = int(child_file.read_text(encoding="utf-8").strip())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=10)
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and Path(f"/proc/{child_pid}").exists():
            time.sleep(0.05)
        self.assertFalse(Path(f"/proc/{child_pid}").exists())


class ConfigurationAndHardwareTests(unittest.TestCase):
    def test_compose_paths_are_relative_to_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = Path(temporary_directory) / "other.yaml"
            config.write_text(
                textwrap.dedent(
                    """
                    version: 1
                    modules:
                      robot:
                        compose: compose.yaml
                        service: open_pi_robot
                        container: open-pi-robot
                    """
                ),
                encoding="utf-8",
            )
            registry = load_registry(config, PROJECT_ROOT)
            self.assertEqual(registry.modules["robot"].compose, PROJECT_ROOT / "compose.yaml")

    def test_compose_path_cannot_escape_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = Path(temporary_directory) / "other.yaml"
            config.write_text(
                textwrap.dedent(
                    """
                    version: 1
                    modules:
                      bad:
                        compose: ../compose.yaml
                        service: bad
                        container: bad
                    """
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_registry(config, PROJECT_ROOT)

    def test_glob_directory_and_usb_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            device = root / "device0"
            device.touch()
            checker = HardwareChecker()
            self.assertTrue(
                checker.check(HardwareCheck("glob", "glob", pattern=str(root / "device*")))[0]
            )
            self.assertTrue(
                checker.check(HardwareCheck("dir", "directory", path=str(root)))[0]
            )
            completed = subprocess.CompletedProcess(
                ["lsusb"], 0, stdout="Bus 001 Device 002: ID 8086:0b3a Camera\n", stderr=""
            )
            with mock.patch("scripts.robot_manager.hardware.shutil.which", return_value="/usr/bin/lsusb"), mock.patch(
                "scripts.robot_manager.hardware.subprocess.run", return_value=completed
            ):
                self.assertTrue(
                    checker.check(HardwareCheck("usb", "usb", vid="8086", pid="0b3a"))[0]
                )


if __name__ == "__main__":
    unittest.main()
