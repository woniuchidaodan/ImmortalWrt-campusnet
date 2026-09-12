"""campusnet 命令行入口。"""

from __future__ import annotations

import argparse
import os
import platform
import sys
from typing import Callable, List, Optional

from . import __version__, autostart
from .config import (
    Config,
    default_config_path,
    has_keyring,
    _keyring_set,
)
from .detector import check_online, detect
from .providers import PROVIDERS, fingerprint
from .detector import DetectContext
from .runner import Runner
from .session import Session, local_ip, local_mac

# -------------------------------------------------------------------- 输出
LEVEL_MARK = {
    "debug": ("·", "90"),
    "info": ("•", "36"),
    "ok": ("✔", "32"),
    "warn": ("!", "33"),
    "error": ("✘", "31"),
}


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if platform.system() == "Windows":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:  # noqa: BLE001
            return False
    return True


class Console:
    """极简控制台输出（不依赖 colorama）。"""

    def __init__(self, verbose: bool = False, quiet: bool = False) -> None:
        self.verbose = verbose
        self.quiet = quiet
        self.color = _supports_color()

    def __call__(self, message: str, level: str = "info") -> None:
        if level == "debug" and not self.verbose:
            return
        if self.quiet and level in ("info", "debug"):
            return
        mark, code = LEVEL_MARK.get(level, ("•", "0"))
        if self.color:
            print("  \033[{}m{}\033[0m {}".format(code, mark, message))
        else:
            print("  {} {}".format(mark, message))

    def raw(self, text: str = "") -> None:
        if not self.quiet:
            print(text)

    def banner(self, text: str) -> None:
        if self.quiet:
            return
        line = "─" * max(8, min(60, len(text) + 4))
        print("\n" + line)
        print("  " + text)
        print(line)


# -------------------------------------------------------------------- 通用
def _load(args) -> Config:
    cfg = Config.load(getattr(args, "config", None) or default_config_path())
    if getattr(args, "username", None):
        cfg.username = args.username
    if getattr(args, "provider", None):
        cfg.provider = args.provider
    if getattr(args, "portal", None):
        cfg.portal_ip = args.portal
    if getattr(args, "timeout", None):
        cfg.timeout = args.timeout
    return cfg


def _make_runner(args) -> Runner:
    return Runner(_load(args), Console(verbose=getattr(args, "verbose", False)))


# -------------------------------------------------------------------- 子命令
def cmd_status(args) -> int:
    cfg = _load(args)
    console = Console(verbose=args.verbose)
    session = Session(timeout=cfg.timeout, use_proxy=cfg.use_proxy)
    status = check_online(session)

    console.banner("campusnet 状态")
    console("网络：{}".format(status.describe()), "ok" if status.online else "warn")
    if status.portal_url:
        console("门户：{}".format(status.portal_url), "info")

    detection = detect(session, cfg, status)
    if detection.scores:
        console("认证系统：{}".format(
            ", ".join("{} {:.2f}".format(n, s) for n, s in detection.scores)), "info")
    if detection.server:
        console("服务器：{}".format(detection.server), "info")

    console("本机 IP：{}".format(local_ip() or "未知"), "info")
    console("本机 MAC：{}".format(local_mac() or "未知"), "info")
    console("账号：{}".format(cfg.username or "（未配置）"), "info")
    console("密码：{}".format(cfg.masked()), "info")
    console("配置：{}".format(cfg.path or default_config_path()), "info")
    console("自启：{}".format(autostart.status().splitlines()[0]), "info")
    return 0 if status.online else 1


def cmd_detect(args) -> int:
    cfg = _load(args)
    console = Console(verbose=args.verbose)
    session = Session(timeout=cfg.timeout, use_proxy=cfg.use_proxy)

    status = check_online(session)
    console.banner("门户探测")
    console("网络：{}".format(status.describe()), "ok" if status.online else "warn")

    detection = detect(session, cfg, status)
    if not detection.portal:
        if status.online:
            console("你现在已经联网，门户页面不会出现，所以探不到。", "warn")
            console("想让 campusnet 也认识你家学校的门户，可以：", "info")
            console("  1) 断开当前认证（或等下次开机会话失效）后重跑 detect；", "info")
            console("  2) 或者直接指定地址：campusnet detect --portal 10.0.0.1", "info")
        else:
            console("没能探到门户地址。自动探测也失败了，请用 --portal 手动指定，", "error")
            console("例如：campusnet detect --portal 10.0.0.1", "error")
        return 1

    console("门户地址：{}".format(detection.portal.rstrip("/")), "ok")
    console("HTTP：{}  Server：{}".format(detection.status, detection.server or "-"), "info")
    console("页面标题：{}".format(detection.title or "-"), "info")
    for key, value in detection.notes.items():
        if value:
            console("{}：{}".format(key, value), "info")

    console.raw()
    if detection.scores:
        console("指纹识别结果：", "ok")
        for name, score in detection.scores:
            console("  {:<10} {:.2f}  {}".format(name, score, PROVIDERS[name].display_name), "info")
    else:
        console("没有匹配到已知认证系统。请把上面的信息发到 issue，或改用 custom provider。", "warn")

    console.raw()
    console("提示：可以把门户地址写进配置 portal_ip，省去每次探测。", "debug")
    return 0


def cmd_login(args) -> int:
    runner = _make_runner(args)
    console = Console(verbose=args.verbose)
    result = runner.ensure_online(force=args.force, limit=3)
    if result.skipped:
        console(result.message, "ok")
        return 0
    if result.ok:
        console(result.message, "ok")
        return 0
    console(result.message, "error")
    return 1


def cmd_watch(args) -> int:
    runner = _make_runner(args)
    console = Console(verbose=args.verbose, quiet=getattr(args, "quiet", False))
    console.banner("campusnet 守护模式")
    try:
        runner.watch(interval_minutes=args.interval)
    except KeyboardInterrupt:
        return 0
    return 0


def cmd_providers(args) -> int:
    console = Console()
    console.banner("支持的认证系统")
    for name, cls in PROVIDERS.items():
        console("{:<9} {}".format(name, cls.display_name), "info")
    console.raw()
    console("用 --provider <名字> 强制指定；默认 auto 会自动识别。", "debug")
    return 0


def cmd_setup(args) -> int:
    console = Console()
    console.banner("campusnet 配置向导")

    path = args.config or default_config_path()
    cfg = Config.load(path)

    # 1) 账号
    default_user = cfg.username
    prompt = "上网账号（学号）"
    if default_user:
        prompt += " [{}]".format(default_user)
    try:
        entered = input("  {}：".format(prompt)).strip()
    except EOFError:
        entered = ""
    cfg.username = entered or default_user
    if not cfg.username:
        console("没有账号，取消。", "error")
        return 2

    # 2) 密码
    import getpass

    try:
        password = getpass.getpass("  密码（输入时不显示）：")
    except EOFError:
        password = ""
    if not password:
        console("没有输入密码，取消。", "error")
        return 2

    save_to = "none"
    if args.save_password:
        save_to = "config"
    elif has_keyring():
        try:
            answer = input("  检测到系统钥匙串，把密码存进去吗？[Y/n] ").strip().lower()
        except EOFError:
            answer = "y"
        if answer in ("", "y", "yes"):
            save_to = "keyring"

    if save_to == "keyring" and _keyring_set(cfg.username, password):
        cfg.password = ""
        cfg.password_source = "keyring"
        console("密码已存入系统钥匙串", "ok")
    elif save_to == "config":
        cfg.password = password
        cfg.password_source = "config"
        console("警告：密码将以明文写入 {}".format(path), "warn")
    else:
        cfg.password = ""
        console("密码未保存 —— 请用环境变量 CAMPUSNET_PASSWORD 提供", "warn")
    del password

    # 3) 探测门户
    console.raw()
    console("正在探测认证门户…", "info")
    session = Session(timeout=cfg.timeout, use_proxy=cfg.use_proxy)
    status = check_online(session)
    detection = detect(session, cfg, status)
    if detection.portal:
        console("发现门户：{}".format(detection.portal.rstrip("/")), "ok")
        cfg.portal_ip = detection.portal.rstrip("/")
        if detection.scores:
            console("认证系统：{}".format(detection.scores[0][0]), "ok")
            cfg.provider = "auto"
    else:
        console("没探测到门户，稍后可手动填 portal_ip", "warn")

    # 4) Wi-Fi 名称（可选）
    try:
        ssid = input("  Wi-Fi 名称（可留空）：").strip()
    except EOFError:
        ssid = ""
    if ssid:
        cfg.wifi_ssid = ssid

    cfg.path = path
    saved = cfg.save(path)
    console.raw()
    console("配置已保存：{}".format(saved), "ok")
    console("下一步：campusnet login", "info")
    return 0


def cmd_autostart(args) -> int:
    console = Console()
    cfg = _load(args)
    action = args.action
    if action == "install":
        console.banner("安装开机自启")
        try:
            console(autostart.install(cfg.path or default_config_path(), args.interval), "ok")
        except Exception as exc:  # noqa: BLE001
            console("安装失败：{}".format(exc), "error")
            return 1
        return 0
    if action == "uninstall":
        console.banner("卸载开机自启")
        console(autostart.uninstall(), "ok")
        return 0
    console.banner("开机自启状态")
    console(autostart.status(), "info")
    return 0


# -------------------------------------------------------------------- 解析
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="campusnet",
        description="校园网 Portal 自动登录：Dr.COM / 深澜 Srun / 锐捷 / 华为 eportal，零依赖。",
        epilog="更多用法见 README.md",
    )
    parser.add_argument("--version", action="version", version="campusnet {}".format(__version__))
    parser.add_argument("-c", "--config", help="配置文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印每个 HTTP 请求的细节")
    parser.add_argument("--timeout", type=int, help="单次请求超时（秒）")

    subs = parser.add_subparsers(dest="command")

    def add(name: str, help_text: str, func: Callable, **kwargs):
        sub = subs.add_parser(name, help=help_text, **kwargs)
        sub.set_defaults(func=func)
        return sub

    p_setup = add("setup", "交互式生成配置", cmd_setup)
    p_setup.add_argument("--save-password", action="store_true",
                         help="把密码明文写进配置文件（不推荐）")

    p_detect = add("detect", "探测门户并做指纹识别", cmd_detect)
    p_detect.add_argument("--portal", help="直接指定门户地址，跳过自动探测")

    p_login = add("login", "登录一次", cmd_login)
    p_login.add_argument("--force", action="store_true", help="即使已联网也重新认证")
    p_login.add_argument("--provider", help="强制使用某个认证方式")
    p_login.add_argument("--portal", help="指定门户地址")
    p_login.add_argument("--username", help="临时覆盖账号")

    p_watch = add("watch", "常驻守护，定时检查并自动补登录", cmd_watch)
    p_watch.add_argument("--interval", type=int, default=10, help="检查间隔（分钟，默认 10）")
    p_watch.add_argument("--provider", help="强制使用某个认证方式")
    p_watch.add_argument("-q", "--quiet", action="store_true", help="静默（用于开机自启）")

    add("status", "查看联网状态", cmd_status)
    add("providers", "列出支持的认证系统", cmd_providers)

    p_auto = add("autostart", "管理开机自启", cmd_autostart)
    p_auto.add_argument("action", choices=["install", "uninstall", "status"])
    p_auto.add_argument("--interval", type=int, default=10, help="守护间隔（分钟）")
    p_auto.add_argument("--portal", help="门户地址")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI 顶层兜底，别把 traceback 摔用户脸上
        console = Console(verbose=getattr(args, "verbose", False))
        console("出错了：{}".format(exc), "error")
        if getattr(args, "verbose", False):
            raise
        return 1
