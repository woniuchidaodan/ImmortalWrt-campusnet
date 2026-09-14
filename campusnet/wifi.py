"""Wi-Fi 管理：读取当前 SSID、切回校园网、关掉别的网络的自动连接。

为什么需要这个模块
------------------

校园网认证只在**连上校园 Wi-Fi 之后**才有意义。而 Windows 有个很坑的默认行为：
你连过的每一个 Wi-Fi 都记着「自动连接」，谁先广播、信号强就连谁。

于是会出现这样的情况：

1. 你手动把 Wi-Fi 从 ``JOU`` 换成手机热点；
2. 关机再开机，系统直接连上手机热点（它也有自动连接）；
3. 热点能上网 → 联网探测通过 → 自动登录逻辑认为「已联网，无需认证」，
   根本不会去碰 Wi-Fi。

结果就是：**开机后一直挂在别的 Wi-Fi 上，校园网永远连不上。**

这个模块负责在认证之前把 Wi-Fi 抢回来。三个动作：

- :func:`current_ssid` —— 看现在连的是哪个网；
- :func:`ensure_wifi` —— 不是目标就 ``netsh wlan connect`` 连回去，并等它连上；
- :func:`forget_other_networks` —— **治本**：把其它网络的「自动连接」关掉，
  这样开机时系统就不会去抢那个热点。

三个平台都实现了，命令不存在或没有权限时**静默降级**，绝不抛异常。
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

#: 单条命令的超时（秒）。netsh 偶尔会卡住，必须兜住。
COMMAND_TIMEOUT = 10

#: 连接 Wi-Fi 后轮询等待的节奏：先密后疏，总共约 (3*5 + 17*3) ≈ 66 秒。
POLL_DELAYS: Sequence[float] = (0.5, 1, 1) + (3,) * 17


@dataclass
class WifiResult:
    """一次 Wi-Fi 操作的结果。"""

    ok: bool = False
    changed: bool = False
    ssid: str = ""
    message: str = ""
    target: str = ""
    supported: bool = True

    def describe(self) -> str:
        return self.message or ("已连接 {}".format(self.ssid) if self.ssid else "未知")


@dataclass
class WifiState:
    """当前无线接口状态。"""

    ssid: str = ""
    state: str = ""
    interface: str = ""
    profiles: List[str] = field(default_factory=list)

    @property
    def connected(self) -> bool:
        return bool(self.ssid)


# --------------------------------------------------------------------- 命令层
def _run(command: Sequence[str]) -> Tuple[int, str]:
    """跑一条命令，返回 ``(returncode, stdout)``。

    永远不抛异常 —— 没装命令、没权限、编码炸了，都算「没跑成」，
    调用方据此降级。中文 Windows 的 netsh 输出是 GBK，必须 ``errors="replace"``，
    否则解码异常会污染整条链路。
    """
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=COMMAND_TIMEOUT,
        )
    except Exception:  # noqa: BLE001 - 探测类操作不该影响主流程
        return 127, ""
    return completed.returncode, completed.stdout or ""


def _which(name: str) -> bool:
    import shutil

    return bool(shutil.which(name))


# --------------------------------------------------------------------- 读 SSID
#: ``netsh wlan show interfaces`` 的行格式随系统语言变化，用「中文名 | 英文名」双匹配。
#:
#: 注意 ``SSID`` 后面**不能**跟「名称」二字：``netsh wlan show profile`` 的输出里有
#: ``SSID 名称 :“JOU”`` 这一行，如果宽泛匹配就会把配置文件里的 SSID 当成当前
#: 正在连接的网络 —— 明明没连网却以为连上了，比不识别更糟。
_FIELD_SSID = re.compile(r"^\s*SSID\s*[:：]\s*(.*?)\s*$", re.I)
_FIELD_STATE = re.compile(r"^\s*(?:状态|State)\s*[:：]\s*(.+?)\s*$", re.I)
_FIELD_NAME = re.compile(r"^\s*(?:名称|Name)\s*[:：]\s*(.+?)\s*$", re.I)

#: netsh 在没连上时会输出空白或占位符，这些都算「没连」。
_EMPTY_SSID = ("", "-", "--", "n/a", "无", "none")

#: 「已连接」在各种语言下的写法。判断 SSID 非空其实就够，这只是辅助。
_CONNECTED_WORDS = ("已连接", "connected", "connected ")


def _parse_interface(text: str) -> WifiState:
    """从 ``netsh wlan show interfaces`` 的中文/英文输出里抠出关键字段。

    最容易踩的坑：``netsh wlan show profile`` 的输出里有一行
    ``SSID 名称 :“JOU”``。如果在全文里宽泛地找 ``SSID``，就会把**配置文件里
    记录的** SSID 当成**当前正连着的**网络 —— 没连网却以为连上了，比识别不出来
    更糟糕。所以这里做了两层防护：

    1. 只认 ``SSID`` 后紧跟冒号的写法，``SSID 名称`` 直接不匹配；
    2. 只在「接口名出现之后」才开始收 SSID（interfaces 输出的字段顺序固定），
       这就把 profile 输出里那种开头就出现 SSID 的情况也挡在外面。
    """
    state = WifiState()
    lines = (text or "").splitlines()

    # profile 输出会以「接口 X 上的配置文件 Y:」开头，遇到就说明给错了文本
    if lines and re.match(r"^\s*接口\s+\S+\s+上的配置文件", lines[0]):
        return state

    for line in lines:
        if not state.interface:
            match = _FIELD_NAME.match(line)
            if match:
                value = match.group(1).strip()
                if value and value.lower() not in ("name",):
                    state.interface = value
                continue

        if not state.ssid:
            match = _FIELD_SSID.match(line)
            if match:
                value = match.group(1).strip()
                if value not in _EMPTY_SSID:
                    # netsh 的中文 profile 输出用中文引号包住 SSID，顺手剥掉
                    state.ssid = value.strip("“”\"'")
                continue

        if not state.state:
            match = _FIELD_STATE.match(line)
            if match:
                state.state = match.group(1).strip()

    return state


def _parse_profiles(text: str) -> List[str]:
    """从 ``netsh wlan show profiles`` 里列出所有「所有用户配置文件」。"""
    profiles: List[str] = []
    for line in (text or "").splitlines():
        if ":" not in line and "：" not in line:
            continue
        line = line.replace("：", ":")
        head, _, tail = line.partition(":")
        if "所有用户配置文件" in head or "all user profile" in head.lower():
            name = tail.strip()
            if name:
                profiles.append(name)
    return profiles


def current_ssid() -> str:
    """当前连着的 Wi-Fi 名；没连 Wi-Fi 或取不到就返回空串。"""
    system = platform.system()
    if system == "Windows":
        code, output = _run(["netsh", "wlan", "show", "interfaces"])
        if code != 0 and not output:
            return ""
        return _parse_interface(output).ssid
    if system == "Darwin":
        code, output = _run(["networksetup", "-getairportnetwork", "en0"])
        if code != 0:
            return ""
        match = re.search(r"Current Wi-Fi Network:\s*(.+?)\s*$", output, re.M)
        return match.group(1).strip() if match else ""
    # Linux
    code, output = _run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    if code != 0:
        return ""
    for line in output.splitlines():
        if line.lower().startswith("yes:"):
            return line.split(":", 1)[1].strip()
    return ""


def _wifi_interface() -> str:
    """无线接口名（Linux/macOS 需要显式指定）。"""
    system = platform.system()
    if system == "Windows":
        return ""  # netsh 会自己挑；多接口时也可忽略
    if system == "Darwin":
        code, output = _run(["networksetup", "-listallhardwareports"])
        if code == 0:
            blocks = output.split("Hardware Port:")
            for block in blocks:
                if "Wi-Fi" in block or "AirPort" in block:
                    match = re.search(r"Device:\s*(\S+)", block)
                    if match:
                        return match.group(1)
        return "en0"
    code, output = _run(["nmcli", "-t", "-f", "DEVICE,TYPE", "dev"])
    if code == 0:
        for line in output.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1] == "wifi":
                return parts[0]
    return ""


def saved_profiles() -> List[str]:
    """已保存的 Wi-Fi 列表（Windows/Linux；macOS 不支持，返回空）。"""
    system = platform.system()
    if system == "Windows":
        code, output = _run(["netsh", "wlan", "show", "profiles"])
        return _parse_profiles(output) if code == 0 or output else []
    if system == "Darwin":
        return []
    code, output = _run(["nmcli", "-t", "-f", "NAME", "connection", "show"])
    if code != 0:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


# --------------------------------------------------------------------- 连接
def connect(ssid: str, timeout: float = 30.0, poll: bool = True) -> WifiResult:
    """连接到指定 Wi-Fi，并等它真的连上。

    ``netsh wlan connect`` 是**异步**的：命令立刻返回，实际关联要等一两秒。
    不等就往下跑认证，必然失败 —— 所以这里必须轮询。
    """
    ssid = (ssid or "").strip()
    if not ssid:
        return WifiResult(ok=False, message="没有指定要连接的 Wi-Fi 名称")

    system = platform.system()
    if system == "Windows":
        command = ["netsh", "wlan", "connect", "name={}".format(ssid), "ssid={}".format(ssid)]
    elif system == "Darwin":
        command = ["networksetup", "-setairportnetwork", _wifi_interface(), ssid]
    else:
        command = ["nmcli", "dev", "wifi", "connect", ssid]

    code, output = _run(command)
    if code != 0:
        detail = (output or "").strip().splitlines()
        reason = detail[-1] if detail else "命令执行失败"
        return WifiResult(ok=False, target=ssid,
                          message="连接「{}」失败：{}".format(ssid, reason))

    if not poll:
        return WifiResult(ok=True, ssid=ssid, target=ssid, changed=True,
                          message="已发起连接 {}".format(ssid))

    deadline = time.time() + max(5.0, timeout)
    for delay in POLL_DELAYS:
        if current_ssid() == ssid:
            return WifiResult(ok=True, ssid=ssid, target=ssid, changed=True,
                              message="已连接到 Wi-Fi「{}」".format(ssid))
        if time.time() >= deadline:
            break
        time.sleep(delay)

    return WifiResult(ok=False, ssid=current_ssid(), target=ssid,
                      message="已发起连接「{}」，但 {} 秒内没能连上".format(ssid, int(timeout)))


def disconnect() -> bool:
    """断开当前 Wi-Fi（仅 Windows/Linux）。"""
    system = platform.system()
    if system == "Windows":
        code, _ = _run(["netsh", "wlan", "disconnect"])
        return code == 0
    if system == "Linux":
        code, _ = _run(["nmcli", "dev", "disconnect", _wifi_interface()])
        return code == 0
    return False


# --------------------------------------------------------------------- 保底抢网
def ensure_wifi(
    ssid: str,
    timeout: float = 30.0,
    logger=None,
) -> WifiResult:
    """确保连的是 ``ssid``。

    - ``ssid`` 为空（没配）→ ``supported=False``，调用方应跳过 Wi-Fi 环节；
    - 已经连着目标 → 什么都不做；
    - 连着别的 → 直接切回目标，并等它连上。

    注意这里**只看当前连的是什么**，不看有没有网。因为「有网」恰恰是问题本身：
    连着手机热点一样有网，但我们需要的是校园网。
    """
    logger = logger or (lambda message, level="info": None)

    if not ssid:
        return WifiResult(ok=True, supported=False,
                          message="未配置 Wi-Fi 名称，跳过 Wi-Fi 检查")

    now = current_ssid()
    if now == ssid:
        return WifiResult(ok=True, ssid=now, target=ssid,
                          message="Wi-Fi 正常（{}）".format(ssid))

    if now:
        logger("当前 Wi-Fi 是「{}」，需要切回校园网「{}」…".format(now, ssid), "warn")
    else:
        logger("当前没有连接 Wi-Fi，尝试连接「{}」…".format(ssid), "warn")

    result = connect(ssid, timeout=timeout)
    if result.ok:
        logger(result.message, "ok")
    else:
        logger(result.message, "warn")
    return result


# --------------------------------------------------------------------- 治本
def set_autoconnect(profile: str, enabled: bool) -> bool:
    """打开/关闭某个 Wi-Fi 配置文件的「自动连接」。

    Windows 靠改写配置文件里的 ``connectionMode`` 实现，需要先导出 XML、
    改字段、再重新添加。看起来绕，但这是唯一不改注册表二进制的办法。
    """
    if platform.system() != "Windows":
        return False

    name = (profile or "").strip()
    if not name:
        return False

    want = "auto" if enabled else "manual"
    # 先看一眼现在是什么模式，省掉没必要的改写
    code, output = _run(["netsh", "wlan", "show", "profile", "name={}".format(name)])
    if code != 0 and not output:
        return False
    if re.search(r"(?:连接模式|Connection mode)\s*[:：]\s*(\S+)", output, re.I):
        match = re.search(r"(?:连接模式|Connection mode)\s*[:：]\s*(\S+)", output, re.I)
        current = (match.group(1) or "").lower()
        if enabled and current in ("auto", "自动", "自动连接"):
            return True
        if not enabled and current in ("manual", "手动"):
            return True

    # 导出 → 改 → 重新写回
    folder = tempfile.mkdtemp(prefix="campusnet-wifi-")
    xml_path = os.path.join(folder, "profile.xml")
    try:
        code, output = _run([
            "netsh", "wlan", "export", "profile",
            "name={}".format(name), "folder={}".format(folder),
        ])
        # 导出后的文件名等于配置文件名（可能被消毒过），扫一遍目录更稳
        candidates = [f for f in os.listdir(folder) if f.lower().endswith(".xml")]
        if not candidates:
            return False
        xml_path = os.path.join(folder, candidates[0])

        with open(xml_path, "r", encoding="utf-8", errors="replace") as fh:
            xml = fh.read()
        if "<connectionMode>" not in xml:
            return False

        new_xml = re.sub(
            r"<connectionMode>.*?</connectionMode>",
            "<connectionMode>{}</connectionMode>".format(want),
            xml,
            count=1,
            flags=re.S,
        )
        if new_xml == xml:
            return True  # 已经是想要的模式
        with open(xml_path, "w", encoding="utf-8") as fh:
            fh.write(new_xml)

        code, output = _run(["netsh", "wlan", "add", "profile",
                             "filename={}".format(xml_path), "user=all"])
        return code == 0
    except Exception:  # noqa: BLE001
        return False
    finally:
        # 注意：测试会把 mkdtemp 替换成临时目录，这里不能连带删掉它
        shutil.rmtree(folder, ignore_errors=True)


def forget_other_networks(keep: str, logger=None) -> List[str]:
    """把除 ``keep`` 之外所有 Wi-Fi 的「自动连接」关掉。

    这是**真正治本**的一步：只要别的网络不再自动连接，开机时系统就没得选，
    只能连校园网 —— 也就不需要每次开机都去抢网了。

    返回被改动的网络名列表。命令不可用或没权限时返回空列表，静默降级。
    """
    logger = logger or (lambda message, level="info": None)
    keep = (keep or "").strip()
    changed: List[str] = []

    if not keep:
        return changed
    if platform.system() not in ("Windows", "Linux"):
        # macOS 没有等价的「关掉单个网络的自动加入」接口，只能靠 ensure_wifi 抢
        return changed

    for name in saved_profiles():
        if name == keep:
            continue
        if set_autoconnect(name, enabled=False):
            changed.append(name)

    if changed:
        logger("已关闭 {} 个其它 Wi-Fi 的自动连接：{}".format(
            len(changed), "、".join(changed[:6]) + ("…" if len(changed) > 6 else "")), "ok")
    else:
        logger("没有需要调整的 Wi-Fi 自动连接设置", "debug")
    return changed


# --------------------------------------------------------------------- 扫描
def scan() -> List[WifiResult]:
    """列出附近可用的 Wi-Fi（用于 ``campusnet wifi`` 展示）。"""
    system = platform.system()
    if system == "Windows":
        code, output = _run(["netsh", "wlan", "show", "networks"])
        if code != 0 and not output:
            return []
        results: List[WifiResult] = []
        for line in output.splitlines():
            match = re.match(r"^\s*SSID\s+\d+\s*[:：]\s*(.+?)\s*$", line, re.I)
            if match:
                name = match.group(1).strip()
                if name:
                    results.append(WifiResult(ok=True, ssid=name, target=name, message=name))
        return results
    if system == "Darwin":
        code, output = _run(["/System/Library/PrivateFrameworks/Apple80211.framework/"
                             "Versions/Current/Resources/airport", "-s"])
        if code != 0:
            return []
        return [WifiResult(ok=True, ssid=line.split()[0], message=line.split()[0])
                for line in output.splitlines()[1:] if line.strip()]
    code, output = _run(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"])
    if code != 0:
        return []
    seen: List[str] = []
    for line in output.splitlines():
        name = line.strip()
        if name and name not in seen:
            seen.append(name)
    return [WifiResult(ok=True, ssid=n, message=n) for n in seen]


def supported() -> bool:
    """这个平台能不能管 Wi-Fi。"""
    system = platform.system()
    if system == "Windows":
        return _which("netsh") or sys.platform == "win32"
    if system == "Darwin":
        return _which("networksetup")
    return _which("nmcli")


def probe_report(target: str = "") -> str:
    """给 ``campusnet wifi`` 用的一小段人类可读报告。"""
    lines: List[str] = []
    state = WifiState()

    if platform.system() == "Windows":
        code, output = _run(["netsh", "wlan", "show", "interfaces"])
        state = _parse_interface(output)
        state.profiles = _parse_profiles(_run(["netsh", "wlan", "show", "profiles"])[1])
    else:
        state.ssid = current_ssid()
        state.profiles = saved_profiles()

    lines.append("无线接口：{}".format(state.interface or "（未知）"))
    lines.append("当前 SSID：{}".format(state.ssid or "（未连接）"))
    if state.state:
        lines.append("连接状态：{}".format(state.state))
    if target:
        lines.append("目标 SSID：{}".format(target))
        lines.append("是否在目标上：{}".format("是" if state.ssid == target else "否"))
    if state.profiles:
        lines.append("已保存 {} 个 Wi-Fi：{}".format(len(state.profiles), "、".join(state.profiles)))
    lines.append("管理能力：{}".format("可用" if supported() else "不可用（缺少命令）"))
    return "\n".join(lines)
