# campusnet · 校园网自动登录

> 一行命令，自动登录校园网 Portal 认证。开机自动、断网自动、纯 Python 零依赖。

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#为什么零依赖)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)

每次重启电脑都要打开浏览器、输账号密码登校园网？`campusnet` 把这件事变成后台自动完成。

```console
$ campusnet status
✔ 已联网  ·  出口正常
  认证方式 : Dr.COM 城市热点
  本机 IP  : 10.190.51.27
  Wi-Fi    : JOU
```

---

## 特性

- **自动识别认证系统** —— 探测门户页面并指纹识别，不用你告诉它学校用的是哪家
- **多厂商支持** —— Dr.COM（城市热点）、深澜 Srun、锐捷 Ruijie、华为/eportal 通用接口、以及自定义模板
- **零第三方依赖** —— 只用 Python 标准库，`pip install` 不会拉一堆包，机房网络差也能装
- **跨平台开机自启** —— Windows 注册表 / macOS LaunchAgent / Linux systemd 用户服务
- **守护模式** —— 常驻后台定时检查，夜里断网、早上恢复后自动重新认证
- **不打扰** —— 已联网时直接退出，不产生任何多余请求
- **凭据安全** —— 优先读环境变量 / 系统钥匙串，明文落盘需要你显式同意
- **没有魔法** —— 所有请求都直接打到学校认证服务器，不经过任何中间服务

## 支持的认证系统

| Provider | 认证系统 | 状态 |
| --- | --- | --- |
| `drcom` | Dr.COM 城市热点（含 `:801/eportal/` ACSetting 兼容接口） | ✅ 已在江苏海洋大学实测 |
| `srun` | 深澜 Srun（`/cgi-bin/srun_portal`，含 `srun_bx1` 加密） | 已实现，待更多学校验证 |
| `ruijie` | 锐捷 Ruijie（`/eportal/InterFace.do`） | 已实现，待更多学校验证 |
| `eportal` | 华为 / 通用 eportal（`c=ACSetting&a=Login`） | 已实现，待更多学校验证 |
| `custom` | 自定义模板（自己填 URL 和字段名） | ✅ |
| `auto` | 自动探测，按置信度依次尝试 | ✅ |

没在上面？用 `campusnet detect` 把指纹打出来提个 issue，或者直接用 `custom` provider。

## 安装

```bash
pip install git+https://github.com/<you>/campusnet.git
```

或者克隆下来直接用，不需要安装：

```bash
git clone https://github.com/<you>/campusnet.git
cd campusnet
python -m campusnet status
```

要求 Python 3.8+，无第三方依赖。

## 快速开始

```bash
# 1. 生成配置（会交互式问账号密码，并自动探测你学校的认证方式）
campusnet setup

# 2. 登录一次试试
campusnet login

# 3. 装成开机自启
campusnet autostart install
```

完事。以后开机自动登录，不用管了。

## 命令

| 命令 | 作用 |
| --- | --- |
| `campusnet setup` | 交互式生成配置文件 |
| `campusnet detect` | 探测门户，打印指纹和推荐 provider |
| `campusnet login` | 登录一次（已联网则直接跳过，`--force` 强制重登） |
| `campusnet watch` | 常驻守护，定时检查并自动补登录 |
| `campusnet status` | 查看联网状态、识别到的认证方式、本机信息 |
| `campusnet providers` | 列出所有支持的认证系统 |
| `campusnet autostart install\|uninstall\|status` | 管理开机自启 |

常用参数：

```bash
campusnet login --config ./my.json      # 指定配置文件
campusnet login --provider srun         # 强制用某个 provider
campusnet watch --interval 5            # 每 5 分钟检查一次
campusnet detect --portal 10.0.0.55     # 直接探测指定地址
campusnet login --verbose               # 打印每个请求的细节，排查问题用
```

## 配置

默认路径：

| 平台 | 位置 |
| --- | --- |
| Windows | `%APPDATA%\campusnet\config.json` |
| macOS / Linux | `~/.config/campusnet/config.json` |

也可以用环境变量覆盖，适合 CI 或不想落盘：

```bash
export CAMPUSNET_USERNAME=2024123456
export CAMPUSNET_PASSWORD='your-password'
export CAMPUSNET_PROVIDER=drcom
```

配置示例：

```json
{
  "username": "2024123456",
  "provider": "auto",
  "portal_ip": "",
  "wifi_ssid": "JOU",
  "verify_url": "http://connect.rom.miui.com/generate_204",
  "timeout": 8,
  "options": {
    "ac_id": "1",
    "carrier": "校园用户"
  }
}
```

**密码存放优先级**：环境变量 → 系统钥匙串（装了 `keyring` 时）→ 配置文件 → 交互式输入。

`campusnet setup --save-password` 才会把密码写进配置文件（会明确警告）。不想落盘就别加这个参数，
配合 `keyring` 或环境变量用。

## 开机自启

```bash
campusnet autostart install     # 安装
campusnet autostart status      # 查看当前用的是哪种方式
campusnet autostart uninstall   # 卸载
```

| 平台 | 方式 |
| --- | --- |
| Windows | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 注册表项，走 `pythonw.exe` 无窗口启动 |
| macOS | `~/Library/LaunchAgents/com.campusnet.watch.plist` + `launchctl` |
| Linux | `~/.config/systemd/user/campusnet.service` + `systemctl --user`；没有 systemd 时退回 crontab `@reboot` |

> 想要 Windows 上用计划任务（支持"网络变化时触发"）？见 [docs/providers.md](docs/providers.md) 末尾的手动配置说明。
> 简单说：计划任务能做的触发，`watch` 模式用定时轮询都能覆盖，而轮询不需要管理员权限。

## 卸载

```bash
campusnet autostart uninstall
pip uninstall campusnet
rm -rf ~/.config/campusnet        # Windows: %APPDATA%\campusnet
```

## 常见问题

**Q：会不会因为反复失败把账号锁了？**
不会。每轮按 provider 依次尝试，命中即停；每次运行前先探测是否已联网，已联网直接退出。
`auto` 模式下同一次运行最多尝试 3 个 provider。

**Q：`campusnet detect` 认不出我们学校怎么办？**
把 detect 的输出（或页面 HTML 前几 KB）发到 issue 里，通常加上一条指纹规则就能支持。
临时方案是用 `custom` provider 自己填接口。

**Q：深澜的 `ac_id` 是多少？**
大多数学校是 `1`。不确定就先跑 `campusnet detect`，它会把从页面里抠出来的 `ac_id` 打印出来。

**Q：为什么零依赖？**
这类工具经常要在宿舍网络很差、甚至只有内网的环境里装。依赖越少，装上的概率越大。
所以只用标准库：HTTP 用 `urllib`，加密用 `hashlib` + 自己实现的 `srun_bx1` 编码，配置用 `json`。

**Q：为什么不模拟浏览器点按钮？**
能直连接口就绝不模拟浏览器。HTTP 直连快、稳、日志清晰、不需要下载 Chromium。
只有在极少数连接口都没有的私有 Portal 上，才需要用 `custom` 走 HTML 表单提交。

**Q：安全吗？**
- 所有请求只发往你学校的认证服务器，没有任何第三方中转
- 密码默认不落盘；落盘需显式开启
- 纯标准库，代码量小，可自行审阅

## 参与贡献

最需要的是**更多学校的指纹样本**。如果你的学校不在支持列表里：

1. 跑 `campusnet detect --verbose`
2. 截图或复制输出，开一个 issue，标题写 `[指纹] 学校名 · 认证系统`
3. 如果你知道接口细节，直接提 PR 加一个 provider

新增 provider 的步骤见 [docs/providers.md](docs/providers.md)。

## English

`campusnet` is a zero-dependency CLI that auto-logs-in to the campus network captive portal
(Dr.COM / Srun / Ruijie / Huawei eportal). It fingerprints the portal automatically, keeps
you online with a background watchdog, and installs itself as a startup item on
Windows / macOS / Linux.

```bash
campusnet setup && campusnet login && campusnet autostart install
```

## License

[MIT](LICENSE)
