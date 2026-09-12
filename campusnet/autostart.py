"""开机自启：Windows / macOS / Linux 三套实现。

统一跑 ``python -m campusnet watch``，Windows 上换成 ``pythonw.exe`` 以免弹黑框。
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys

APP_NAME = "campusnet"
LABEL = "com.campusnet.watch"

# -------------------------------------------------------------------- 命令构造
def _base_command(config_path: str, interval: int = 10) -> list:
    python = _python_executable()
    args = [python, "-m", "campusnet", "watch", "--interval", str(interval)]
    if config_path:
        args += ["--config", config_path]
    return args


def _python_executable() -> str:
    """Windows 上优先用 pythonw.exe（无控制台窗口）。"""
    exe = sys.executable or "python"
    if platform.system() == "Windows":
        candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(candidate):
            return candidate
    return exe


def _quote(args: list) -> str:
    if platform.system() == "Windows":
        return subprocess.list2cmdline(args)
    return " ".join(shlex.quote(part) for part in args)


# -------------------------------------------------------------------- 对外接口
def install(config_path: str = "", interval: int = 10) -> str:
    system = platform.system()
    if system == "Windows":
        return _install_windows(config_path, interval)
    if system == "Darwin":
        return _install_macos(config_path, interval)
    return _install_linux(config_path, interval)


def uninstall() -> str:
    system = platform.system()
    if system == "Windows":
        return _uninstall_windows()
    if system == "Darwin":
        return _uninstall_macos()
    return _uninstall_linux()


def status() -> str:
    system = platform.system()
    if system == "Windows":
        return _status_windows()
    if system == "Darwin":
        return _status_macos()
    return _status_linux()


# -------------------------------------------------------------------- Windows
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _install_windows(config_path: str, interval: int) -> str:
    import winreg  # type: ignore

    command = _quote(_base_command(config_path, interval))
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0,
                        winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
    return "已写入注册表启动项 HKCU\\{} · {}\n  {}".format(WINDOWS_RUN_KEY, APP_NAME, command)


def _uninstall_windows() -> str:
    import winreg  # type: ignore

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        return "已移除注册表启动项"
    except FileNotFoundError:
        return "没有找到启动项（可能本来就没装）"
    except OSError as exc:
        return "移除失败：{}".format(exc)


def _status_windows() -> str:
    import winreg  # type: ignore

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0,
                            winreg.KEY_QUERY_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
        return "已安装（注册表启动项）\n  {}".format(value)
    except FileNotFoundError:
        return "未安装"
    except OSError as exc:
        return "读取失败：{}".format(exc)


# -------------------------------------------------------------------- macOS
def _macos_plist_path() -> str:
    return os.path.expanduser("~/Library/LaunchAgents/{}.plist".format(LABEL))


def _install_macos(config_path: str, interval: int) -> str:
    path = _macos_plist_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    python = _python_executable()
    args = [python, "-m", "campusnet", "watch", "--interval", str(interval)]
    if config_path:
        args += ["--config", config_path]
    program_args = "\n".join(
        "        <string>{}</string>".format(a) for a in args
    )
    plist = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        "<plist version=\"1.0\">\n"
        "<dict>\n"
        "    <key>Label</key>\n"
        "    <string>{label}</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n{args}\n    </array>\n"
        "    <key>RunAtLoad</key>\n    <true/>\n"
        "    <key>KeepAlive</key>\n    <true/>\n"
        "    <key>StandardOutPath</key>\n    <string>/tmp/{label}.log</string>\n"
        "    <key>StandardErrorPath</key>\n    <string>/tmp/{label}.err</string>\n"
        "</dict>\n"
        "</plist>\n"
    ).format(label=LABEL, args=program_args)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(plist)

    if shutil.which("launchctl"):
        subprocess.run(["launchctl", "unload", path], capture_output=True)
        subprocess.run(["launchctl", "load", path], capture_output=True)
    return "已安装 LaunchAgent：{}".format(path)


def _uninstall_macos() -> str:
    path = _macos_plist_path()
    if not os.path.exists(path):
        return "没有找到 LaunchAgent（可能本来就没装）"
    if shutil.which("launchctl"):
        subprocess.run(["launchctl", "unload", path], capture_output=True)
    os.remove(path)
    return "已移除 LaunchAgent"


def _status_macos() -> str:
    path = _macos_plist_path()
    return "已安装: {}".format(path) if os.path.exists(path) else "未安装"


# -------------------------------------------------------------------- Linux
def _systemd_unit_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "systemd", "user", "{}.service".format(APP_NAME))


def _install_linux(config_path: str, interval: int) -> str:
    if shutil.which("systemctl"):
        path = _systemd_unit_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        unit = (
            "[Unit]\n"
            "Description=campusnet 校园网自动登录\n"
            "After=network-online.target\n"
            "Wants=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            "ExecStart={exec}\n"
            "Restart=always\n"
            "RestartSec=30\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        ).format(exec=_quote(_base_command(config_path, interval)))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(unit)
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", APP_NAME], capture_output=True)
        return "已安装 systemd 用户服务：{}".format(path)

    # 没有 systemd 就退回 crontab @reboot
    line = "@reboot {} >/dev/null 2>&1".format(_quote(_base_command(config_path, interval)))
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True, errors="replace")
    current = existing.stdout if existing.returncode == 0 else ""
    if line not in current:
        new = (current.rstrip("\n") + "\n" + line + "\n").lstrip("\n")
        subprocess.run(["crontab", "-"], input=new, text=True)
    return "已写入 crontab @reboot"


def _uninstall_linux() -> str:
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "disable", "--now", APP_NAME], capture_output=True)
        path = _systemd_unit_path()
        if os.path.exists(path):
            os.remove(path)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        return "已移除 systemd 用户服务"

    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True, errors="replace")
    if existing.returncode != 0:
        return "没有找到 crontab 条目"
    kept = [line for line in existing.stdout.splitlines() if APP_NAME not in line]
    subprocess.run(["crontab", "-"], input="\n".join(kept) + "\n", text=True)
    return "已从 crontab 移除"


def _status_linux() -> str:
    if shutil.which("systemctl"):
        result = subprocess.run(["systemctl", "--user", "is-enabled", APP_NAME],
                                capture_output=True, text=True, errors="replace")
        state = result.stdout.strip() or "not-found"
        if state == "enabled":
            return "已安装（systemd 用户服务，enabled）"
        return "未启用（systemd: {}）".format(state)
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True, errors="replace")
    if existing.returncode == 0 and APP_NAME in existing.stdout:
        return "已安装（crontab @reboot）"
    return "未安装"
