"""Wi-Fi 模块测试。

这个模块负责修一个很具体的 bug：用户手动切到别的 Wi-Fi 之后重启，
系统连上了那个网络，于是「有没有网」的探测通过，自动登录就再也不去碰 Wi-Fi 了。

所以测试的重点有两块：

1. **解析** —— ``netsh`` 的中/英文输出都要能抠出 SSID 和配置文件名；
   中文 Windows 的输出格式和英文版不一样，这是最容易埋雷的地方。
2. **顺序** —— ``Runner.ensure_online`` 必须**先切 Wi-Fi 再判联网**。
   顺序反了 bug 就回来了，所以专门有一条测试钉住它。
"""

from __future__ import annotations

import pytest

from campusnet import wifi
from campusnet.config import Config
from campusnet.runner import Runner

# ---------------------------------------------------------------- 真实 netsh 输出
#: 中文 Windows 的 ``netsh wlan show interfaces``（连上时）
INTERFACES_ZH_CONNECTED = """
系统上有 1 个接口:

    名称                   : WLAN
    说明            : Intel(R) Wi-Fi 6 AX201 160MHz
    GUID                   : 1c07918f-dc1b-4076-baf6-941e2fed7ed5
    物理地址       : 04:ec:d8:ef:a4:ac
    状态                  : 已连接
    SSID                   : JOU
    AP BSSID               : 74:4d:6d:77:bf:10
    波段                   : 5 GHz
    身份验证               : 开放式
    配置文件               : JOU
    已配置     QoS MSCS： 0
"""

#: 中文 Windows 的 ``netsh wlan show interfaces``（没连上时，SSID 是空白）
INTERFACES_ZH_DISCONNECTED = """
系统上有 1 个接口:

    名称                   : WLAN
    说明            : Intel(R) Wi-Fi 6 AX201 160MHz
    状态                  : 已断开连接
    SSID                   :
"""

#: 英文版
INTERFACES_EN_CONNECTED = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201 160MHz
    GUID                   : 1c07918f-dc1b-4076-baf6-941e2fed7ed5
    Physical address       : 04:ec:d8:ef:a4:ac
    State                  : connected
    SSID                   : Campus-Net
    BSSID                  : 74:4d:6d:77:bf:10
    Profile                : Campus-Net
"""

PROFILES_ZH = """
接口 WLAN 上的配置文件:

组策略配置文件(只读)
---------------------------------
    <无>

用户配置文件
-------------
    所有用户配置文件 : gggghhhhhh iPhone 17
    所有用户配置文件 : JOU
    所有用户配置文件 : WIFI-eryuan
    所有用户配置文件 : 思齐不挂科
    所有用户配置文件 : 404
"""

PROFILE_ZH_JOU = """
接口 WLAN 上的配置文件 JOU:
=======================================================================

已应用: 所有用户配置文件

配置文件信息
-------------------
    版本                   : 1
    类型                   : 无线局域网
    名称                   : JOU
    控制选项               :
        连接模式           : 自动连接
        网络广播           : 只在网络广播时连接
        AutoSwitch         : 请勿切换到其他网络
        MAC 随机化: 禁用

连接设置
---------------------
    SSID 数目              : 1
    SSID 名称              :“JOU”
"""


# --------------------------------------------------------------------- 解析
class TestParseInterface:
    def test_chinese_connected(self):
        state = wifi._parse_interface(INTERFACES_ZH_CONNECTED)
        assert state.ssid == "JOU"
        assert state.interface == "WLAN"
        assert state.state == "已连接"
        assert state.connected is True

    def test_chinese_disconnected_gives_empty_ssid(self):
        state = wifi._parse_interface(INTERFACES_ZH_DISCONNECTED)
        assert state.ssid == ""
        assert state.connected is False

    def test_english_connected(self):
        state = wifi._parse_interface(INTERFACES_EN_CONNECTED)
        assert state.ssid == "Campus-Net"
        assert state.interface == "Wi-Fi"

    def test_empty_input_does_not_crash(self):
        for text in ("", None, "乱码", "系统上没有无线接口"):
            state = wifi._parse_interface(text or "")
            assert state.ssid == ""

    def test_ssid_with_spaces_is_preserved(self):
        text = "    状态                  : 已连接\n    SSID                   : 我的 热点 2.4G\n"
        assert wifi._parse_interface(text).ssid == "我的 热点 2.4G"

    def test_chinese_ssid(self):
        text = "    状态                  : 已连接\n    SSID                   : 思齐不挂科\n"
        assert wifi._parse_interface(text).ssid == "思齐不挂科"

    def test_does_not_confuse_ssid_name_field(self):
        """``SSID 名称`` 出现在 profile 输出里，不能被当成当前 SSID。"""
        state = wifi._parse_interface(PROFILE_ZH_JOU)
        assert state.ssid == ""


class TestParseProfiles:
    def test_lists_all_user_profiles(self):
        profiles = wifi._parse_profiles(PROFILES_ZH)
        assert profiles == [
            "gggghhhhhh iPhone 17", "JOU", "WIFI-eryuan", "思齐不挂科", "404",
        ]

    def test_ignores_group_policy_section(self):
        assert "组策略配置文件(只读)" not in wifi._parse_profiles(PROFILES_ZH)

    def test_english_output(self):
        text = "    All User Profile     : Campus-Net\n    All User Profile     : Home\n"
        assert wifi._parse_profiles(text) == ["Campus-Net", "Home"]

    def test_empty(self):
        assert wifi._parse_profiles("") == []
        assert wifi._parse_profiles(None or "") == []


# --------------------------------------------------------------------- 连接逻辑
class TestEnsureWifi:
    def test_no_ssid_configured_is_supported_false(self):
        """没配 Wi-Fi 名称 → 完全不影响原有行为。"""
        result = wifi.ensure_wifi("")
        assert result.supported is False
        assert result.ok is True

    def test_already_on_target_does_nothing(self, monkeypatch):
        monkeypatch.setattr(wifi, "current_ssid", lambda: "JOU")
        called = []
        monkeypatch.setattr(wifi, "connect", lambda *a, **k: called.append(a))

        result = wifi.ensure_wifi("JOU")
        assert result.ok is True
        assert result.changed is False
        assert called == []  # 关键：不该发连接命令

    def test_switches_back_when_on_another_network(self, monkeypatch):
        """核心场景：连着别的网 → 必须切回校园网。"""
        state = {"ssid": "gggghhhhhh iPhone 17"}
        monkeypatch.setattr(wifi, "current_ssid", lambda: state["ssid"])

        def fake_connect(ssid, timeout=30.0, poll=True):
            state["ssid"] = ssid
            return wifi.WifiResult(ok=True, ssid=ssid, target=ssid, changed=True,
                                   message="已连接到 Wi-Fi「{}」".format(ssid))

        monkeypatch.setattr(wifi, "connect", fake_connect)

        result = wifi.ensure_wifi("JOU")
        assert result.ok is True
        assert result.changed is True
        assert result.ssid == "JOU"
        assert state["ssid"] == "JOU"

    def test_disconnected_then_connects(self, monkeypatch):
        monkeypatch.setattr(wifi, "current_ssid", lambda: "")
        monkeypatch.setattr(wifi, "connect",
                            lambda ssid, timeout=30.0, poll=True: wifi.WifiResult(
                                ok=True, ssid=ssid, target=ssid, changed=True))
        result = wifi.ensure_wifi("JOU")
        assert result.ok is True
        assert result.changed is True

    def test_connect_failure_is_reported_not_raised(self, monkeypatch):
        monkeypatch.setattr(wifi, "current_ssid", lambda: "别的网")
        monkeypatch.setattr(wifi, "connect",
                            lambda ssid, timeout=30.0, poll=True: wifi.WifiResult(
                                ok=False, target=ssid, message="连不上"))
        result = wifi.ensure_wifi("JOU")
        assert result.ok is False
        assert "连不上" in result.message

    def test_logs_a_warning_when_switching(self, monkeypatch):
        monkeypatch.setattr(wifi, "current_ssid", lambda: "别的网")
        monkeypatch.setattr(wifi, "connect",
                            lambda ssid, timeout=30.0, poll=True: wifi.WifiResult(
                                ok=True, ssid=ssid, changed=True))
        logs = []
        wifi.ensure_wifi("JOU", logger=lambda m, lv="info": logs.append((lv, m)))
        assert any(lv == "warn" for lv, _ in logs)


class TestConnect:
    def test_empty_ssid_rejected(self):
        result = wifi.connect("")
        assert result.ok is False

    def test_command_failure_reported(self, monkeypatch):
        monkeypatch.setattr(wifi, "_run", lambda cmd: (1, "配置文件不存在"))
        monkeypatch.setattr(wifi.platform, "system", lambda: "Windows")
        result = wifi.connect("不存在的网", poll=False)
        assert result.ok is False
        assert "不存在的网" in result.message

    def test_windows_command_shape(self, monkeypatch):
        seen = {}

        def fake_run(cmd):
            seen["cmd"] = cmd
            return 0, ""

        monkeypatch.setattr(wifi, "_run", fake_run)
        monkeypatch.setattr(wifi.platform, "system", lambda: "Windows")
        wifi.connect("JOU", poll=False)
        assert seen["cmd"] == ["netsh", "wlan", "connect", "name=JOU", "ssid=JOU"]

    def test_polls_until_associated(self, monkeypatch):
        """netsh connect 是异步的，必须轮询确认真的连上了。"""
        monkeypatch.setattr(wifi, "_run", lambda cmd: (0, ""))
        monkeypatch.setattr(wifi.platform, "system", lambda: "Windows")
        monkeypatch.setattr(wifi.time, "sleep", lambda s: None)

        calls = {"n": 0}

        def fake_ssid():
            calls["n"] += 1
            return "JOU" if calls["n"] >= 3 else "旧网络"

        monkeypatch.setattr(wifi, "current_ssid", fake_ssid)
        result = wifi.connect("JOU", timeout=30)
        assert result.ok is True
        assert calls["n"] >= 3


class TestAutoconnect:
    def test_noop_when_target_empty(self, monkeypatch):
        assert wifi.forget_other_networks("") == []

    def test_unsupported_on_macos(self, monkeypatch):
        monkeypatch.setattr(wifi.platform, "system", lambda: "Darwin")
        assert wifi.forget_other_networks("JOU") == []

    def test_disables_everything_but_target(self, monkeypatch):
        monkeypatch.setattr(wifi.platform, "system", lambda: "Windows")
        monkeypatch.setattr(wifi, "saved_profiles",
                            lambda: ["JOU", "热点A", "热点B"])

        touched = []

        def fake_set(profile, enabled):
            touched.append((profile, enabled))
            return True

        monkeypatch.setattr(wifi, "set_autoconnect", fake_set)
        changed = wifi.forget_other_networks("JOU")

        assert changed == ["热点A", "热点B"]
        assert all(enabled is False for _, enabled in touched)
        assert ("JOU", False) not in touched  # 校园网必须留着自动连接

    def test_failures_are_filtered_out(self, monkeypatch):
        monkeypatch.setattr(wifi.platform, "system", lambda: "Windows")
        monkeypatch.setattr(wifi, "saved_profiles", lambda: ["JOU", "A", "B"])
        monkeypatch.setattr(wifi, "set_autoconnect",
                            lambda p, enabled: p == "A")
        assert wifi.forget_other_networks("JOU") == ["A"]

    def test_rewrites_connection_mode(self, monkeypatch, tmp_path):
        """真改 XML 的那条路径：导出 → 替换 connectionMode → 写回。"""
        workdir = tmp_path / "wifi-export"
        workdir.mkdir()
        xml = (
            '<?xml version="1.0"?>\n<WLANProfile>\n  <name>热点A</name>\n'
            "  <connectionMode>auto</connectionMode>\n</WLANProfile>\n"
        )
        (workdir / "热点A.xml").write_text(xml, encoding="utf-8")

        commands = []

        def fake_run(cmd):
            commands.append(cmd)
            if "show" in cmd:
                return 0, "    连接模式           : 自动连接\n"
            if "export" in cmd:
                return 0, ""
            return 0, ""

        monkeypatch.setattr(wifi.platform, "system", lambda: "Windows")
        monkeypatch.setattr(wifi, "_run", fake_run)
        monkeypatch.setattr(wifi.tempfile, "mkdtemp",
                            lambda prefix="", **kw: str(workdir))
        # 生产代码在 finally 里会清掉临时目录，测试里必须挡掉，
        # 否则断言时文件已经被删了
        monkeypatch.setattr(wifi.shutil, "rmtree", lambda *a, **k: None)

        assert wifi.set_autoconnect("热点A", enabled=False) is True

        written = (workdir / "热点A.xml").read_text(encoding="utf-8")
        assert "<connectionMode>manual</connectionMode>" in written
        assert any("add" in c for c in commands)

    def test_skips_write_when_already_correct(self, monkeypatch):
        """已经是手动模式就别瞎折腾，避免反复重写 profile。"""
        monkeypatch.setattr(wifi.platform, "system", lambda: "Windows")
        monkeypatch.setattr(wifi, "_run", lambda cmd: (0, "    连接模式           : 手动\n"))
        assert wifi.set_autoconnect("热点A", enabled=False) is True


# --------------------------------------------------------------------- 顺序（回归）
class TestRunnerOrdering:
    """**最重要的测试**：先切 Wi-Fi，再判联网。顺序反了这个 bug 就回来了。"""

    def test_wifi_is_switched_before_online_check(self, monkeypatch):
        events = []

        monkeypatch.setattr("campusnet.runner.ensure_wifi",
                            lambda ssid, timeout=30.0, logger=None: (
                                events.append("wifi"),
                                wifi.WifiResult(ok=True, ssid="JOU", changed=True,
                                                target="JOU"))[1])

        cfg = Config(username="2024122304", wifi_ssid="JOU")
        runner = Runner(cfg)

        def fake_status():
            events.append("status")

            class S:
                online = True
                portal_url = ""
                detail = ""

                def describe(self):
                    return "已联网"

            return S()

        monkeypatch.setattr(runner, "status", fake_status)
        result = runner.ensure_online()

        assert events == ["wifi", "status"], "必须先切 Wi-Fi 再判联网"
        assert result.skipped is True  # 切回校园网之后确实已联网，直接收工

    def test_still_skips_when_no_wifi_configured(self, monkeypatch):
        """没配 wifi_ssid 的老用户行为完全不变。"""
        called = []
        monkeypatch.setattr("campusnet.runner.ensure_wifi",
                            lambda ssid, timeout=30.0, logger=None: called.append(ssid) or
                            wifi.WifiResult(ok=True, supported=False))

        cfg = Config(username="u")
        runner = Runner(cfg)

        class S:
            online = True
            portal_url = ""
            detail = ""

            def describe(self):
                return "已联网"

        monkeypatch.setattr(runner, "status", lambda: S())
        result = runner.ensure_online()
        assert called == [""]
        assert result.skipped is True

    def test_returns_run_result(self):
        """单个 provider 崩了不该炸整个 Runner —— 这条守住返回类型契约。"""
        from campusnet.runner import RunResult

        runner = Runner(Config(username="u", wifi_ssid=""))
        assert isinstance(RunResult(), RunResult)
        assert isinstance(runner, Runner)
