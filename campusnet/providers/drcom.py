"""Dr.COM 城市热点 Portal 认证。

实测于：江苏海洋大学（2026-09）

同一套服务器通常同时暴露两个接口，按成功率排序依次尝试：

1. 传统 JSONP 接口 —— 最干净，明文参数，返回结构化结果
   ``GET /drcom/login?callback=dr1003&DDDDD=<账号>&upass=<密码>&0MKKey=123456&...``
   返回 ``dr1003({"result":1,...})``，``result == 1`` 即成功。

2. 经典 eportal/ACSetting 接口（默认 801 端口）
   ``POST :801/eportal/?c=ACSetting&a=Login``，表单 ``DDDDD`` / ``upass``
   成功时返回 ``Dr.COMWebLoginID_3.htm`` 标记。

页面上那四个「服务类型」（校园用户 / 校园电信 / 校园联通 / 校园其他）
通过 ``R1`` / ``R3`` / ``para`` 三个参数区分，见 ``CARRIERS``。
"""

from __future__ import annotations

import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from .base import DetectContext, LoginResult, Provider
from ..session import local_ip, local_mac

#: 经典 ACSetting 接口的返回格式：``Msg=01;time=0;msga='无法获取用户认证账号！'``
MSG_PATTERN = re.compile(r"Msg\s*=\s*(\d+)\s*;\s*(?:time=\d+\s*;\s*)?msga\s*=\s*'([^']*)'", re.I)

#: 登录页上的「服务类型」→ (R1, R3, para, 账号后缀)
CARRIERS: Dict[str, Tuple[str, str, str, str]] = {
    "校园用户": ("0", "0", "00", ""),
    "校园电信": ("1", "0", "00", ""),
    "校园联通": ("0", "1", "00", ""),
    "校园其他": ("0", "0", "30", ""),
    "移动": ("0", "0", "30", "@cmcc"),
    "电信": ("0", "0", "00", "@telecom"),
    "联通": ("0", "0", "00", "@unicom"),
}

SUCCESS_MARKER = "Dr.COMWebLoginID_3.htm"
FAIL_MARKER = "Dr.COMWebLoginID_2.htm"


class DrComProvider(Provider):
    name = "drcom"
    display_name = "Dr.COM 城市热点"
    docs = "https://www.doctorcom.com/"
    min_confidence = 0.4

    # ------------------------------------------------------------ 指纹
    @classmethod
    def detect(cls, ctx: DetectContext) -> float:
        score = 0.0
        server = (ctx.headers.get("server") or "").lower()
        url = (ctx.url or "").lower()

        if "drcom" in server:
            score += 0.6
        if "dr.comwebloginid" in ctx.lower_text:
            score += 0.6
        if "drcomserver" in ctx.lower_text:
            score += 0.3
        if ctx.has("ddddd") and ctx.has("upass"):
            score += 0.4
        if "/eportal/" in url or "acsetting" in ctx.lower_text:
            score += 0.25
        if "v4serip" in ctx.lower_text or "mip=" in ctx.lower_text:
            score += 0.25
        if "城市热点" in ctx.text or "doctorcom" in ctx.lower_text:
            score += 0.5
        return min(score, 1.0)

    # ------------------------------------------------------------ 登录
    def login(self, portal: str, username: str, password: str, client_ip: str = "", mac: str = "") -> LoginResult:
        ip = client_ip or local_ip()
        mac = mac or local_mac()
        carrier = str(self.opt("carrier", "校园用户"))
        r1, r3, para, suffix = CARRIERS.get(carrier, CARRIERS["校园用户"])
        r1 = str(self.opt("r1", r1))
        r3 = str(self.opt("r3", r3))
        para = str(self.opt("para", para))
        user = username + str(self.opt("username_suffix", suffix))

        errors: List[str] = []

        for origin in self.origins(portal, extra_ports=(801, 803)):
            for attempt in self._attempts(origin, user, password, ip, mac, r1, r3, para):
                label, fn = attempt
                try:
                    result = fn()
                except Exception as exc:  # noqa: BLE001 - 换下一个接口继续试
                    errors.append("{}：{}".format(label, exc))
                    continue
                if result.ok or result.already_online:
                    return result
                errors.append("{}：{}".format(label, result.message))

        return LoginResult(
            ok=False,
            provider=self.name,
            message="所有 Dr.COM 接口均未成功。最后一次返回：{}".format(errors[-1] if errors else "无响应"),
            raw="\n".join(errors[-3:]),
        )

    # ------------------------------------------------------------ 内部
    def _attempts(self, origin: str, user: str, password: str, ip: str, mac: str, r1: str, r3: str, para: str):
        ts = int(time.time())
        q = (
            "DDDDD={u}&upass={p}&0MKKey={k}&R1={r1}&R2=&R3={r3}&R6=0"
            "&para={para}&v6ip=&v={ts}"
        ).format(u=quote(user, safe=""), p=quote(password, safe=""), k=self.opt("0MKKey", "123456"),
                 r1=r1, r3=r3, para=para, ts=ts)

        # 1) 传统 JSONP
        yield ("jsonp", lambda: self._as_result(
            self.session.get("{}?callback=dr1003&{}".format(origin + "/drcom/login", q),
                             headers={"Referer": origin + "/"}),
            origin + "/drcom/login",
        ))

        # 2) 经典 eportal / ACSetting（801 / 803）
        extra = (
            "&wlanuserip={ip}&wlanacip={ac}&mac={mac}&ip={ip}"
            "&enAdvert=0&queryACIP=0&loginMethod=1&url=drappall"
        ).format(ip=ip, ac=self.ip_from_portal(origin), mac=mac)
        yield ("eportal", lambda: self._as_result(
            self.session.post("{}?c=ACSetting&a=Login{}".format(origin + "/eportal/", extra),
                              data=q, headers={"Referer": origin + "/"}),
            origin + "/eportal/",
        ))

        # 3) 带 wlanuserip 的传统接口（部分学校要求）
        yield ("jsonp+wlanuserip", lambda: self._as_result(
            self.session.get("{}?callback=dr1003&{}{}".format(origin + "/drcom/login", q, extra),
                             headers={"Referer": origin + "/"}),
            origin + "/drcom/login",
        ))

    def _as_result(self, resp, endpoint: str) -> LoginResult:
        text = resp.text or ""
        payload = resp.jsonp_payload

        if payload:
            import json

            try:
                data = json.loads(payload)
            except ValueError:
                data = None
            if isinstance(data, dict):
                result = str(data.get("result", ""))
                msg = str(data.get("msga") or data.get("msg") or "")
                if result == "1":
                    return LoginResult(True, self.name, msg or "认证成功", endpoint=endpoint, raw=text[:600])
                if result in ("2", "3"):
                    return LoginResult(True, self.name, msg or "已在线上", endpoint=endpoint,
                                       raw=text[:600], already_online=True)
                return LoginResult(False, self.name, msg or "result={}".format(result),
                                   endpoint=endpoint, raw=text[:600])

        # 经典 ACSetting 接口用 Msg=NN;msga='...' 表达结果
        match = MSG_PATTERN.search(text)
        if match:
            code, message = match.group(1), match.group(2).strip()
            if code in ("00", "0"):
                return LoginResult(True, self.name, message or "认证成功", endpoint=endpoint, raw=text[:600])
            return LoginResult(False, self.name, "[{}] {}".format(code, message or "认证失败"),
                               endpoint=endpoint, raw=text[:600])

        if SUCCESS_MARKER in text:
            return LoginResult(True, self.name, "认证成功（页面标记）", endpoint=endpoint, raw=text[:600])
        if FAIL_MARKER in text:
            msg = self.find(r"msga\s*=\s*'([^']*)'", text) or "认证失败"
            return LoginResult(False, self.name, msg, endpoint=endpoint, raw=text[:600])
        if "无法获取用户认证账号" in text:
            return LoginResult(False, self.name, "接口未收到账号参数（试着换 provider？）",
                               endpoint=endpoint, raw=text[:600])

        return LoginResult(False, self.name, "HTTP {} 未识别响应".format(resp.status),
                           endpoint=endpoint, raw=text[:600])
