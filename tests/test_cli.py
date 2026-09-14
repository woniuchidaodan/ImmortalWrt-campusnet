"""控制台输出在「编不出中文」的环境里也必须活着。

这块曾让 Windows 上的 CI 全红：GitHub Actions 的 Windows runner 控制台编码是
cp1252，编不出中文和 ``─`` ``✔`` 这类字符，``print`` 直接抛 ``UnicodeEncodeError``，
命令以退出码 1 结束。Linux/macOS 是 UTF-8 所以看不出来 —— 典型的"只在某个平台炸"。
"""

from __future__ import annotations

import io

import pytest

from campusnet import cli
from campusnet.detector import Detection, NetStatus


def cp1252_stream():
    """一个真实的 cp1252 输出流，用来模拟英文 Windows / CI runner。"""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")


# -------------------------------------------------------------------- 基础工具
def test_can_encode_reflects_stream_encoding():
    assert cli._can_encode(cp1252_stream(), "plain ascii")
    assert not cli._can_encode(cp1252_stream(), "中文")
    assert not cli._can_encode(cp1252_stream(), "✔")


def test_safe_write_does_not_raise_on_unencodable_text():
    stream = cp1252_stream()
    cli._safe_write(stream, "中文 ✔ ─ •\n")  # 以前这里必抛
    stream.flush()
    assert stream.buffer.getvalue(), "至少要写出去点东西"


def test_safe_write_prefers_exact_text_when_possible():
    stream = cp1252_stream()
    cli._safe_write(stream, "ok ✔\n")
    stream.flush()
    assert stream.buffer.getvalue().startswith(b"ok ")


def test_safe_write_tolerates_broken_stream():
    class Broken:
        encoding = "cp1252"

        def write(self, _text):
            raise UnicodeEncodeError("cp1252", "x", 0, 1, "boom")

    cli._safe_write(Broken(), "中文")  # 不能抛
    cli._safe_write(None, "中文")      # None 也要能忍


def test_decorative_chars_have_ascii_fallbacks():
    for char in "─│✔✘•·★→…":
        assert ord(char) in cli.ASCII_TRANSLATION
    assert "✔".translate(cli.ASCII_TRANSLATION) == "v"
    assert "─".translate(cli.ASCII_TRANSLATION) == "-"


# -------------------------------------------------------------------- Console
def test_console_detects_ascii_only_stream(monkeypatch):
    monkeypatch.setattr(cli.sys, "stdout", cp1252_stream())
    console = cli.Console()
    assert console.ascii_only is True
    assert console.color is False


def test_console_uses_ascii_marks_in_ascii_only_mode(monkeypatch):
    monkeypatch.setattr(cli.sys, "stdout", cp1252_stream())
    console = cli.Console()
    for level, expected in (("info", "-"), ("ok", "v"), ("error", "x")):
        assert console._mark(level) == expected


def test_console_output_never_raises(monkeypatch):
    """把 Console 的全部输出路径都跑一遍，一个都不许抛。"""
    stream = cp1252_stream()
    monkeypatch.setattr(cli.sys, "stdout", stream)
    console = cli.Console(verbose=True)

    for level in ("debug", "info", "ok", "warn", "error"):
        console("中文消息 ✔ ─ •", level)
    console.raw("裸输出 → 中文")
    console.banner("支持的认证系统")
    stream.flush()
    assert stream.buffer.getvalue()


# -------------------------------------------------------------------- 端到端
@pytest.mark.parametrize("argv", [
    ["providers"],
    ["autostart", "status"],
])
def test_commands_survive_cp1252_console(monkeypatch, argv):
    """这些命令复现过 CI 崩溃，现在必须正常返回。"""
    monkeypatch.setattr(cli.sys, "stdout", cp1252_stream())
    monkeypatch.setattr(cli.sys, "stderr", cp1252_stream())
    assert cli.main(argv) == 0


@pytest.mark.parametrize("argv", [
    ["--version"],
    ["--help"],
    ["detect", "--help"],
    ["login", "--help"],
])
def test_help_and_version_exit_cleanly_on_cp1252(monkeypatch, argv):
    monkeypatch.setattr(cli.sys, "stdout", cp1252_stream())
    monkeypatch.setattr(cli.sys, "stderr", cp1252_stream())
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    assert excinfo.value.code == 0


def test_status_reports_even_when_offline(monkeypatch):
    """status 是报告状态，未联网属于正常信息，不该算命令失败。"""
    monkeypatch.setattr(cli, "check_online", lambda *a, **k: NetStatus(online=False, detail="测试"))
    monkeypatch.setattr(cli, "detect", lambda *a, **k: Detection())
    monkeypatch.setattr(cli.autostart, "status", lambda: "未安装")

    stream = cp1252_stream()
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(cli.sys, "stderr", stream)

    assert cli.main(["status"]) == 0
    assert cli.main(["status", "--check"]) == 1


# -------------------------------------------------------------------- 无网卡的机器
#: 这一组修的是一个真实踩过的坑：CI 的 Ubuntu runner 没有无线网卡，
#: ``wifi list`` 扫不到任何网络就返回了 1，而 workflow 里写的是 ``run: |``，
#: 任意一条非零退出码会把整个步骤判红 —— 9 个 job 全挂。
#: 扫不到网络是**正常状态**，不是命令失败。
@pytest.mark.parametrize("argv", [
    ["wifi"],
    ["wifi", "status"],
    ["wifi", "list"],
    ["wifi", "autoconnect", "JOU"],
])
def test_wifi_reporting_exits_zero_without_adapter(monkeypatch, argv):
    """没有无线网卡的机器上，这些只是「报状态」的命令必须返回 0。"""
    monkeypatch.setattr(cli.wifi.platform, "system", lambda: "Linux")
    monkeypatch.setattr(cli.wifi, "scan", lambda: [])
    monkeypatch.setattr(cli.wifi, "saved_profiles", lambda: [])
    monkeypatch.setattr(cli.wifi, "current_ssid", lambda: "")
    monkeypatch.setattr(cli.wifi, "supported", lambda: False)

    stream = cp1252_stream()
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(cli.sys, "stderr", stream)

    assert cli.main(argv) == 0


def test_wifi_action_failure_is_still_nonzero(monkeypatch):
    """反过来说：真的“去连一个网”而失败了，必须返回非零。

    「报状态」和「执行动作」两种情况不能一刀切都返回 0。
    """
    monkeypatch.setattr(cli.wifi, "connect",
                        lambda ssid, **kw: cli.wifi.WifiResult(
                            ok=False, target=ssid, message="连不上"))

    stream = cp1252_stream()
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(cli.sys, "stderr", stream)

    assert cli.main(["wifi", "connect", "JOU"]) == 1
