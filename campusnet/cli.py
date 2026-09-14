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
from . import carrier, wifi

# -------------------------------------------------------------------- 输出
#: 日志级别 → (Unicode 标记, 颜色码, ASCII 降级标记)
LEVEL_MARK = {
    "debug": ("·", "90", "."),
    "info": ("•", "36", "-"),
    "ok": ("✔", "32", "v"),
    "warn": ("!", "33", "!"),
    "error": ("✘", "31", "x"),
}

#: 装饰性字符的 ASCII 替代。控制台编码编不出这些符号时用它，避免直接崩。
ASCII_TRANSLATION = {
    ord("─"): "-", ord("│"): "|", ord("✔"): "v", ord("✘"): "x",
    ord("•"): "-", ord("·"): ".", ord("★"): "*", ord("→"): "->",
    ord("…"): "...",
}


def _stream_encoding(stream) -> str:
    return getattr(stream, "encoding", None) or "ascii"


def _can_encode(stream, text: str) -> bool:
    """这个输出流编不编得出这段文本。"""
    try:
        text.encode(_stream_encoding(stream))
        return True
    except (UnicodeEncodeError, LookupError, TypeError):
        return False


def _safe_write(stream, text: str) -> None:
    """写不出去也绝不能崩。

    中文 Windows 的控制台是 cp936，显示中文没问题；但 GitHub Actions 的 Windows
    runner（cp1252）连中文都编不出来，直接 ``print`` 会抛 ``UnicodeEncodeError``
    把整个命令打挂 —— 这曾让 Windows 上三个 Python 版本的 CI 全红。
    这里做两级兜底：先原样写，不行就退到 ASCII 替代字符再写。
    """
    if stream is None:
        return
    try:
        stream.write(text)
        return
    except UnicodeEncodeError:
        pass
    enc = _stream_encoding(stream)
    try:
        stream.write(text.translate(ASCII_TRANSLATION).encode(enc, "replace").decode(enc, "replace"))
    except Exception:  # noqa: BLE001 - 实在写不出去就放弃输出，但绝不抛
        pass


def ensure_output_encoding() -> None:
    """需要时才把标准输出切到 UTF-8。

    只在这台机器的默认编码确实编不出中文/装饰字符时才切 —— 中文 Windows 的 cp936
    本来就能显示中文，强行改 UTF-8 反而会在老终端里变乱码。
    """
    probe = "中文 ✔ ─ •"
    for stream in (sys.stdout, sys.stderr):
        if stream is None or _can_encode(stream, probe):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 切不了就走 _safe_write 的 ASCII 兜底
            pass


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
    """极简控制台输出（不依赖 colorama，且在编不出中文的控制台上也不会崩）。"""

    def __init__(self, verbose: bool = False, quiet: bool = False) -> None:
        self.verbose = verbose
        self.quiet = quiet
        self.ascii_only = not _can_encode(sys.stdout, "中文 ✔ ─")
        self.color = _supports_color() and not self.ascii_only

    def _mark(self, level: str) -> str:
        unicode_mark, _color, ascii_mark = LEVEL_MARK.get(level, ("•", "0", "-"))
        return ascii_mark if self.ascii_only else unicode_mark

    def __call__(self, message: str, level: str = "info") -> None:
        if level == "debug" and not self.verbose:
            return
        if self.quiet and level in ("info", "debug"):
            return
        if self.ascii_only:
            message = message.translate(ASCII_TRANSLATION)
        mark = self._mark(level)
        if self.color:
            color = LEVEL_MARK.get(level, ("", "0", ""))[1]
            _safe_write(sys.stdout, "  \033[{}m{}\033[0m {}\n".format(color, mark, message))
        else:
            _safe_write(sys.stdout, "  {} {}\n".format(mark, message))

    def raw(self, text: str = "") -> None:
        if not self.quiet:
            _safe_write(sys.stdout, text + "\n")

    def banner(self, text: str) -> None:
        if self.quiet:
            return
        char = "-" if self.ascii_only else "─"
        line = char * max(8, min(60, len(text) + 4))
        _safe_write(sys.stdout, "\n" + line + "\n  " + text + "\n" + line + "\n")


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
    if getattr(args, "carrier", None):
        cfg.options["carrier"] = carrier.normalize(args.carrier)
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

    # 运营商没设对，账号密码再对也认证不上，所以状态里要能看见
    current_carrier = str(cfg.options.get("carrier", "") or "")
    if current_carrier:
        console("运营商：{}".format(carrier.label(carrier.normalize(current_carrier))), "info")
    else:
        console("运营商：未设置（校园用户；要选运营商的话用 campusnet carrier 移动）", "info")

    # Wi-Fi 是最容易出问题的一环，状态里必须能看到
    if cfg.wifi_ssid:
        now = wifi.current_ssid()
        on_target = now == cfg.wifi_ssid
        console("校园 Wi-Fi：{}（当前 {}{}）".format(
            cfg.wifi_ssid,
            now or "未连接",
            "" if on_target else " ← 不一致，登录时会自动切回",
        ), "ok" if on_target else "warn")
    else:
        console("校园 Wi-Fi：（未配置）", "warn")

    console("配置：{}".format(cfg.path or default_config_path()), "info")
    console("自启：{}".format(autostart.status().splitlines()[0]), "info")
    # status 是「报告状态」，未联网是正常信息，不该算命令失败；
    # 需要脚本判断时用 --check。
    if getattr(args, "check", False):
        return 0 if status.online else 1
    return 0


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
    if getattr(args, "wifi", None):
        runner.cfg.wifi_ssid = args.wifi
    console = Console(verbose=args.verbose, quiet=getattr(args, "quiet", False))
    console.banner("campusnet 守护模式")
    try:
        runner.watch(interval_minutes=args.interval)
    except KeyboardInterrupt:
        return 0
    return 0


def cmd_wifi(args) -> int:
    """查看/管理 Wi-Fi：诊断、切换、以及关闭其它网络的自动连接。"""
    console = Console(verbose=args.verbose)
    cfg = _load(args)
    target = args.ssid or cfg.wifi_ssid

    action = args.action

    if action == "set":
        name = (args.ssid or "").strip()
        if not name:
            console("用法：campusnet wifi set <校园网名称>", "error")
            return 2
        cfg.wifi_ssid = name
        saved = cfg.save(cfg.path or default_config_path())
        console.banner("已设置校园 Wi-Fi")
        console("校园网：{}".format(name), "ok")
        console("配置：{}".format(saved), "info")
        console.raw()
        console("现在 campusnet login 和守护模式都会先确认连在「{}」上。".format(name), "info")
        console("建议再执行一次，把其它网络的自动连接关掉（治本）：", "info")
        console("  campusnet wifi autoconnect", "info")
        return 0

    if action == "restore":
        name = (args.ssid or "").strip()
        if not name:
            console("用法：campusnet wifi restore <名称>", "error")
            return 2
        console.banner("恢复自动连接")
        if wifi.set_autoconnect(name, enabled=True):
            console("已把「{}」改回自动连接".format(name), "ok")
            return 0
        console("没能改「{}」的设置（可能名称不对或没有权限）".format(name), "error")
        return 1

    if action == "list":
        console.banner("附近的 Wi-Fi")
        found = wifi.scan()
        if not found:
            # 扫不到不等于命令失败：CI/服务器的机器本来就没有无线网卡。
            # 返回非零会让 `run: |` 里的脚本步骤整体变红，所以这里是 0。
            console("扫描不到网络（可能没开无线网卡，或命令不可用）", "warn")
            return 0
        for item in found:
            mark = "ok" if target and item.ssid == target else "info"
            suffix = "  ← 校园网" if target and item.ssid == target else ""
            console(item.ssid + suffix, mark)
        return 0

    if action == "connect":
        if not target:
            console("没指定 Wi-Fi 名称。用 campusnet wifi connect <名称>，或先写进配置。", "error")
            return 2
        console.banner("连接 Wi-Fi")
        result = wifi.connect(target)
        console(result.message, "ok" if result.ok else "error")
        return 0 if result.ok else 1

    if action == "autoconnect":
        if not target:
            console("没指定校园 Wi-Fi 名称，无法判断该保留哪个。", "error")
            return 2
        console.banner("关闭其它 Wi-Fi 的自动连接")
        console("校园网：{}".format(target), "info")
        console("其它网络会被改成「手动连接」——开机时系统就不会抢它们了。", "info")
        console.raw()
        changed = wifi.forget_other_networks(target, logger=lambda m, lv="info": console(m, lv))
        if not changed:
            # 同上：这台机器根本没有无线网卡时不该算失败。
            # 只有「平台支持却一个都没改成」才值得报警告。
            console("没有改动任何设置（可能不支持，或本来就都对）", "warn")
            return 0
        console.raw()
        console("完成。想恢复某个网络，用：campusnet wifi restore <名称>", "info")
        return 0

    # 默认：诊断报告
    console.banner("Wi-Fi 状态")
    report = wifi.probe_report(target)
    for line in report.splitlines():
        console(line, "info")

    if not cfg.wifi_ssid:
        console.raw()
        console("提示：配置里没写 Wi-Fi 名称，所以不会自动切换网络。", "warn")
        console("加上它就能解决「开机连到别的 WiFi 后不回校园网」的问题：", "info")
        console("  campusnet wifi set JOU", "info")
    elif target and wifi.current_ssid() != target:
        console.raw()
        console("现在没连在校园网上，执行 campusnet login 会自动切回去。", "warn")
    return 0


def cmd_carrier(args) -> int:
    """查看/设置运营商。

    很多学校登录页上要先选「服务类型」（校园用户 / 校园电信 / 移动 / 联通 …），
    这一步没选对，账号密码再对也认证不上。
    """
    console = Console()
    cfg = _load(args)

    if args.name:
        code = carrier.normalize(args.name)
        cfg.options["carrier"] = code
        saved = cfg.save(cfg.path or default_config_path())
        console.banner("运营商已设置")
        console("运营商：{}".format(carrier.label(code)), "ok")
        if not carrier.is_known(code):
            console("（这是自定义值，会当作账号后缀 @{} 使用）".format(code), "warn")
        console("配置：{}".format(saved), "info")
        console.raw()
        console("下一步：campusnet login 验证一下", "info")
        return 0

    console.banner("运营商设置")
    current = str(cfg.options.get("carrier", "") or "")
    if current:
        code = carrier.normalize(current)
        console("当前：{}".format(carrier.label(code)), "ok")
    else:
        console("当前：未设置（等同于「校园用户」）", "warn")
        console.raw()
        console("如果你的学校登录时要选运营商，那这一步一定要设：", "info")

    console.raw()
    console("可选值：", "info")
    for code, text in carrier.CHOICES:
        console("  {:<10} {}".format(code, text), "info")
    console.raw()
    console("用法：campusnet carrier 移动", "info")
    console("也可以直接写自己的运营商名，会当作账号后缀处理。", "debug")
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

    # 4) 运营商 —— 很多学校登录时要先选「校园/移动/电信/联通」
    console.raw()
    console("有些学校登录时要先选运营商（页面上的「服务类型」）。", "info")
    console("不选会影响认证，不确定就按你办宽带的那家选。", "info")
    current = str(cfg.options.get("carrier", "") or "")
    if current:
        console("当前设置：{}".format(carrier.label(carrier.normalize(current))), "debug")
    for index, (code, text) in enumerate(carrier.CHOICES, 1):
        console("  {}. {}".format(index, text), "info")
    console("  0. 不选 / 跳过（我们学校不用选）", "info")
    try:
        picked = input("  选择 [1]：").strip()
    except EOFError:
        picked = ""
    if picked in ("0",):
        cfg.options.pop("carrier", None)
        console("已跳过运营商设置", "info")
    else:
        if picked.isdigit() and 1 <= int(picked) <= len(carrier.CHOICES):
            code = carrier.CHOICES[int(picked) - 1][0]
        elif picked:
            # 用户直接打字输入运营商名，比如「移动」或「中国移动」
            code = carrier.normalize(picked)
            if not carrier.is_known(code):
                console("没认出来，将按自定义运营商处理：{}".format(code), "warn")
        else:
            code = current_code if (current_code := carrier.normalize(current)) else "campus"
        cfg.options["carrier"] = code
        console("运营商：{}".format(carrier.label(code)), "ok")

    # 5) Wi-Fi 名称（可选，但强烈建议填）
    console.raw()
    console("校园 Wi-Fi 名称可以解决「开机连到别的网络就不回校园网」的问题。", "info")
    detected = wifi.current_ssid()
    if detected:
        console("当前连的是：{}".format(detected), "debug")
    hint = " [{}]".format(cfg.wifi_ssid) if cfg.wifi_ssid else ""
    try:
        ssid = input("  校园 Wi-Fi 名称（留空跳过）{}：".format(hint)).strip()
    except EOFError:
        ssid = ""
    if not ssid and cfg.wifi_ssid:
        ssid = cfg.wifi_ssid
    if ssid:
        cfg.wifi_ssid = ssid
        console("已记住校园网：{}".format(ssid), "ok")
    else:
        console("没填 —— 宿主机换过 Wi-Fi 后可能连不回校园网", "warn")

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
    p_login.add_argument("--carrier", help="运营商（如 移动 / 电信 / 联通 / 校园用户）")

    p_watch = add("watch", "常驻守护，定时检查并自动补登录", cmd_watch)
    p_watch.add_argument("--interval", type=int, default=10, help="检查间隔（分钟，默认 10）")
    p_watch.add_argument("--provider", help="强制使用某个认证方式")
    p_watch.add_argument("--wifi", help="校园 Wi-Fi 名称（覆盖配置；填了就会自动切网）")
    p_watch.add_argument("--carrier", help="运营商（如 移动 / 电信 / 联通 / 校园用户）")
    p_watch.add_argument("-q", "--quiet", action="store_true", help="静默（用于开机自启）")

    p_wifi = add("wifi", "查看/管理 Wi-Fi（诊断、切换、关闭其它网络自动连接）", cmd_wifi)
    p_wifi.add_argument("action", nargs="?", default="status",
                        choices=["status", "list", "connect", "autoconnect", "set", "restore"],
                        help="status 诊断 / list 扫描 / connect 连接 / "
                             "autoconnect 关闭其它自动连接 / set 记住校园网 / restore 恢复")
    p_wifi.add_argument("ssid", nargs="?", default="", help="Wi-Fi 名称")

    p_status = add("status", "查看联网状态", cmd_status)
    p_status.add_argument("--check", action="store_true",
                          help="未联网时以非零退出码返回，方便写进脚本")
    add("providers", "列出支持的认证系统", cmd_providers)

    p_carrier = add("carrier", "查看/设置运营商（登录前要选服务类型的学校用）", cmd_carrier)
    p_carrier.add_argument("name", nargs="?", default="",
                           help="运营商，如 移动 / 电信 / 联通 / 校园用户；留空则显示当前设置")

    p_auto = add("autostart", "管理开机自启", cmd_autostart)
    p_auto.add_argument("action", choices=["install", "uninstall", "status"])
    p_auto.add_argument("--interval", type=int, default=10, help="守护间隔（分钟）")
    p_auto.add_argument("--portal", help="门户地址")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    # 必须在解析参数之前调用：argparse 的 help 文本里也有中文，
    # 否则在编不出中文的控制台上 --help 就会崩。
    ensure_output_encoding()
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
