"""Cross-platform scheduling for the Planner Agent."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLIST_LABEL = "com.deevpal.planner-agent"


def install_schedule(time_str: str = "07:00", config_path: str = "config.yaml") -> str:
    """Install a daily schedule. Returns description of what was installed."""
    if sys.platform == "darwin":
        return _install_launchd(time_str, config_path)
    else:
        return _install_crontab(time_str, config_path)


def uninstall_schedule() -> bool:
    """Remove the installed schedule."""
    if sys.platform == "darwin":
        return _uninstall_launchd()
    else:
        return _uninstall_crontab()


def _install_launchd(time_str: str, config_path: str) -> str:
    hour, minute = time_str.split(":")
    project_dir = Path.cwd().resolve()
    log_dir = project_dir / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    uv_path = _find_uv()
    config_abs = (project_dir / config_path).resolve()

    plist_content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{uv_path}</string>
        <string>run</string>
        <string>planner</string>
        <string>-c</string>
        <string>{config_abs}</string>
        <string>daily</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{project_dir}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{int(hour)}</integer>
        <key>Minute</key>
        <integer>{int(minute)}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{log_dir}/planner-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/planner-stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{Path.home() / '.local' / 'bin'}</string>
    </dict>
</dict>
</plist>"""

    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    # Unload existing if present
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)

    plist_path.write_text(plist_content)
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)

    return f"launchd: {plist_path}"


def _uninstall_launchd() -> bool:
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
    if not plist_path.exists():
        return False
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    plist_path.unlink()
    return True


def _install_crontab(time_str: str, config_path: str) -> str:
    hour, minute = time_str.split(":")
    project_dir = Path.cwd().resolve()
    uv_path = _find_uv()
    config_abs = (project_dir / config_path).resolve()

    cron_line = (
        f"{minute} {hour} * * * "
        f"cd {project_dir} && {uv_path} run planner -c {config_abs} daily "
        f">> {project_dir}/data/logs/planner.log 2>&1"
    )

    marker = f"# {PLIST_LABEL}"
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    # Remove old entry
    lines = [ln for ln in existing.splitlines() if PLIST_LABEL not in ln]
    lines.append(f"{cron_line}  {marker}")

    subprocess.run(
        ["crontab", "-"],
        input="\n".join(lines) + "\n",
        text=True, check=True,
    )
    return f"crontab: {cron_line}"


def _uninstall_crontab() -> bool:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return False
    lines = [ln for ln in result.stdout.splitlines() if PLIST_LABEL not in ln]
    if len(lines) == len(result.stdout.splitlines()):
        return False
    subprocess.run(
        ["crontab", "-"],
        input="\n".join(lines) + "\n",
        text=True, check=True,
    )
    return True


def _find_uv() -> str:
    for candidate in [
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv",
        Path("/usr/local/bin/uv"),
    ]:
        if candidate.exists():
            return str(candidate)
    result = subprocess.run(["which", "uv"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return "uv"
