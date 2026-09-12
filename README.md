# campusnet · 校园网自动登录

> 一条命令搞定校园网 Portal 认证。开机自动登录，断网自动重连。

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#为什么零依赖)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)

零依赖 · 跨平台 · 自动识别认证系统 · 支持 Dr.COM / 深澜 / 锐捷 / 华为 eportal

**已在江苏海洋大学实测通过。** 欢迎其它学校的同学跑 `campusnet detect` 反馈指纹，一起把覆盖面做广。

```console
$ campusnet status
✔ 网络：已联网
• 认证系统：drcom 1.00  Dr.COM 城市热点
• 本机 IP：10.190.51.27
```

## 特性

- **自动识别认证系统** —— 探测门户页面做指纹识别，不用你告诉它学校用的哪家
- **零第三方依赖** —— 只用 Python 标准库，宿舍内网也装得上
- **开机自启** —— Windows 注册表 / macOS LaunchAgent / Linux systemd，无需管理员权限
- **守护模式** —— 定时检查，夜间断网、早上恢复后自动重新认证
- **不打扰** —— 已联网时直接退出，不发多余请求
- **凭据安全** —— 优先环境变量 / 系统钥匙串，明文落盘需显式同意

## 安装

```bash
pip install git+https://github.com/<you>/campusnet.git
```

或克隆后直接用，无需安装：

```bash
git clone https://github.com/<you>/campusnet.git
cd campusnet && python -m campusnet status
```

要求 Python 3.8+，无第三方依赖。

## 快速开始

```bash
campusnet setup               # 1. 生成配置（交互式，自动探测认证方式）
campusnet login               # 2. 登录一次试试
campusnet autostart install   # 3. 装成开机自启
```

## 命令

| 命令 | 作用 |
| --- | --- |
| `setup` | 交互式生成配置 |
| `detect` | 探测门户并做指纹识别 |
| `login` | 登录一次（已联网则跳过，`--force` 强制重登） |
| `watch` | 常驻守护，定时检查并自动补登录 |
| `status` | 查看联网状态与本机信息 |
| `providers` | 列出支持的认证系统 |
| `autostart install\|uninstall\|status` | 管理开机自启 |

常用参数：`--config` 指定配置 · `--provider` 强制认证方式 · `--portal` 指定门户 ·
`--interval` 守护间隔 · `--verbose` 打印请求细节

## 支持的认证系统

| Provider | 认证系统 | 状态 |
| --- | --- | --- |
| `drcom` | Dr.COM 城市热点 | ✅ **江苏海洋大学**实测 |
| `srun` | 深澜 Srun | 已实现，待验证 |
| `ruijie` | 锐捷 Ruijie | 已实现，待验证 |
| `eportal` | 华为 / 通用 eportal | 已实现，待验证 |
| `custom` | 自定义模板 | ✅ |
| `auto` | 自动探测（默认） | ✅ |

没在上面？跑 `campusnet detect` 把指纹发到 issue，或用 `custom` 自己填接口。
协议细节和开发指引见 [docs/providers.md](docs/providers.md)。

## 配置

| 平台 | 路径 |
| --- | --- |
| Windows | `%APPDATA%\campusnet\config.json` |
| macOS / Linux | `~/.config/campusnet/config.json` |

也可以用环境变量，适合不落盘：

```bash
export CAMPUSNET_USERNAME=你的学号
export CAMPUSNET_PASSWORD=你的密码
```

密码存放优先级：环境变量 → 系统钥匙串（装了 `keyring`）→ 配置文件 → 交互输入。
只有加 `--save-password` 才会明文写进配置文件。

## 常见问题

**会不会反复失败把账号锁了？**
不会。命中即停，每次先探测是否已联网，已联网直接退出；`auto` 模式单次最多试 3 个 provider。

**认不出我们学校怎么办？**
跑 `detect`，把输出（**记得给账号、IP、MAC 打码**）发到 issue，通常加一条指纹规则就能支持。

**为什么零依赖、不模拟浏览器？**
能直连接口就绝不模拟浏览器——快、稳、日志清晰、不用下载 Chromium。标准库够用，就不引第三方包。

**安全吗？**
请求只发往你学校的认证服务器，无第三方中转；密码默认不落盘；代码量小，可自行审阅。

## 参与贡献

最缺的是**更多学校的指纹样本**。跑 `campusnet detect --verbose` → 开 issue（标题 `[指纹] 学校名 · 认证系统`），
或直接提 PR 加一个 provider。

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。发布说明见 [docs/releases/](docs/releases/)，
上手发布流程见 [docs/PUBLISHING.md](docs/PUBLISHING.md)。

## License

[MIT](LICENSE)
