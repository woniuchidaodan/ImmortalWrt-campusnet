"""编排：探测 → 选择认证方式 → 登录 → 校验。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .config import Config
from .detector import Detection, NetStatus, check_online, detect, portal_candidates, provider_order
from .providers import LoginResult, get_provider
from .session import Session, local_ip, local_mac
from .wifi import WifiResult, ensure_wifi

LEVELS = ("debug", "info", "ok", "warn", "error")


def _null_log(message: str, level: str = "info") -> None:
    pass


@dataclass
class RunResult:
    ok: bool = False
    skipped: bool = False
    provider: str = ""
    message: str = ""
    status_before: Optional[NetStatus] = None
    detection: Optional[Detection] = None
    attempts: List[LoginResult] = field(default_factory=list)


class Runner:
    """把配置、HTTP 会话、provider 串起来。"""

    def __init__(self, cfg: Config, logger: Optional[Callable[[str, str], None]] = None) -> None:
        self.cfg = cfg
        self.log = logger or _null_log
        self._session: Optional[Session] = None
        #: 等 Wi-Fi 关联的超时（秒）。命令行可覆盖。
        self.wifi_timeout: float = float(cfg.options.get("wifi_timeout", 30))

    # ------------------------------------------------------------ 资源
    @property
    def session(self) -> Session:
        if self._session is None:
            self._session = Session(
                timeout=self.cfg.timeout,
                use_proxy=self.cfg.use_proxy,
                logger=lambda msg: self.log(msg, "debug"),
            )
        return self._session

    @property
    def client_ip(self) -> str:
        return local_ip()

    # ------------------------------------------------------------ 探测
    def status(self) -> NetStatus:
        hint = self.cfg.portal_ip and (self.cfg.portal_ip if "//" in self.cfg.portal_ip
                                       else "http://" + self.cfg.portal_ip + "/")
        return check_online(self.session, hint or "")

    def detect(self, status: Optional[NetStatus] = None) -> Detection:
        detection = detect(self.session, self.cfg, status)
        if detection.scores:
            self.log("识别到认证系统：{}（置信度 {:.2f}）".format(
                detection.best, detection.scores[0][1]), "ok")
        else:
            self.log("未能识别门户类型，将按通用顺序尝试", "warn")
        return detection

    # ------------------------------------------------------------ Wi-Fi
    def ensure_wifi(self) -> WifiResult:
        """把 Wi-Fi 抢回校园网。

        **必须在联网探测之前做。** 反过来就会出现这个 bug：

        连着手机热点 → 热点能上网 → 探测说「已联网」→ 直接返回，Wi-Fi 永远不切。

        所以这里的判断依据是「当前连的是不是校园网」，而不是「有没有网」。
        只有配置了 ``wifi_ssid`` 才会动手；没配就完全不影响原有行为。
        """
        result = ensure_wifi(self.cfg.wifi_ssid, timeout=self.wifi_timeout, logger=self.log)
        if not result.supported:
            self.log(result.message, "debug")
            return result
        if result.changed and result.ok:
            # 刚换了 Wi-Fi，DHCP 还没走完，给它一点时间再探测
            delay = float(self.cfg.options.get("wifi_settle_delay", 3))
            if delay:
                time.sleep(delay)
        return result

    # ------------------------------------------------------------ 主流程
    def ensure_online(self, force: bool = False, limit: int = 3) -> RunResult:
        cfg = self.cfg

        # 先抢 Wi-Fi，再判联网 —— 顺序不能反，理由见 ensure_wifi 的注释。
        self.ensure_wifi()

        status = self.status()
        if status.online and not force:
            return RunResult(ok=True, skipped=True, message="已联网，无需认证", status_before=status)

        if status.online and force:
            self.log("当前已联网，但指定了 --force，仍要重新认证一次", "warn")

        if not cfg.username:
            return RunResult(ok=False, message="配置里没有账号，请先运行：campusnet setup", status_before=status)

        password = cfg.resolve_password(prompt=False)
        if not password:
            return RunResult(ok=False,
                             message="没有取到密码。请设置 CAMPUSNET_PASSWORD 环境变量，或用 campusnet setup 配置",
                             status_before=status)

        detection = self.detect(status)
        portal = detection.portal or (portal_candidates(cfg, status) or [""])[0]
        if not portal:
            return RunResult(ok=False, message="找不到认证门户地址，请用 --portal 指定或写入配置",
                             status_before=status, detection=detection)

        order = provider_order(cfg, detection, limit=limit)
        self.log("认证门户：{}".format(portal.rstrip("/")), "info")
        self.log("尝试顺序：{}".format(" → ".join(order)), "info")

        ip, mac = self.client_ip, local_mac()
        attempts: List[LoginResult] = []

        for name in order:
            try:
                provider = get_provider(name)(self.session, cfg.options)
            except KeyError as exc:
                self.log(str(exc), "error")
                continue
            self.log("使用 {} 登录…".format(provider.display_name), "info")
            try:
                result = provider.login(portal, cfg.username, password, ip, mac)
            except Exception as exc:  # noqa: BLE001 - 单个 provider 崩了不该中断整体
                result = LoginResult(False, name, "内部异常：{}".format(exc))
            attempts.append(result)
            self.log(result.short(), "ok" if result.ok else "warn")

            if result.already_online:
                return RunResult(ok=True, provider=name, message=result.message,
                                 status_before=status, detection=detection, attempts=attempts)

            if not result.ok:
                if result.raw:
                    self.log(result.raw, "debug")
                continue

            # 接口说成功还不够，必须联网校验通过
            if force and status.online:
                return RunResult(ok=True, provider=name, message=result.message,
                                 status_before=status, detection=detection, attempts=attempts)

            wait = float(cfg.options.get("verify_delay", 2))
            if wait:
                time.sleep(wait)
            after = self.status()
            if after.online:
                return RunResult(ok=True, provider=name, message="认证成功，网络已连通",
                                 status_before=status, detection=detection, attempts=attempts)
            self.log("接口返回成功，但联网校验未通过，继续尝试其它方式", "warn")

        message = attempts[-1].message if attempts else "没有可用的认证方式"
        return RunResult(ok=False, message=message, status_before=status,
                         detection=detection, attempts=attempts)

    def watch(self, interval_minutes: int = 10, on_event: Optional[Callable[[RunResult], None]] = None):
        """常驻守护：联网正常时完全安静，断了就补登录。"""
        self.log("守护模式启动，每 {} 分钟检查一次".format(interval_minutes), "ok")
        if self.cfg.wifi_ssid:
            self.log("已配置校园 Wi-Fi「{}」，每轮都会确认是否连在它上面".format(self.cfg.wifi_ssid), "info")
        while True:
            try:
                # 每轮都先确认 Wi-Fi。用户随时可能手动切走，
                # 而切走之后「有网」反倒会掩盖问题。
                wifi = self.ensure_wifi()
                status = self.status()
                if not status.online:
                    self.log("检测到网络未认证，开始自动登录…", "warn")
                    result = self.ensure_online()
                    if on_event:
                        on_event(result)
                    self.log(result.message, "ok" if result.ok else "error")
                elif wifi.changed:
                    self.log("已切回校园 Wi-Fi，网络正常", "ok")
            except KeyboardInterrupt:
                self.log("收到中断，退出守护模式", "info")
                return
            except Exception as exc:  # noqa: BLE001 - 守护进程必须活到最后
                self.log("本轮检查出错：{}".format(exc), "error")
            time.sleep(max(30, interval_minutes * 60))
