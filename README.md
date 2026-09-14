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
• 本机 IP：10.20.30.40
```

## 特性

- **自动识别认证系统** —— 探测门户页面做指纹识别，不用你告诉它学校用的哪家
- **换过 Wi-Fi 也能自己连回来** —— 手动切到手机热点后重启，会自动切回校园网
- **支持先选运营商** —— 登录前要挑「移动 / 电信 / 联通」的学校也能用
- **零第三方依赖** —— 只用 Python 标准库，宿舍内网也装得上
- **开机自启** —— Windows 注册表 / macOS LaunchAgent / Linux systemd，无需管理员权限
- **守护模式** —— 定时检查，夜间断网、早上恢复后自动重新认证
- **不打扰** —— 已联网时直接退出，不发多余请求
- **凭据安全** —— 优先环境变量 / 系统钥匙串，明文落盘需显式同意

## 安装

```bash
pip install git+https://github.com/demo133/campusnet.git
```

或克隆后直接用，无需安装：

```bash
git clone https://github.com/demo133/campusnet.git
cd campusnet && python -m campusnet status
```

要求 Python 3.8+，无第三方依赖。

## 快速开始

```bash
campusnet setup               # 1. 生成配置（交互式，自动探测认证方式）
campusnet login               # 2. 登录一次试试
campusnet autostart install   # 3. 装成开机自启
```

> **第 1 步里问的「校园 Wi-Fi 名称」一定要填。** 它修的是下面这个问题。

## 换过 Wi-Fi 之后开机连不回校园网？

这是校园网自动登录最常见的翻车点，因为它的成因有点反直觉：

1. 你把 Wi-Fi 从校园网手动换成手机热点（或者别人的热点）；
2. 关机再开机，系统发现热点也有「自动连接」，就先连上热点了；
3. 热点能上网 → 联网探测通过 → 自动登录逻辑认为「已联网，无需认证」，
   于是**根本不会去碰 Wi-Fi**。

结果就是一直挂在热点上，校园网永远连不上 —— 明明有网，却不是你要的那个网。

**关键在于判断依据**：不能问「有没有网」，而要问「连的是不是校园网」。
所以 `campusnet` 在联网探测**之前**会先确认 Wi-Fi：

```bash
campusnet wifi set JOU          # 记住校园网名称（填你自己的 SSID）
campusnet wifi autoconnect      # 关闭其它网络自动连接（治本）
campusnet wifi                  # 看当前 Wi-Fi 状态
```

三条命令各自的作用：

| 命令 | 作用 | 是否必须 |
| --- | --- | --- |
| `wifi set <名称>` | 记下校园网 SSID，之后登录前会检查 | **必须**，不填就没有切网功能 |
| `wifi autoconnect` | 把其它所有 Wi-Fi 改成「手动连接」，开机时系统就没得抢 | 强烈建议 |
| `wifi` | 诊断：当前连的哪个网、是否在目标上、保存了哪些网络 | 排查用 |

只做第一步也能修好：每次登录前如果发现连的不是校园网，会执行
`netsh wlan connect` 并等它真的连上（最多 30 秒）再走认证流程。
第二步是**治本** —— 让开机时压根不会去连别的网。

配置好之后的行为：

```console
$ campusnet login
! 当前 Wi-Fi 是「iPhone 热点」，需要切回校园网「JOU」…
✔ 已连接到 Wi-Fi「JOU」
✔ 认证成功，网络已连通
```

再也不用先手动切回校园网了。`watch` 守护模式每一轮也会做这个检查，
所以用着用着 Wi-Fi 被切走，下一个周期就会被拉回来。

> macOS 没有「关闭单个网络自动加入」的接口，`wifi autoconnect` 是空操作；
> 但 `wifi set` + 登录前自动切网在三个平台上都有效。

## 登录前要先选运营商？

**可以，加一条命令就行。**

有些学校的校园网登录页不只是填账号密码，还得先从「校园用户 / 中国移动 /
中国电信 / 中国联通」里面选一个 —— 不选就认证失败，或者选错了上不了外网。

`campusnet` 支持这个。设一次，之后 `login` / `watch` 都会自动带上：

```bash
campusnet carrier 移动        # 设成中国移动
campusnet carrier             # 看看现在设的是什么
campusnet login               # 正常登录
```

向导里也会问（`campusnet setup` 的第 4 步），
临时改一次可以用 `campusnet login --carrier 电信`。

各认证系统是怎么表达运营商的：

| 认证系统 | 实现方式 |
| --- | --- |
| Dr.COM 城市热点 | 用隐藏字段 `R1` / `R3` / `para`，部分学校再加账号后缀（`@cmcc`） |
| 深澜 Srun | 用 `domain` 参数（`domain=cmcc`），或账号后缀 |
| 锐捷 / eportal | 一般没有独立字段，运营商直接拼在账号后缀上 |

能填的值（中文、英文、大小写都认）：

| 你说 | 归一成 | Dr.COM 参数 | 账号后缀 |
| --- | --- | --- | --- |
| 校园用户 / 校园网 / 默认 | `campus` | `R1=0 R3=0 para=00` | — |
| 移动 / 中国移动 / CMCC | `cmcc` | `R1=0 R3=0 para=30` | `@cmcc` |
| 电信 / 中国电信 | `telecom` | `R1=0 R3=0 para=00` | `@telecom` |
| 联通 / 中国联通 | `unicom` | `R1=0 R3=0 para=00` | `@unicom` |
| 校园其他 / 其它 | `other` | `R1=0 R3=0 para=30` | — |
| 校园电信（Dr.COM 独立选项） | `campus_telecom` | **`R1=1`** R3=0 para=00 | — |
| 校园联通（Dr.COM 独立选项） | `campus_unicom` | R1=0 **`R3=1`** para=00 | — |

> ⚠️ **别把「校园电信」和「电信」搞混。** 这两个在 Dr.COM 上是**不同的服务类型**：
> 「校园电信」走 `R1=1`，「电信」只是给账号加个 `@telecom` 后缀。
> 填错了参数发出去就是认证失败，而且报错信息看不出来。学校页面上写的是哪个就填哪个。

**认不出的名字不会被拒**。如果你学校的运营商不在上面，直接填它的名字就行 ——
`campusnet` 会把它当账号后缀用（`campusnet carrier 某某宽带` → 账号变成
`学号@某某宽带`），这恰好是很多学校的做法。实在不对还能用逃生舱直接写死参数：

```bash
campusnet login --option r1=1 --option r3=0 --option para=00
```

> **不选运营商、也没设 `carrier` 会怎样？**
> 默认按「校园用户」走（`R1=0 R3=0 para=00`，不加后缀）。
> 如果你的学校本来就不需要选，这就是对的；需要选的话认证会失败，
> 设一下 `campusnet carrier` 即可。

## 命令

| 命令 | 作用 |
| --- | --- |
| `setup` | 交互式生成配置 |
| `detect` | 探测门户并做指纹识别 |
| `login` | 登录一次（已联网则跳过，`--force` 强制重登） |
| `watch` | 常驻守护，定时检查并自动补登录 |
| `wifi [status\|list\|connect\|autoconnect\|set\|restore]` | 查看/管理 Wi-Fi，解决换网后连不回校园网 |
| `carrier [值]` | 查看/设置运营商，登录前要选服务类型的学校用 |
| `status` | 查看联网状态与本机信息（加 `--check` 则未联网时返回非零，方便写进脚本） |
| `providers` | 列出支持的认证系统 |
| `autostart install\|uninstall\|status` | 管理开机自启 |

常用参数：`--config` 指定配置 · `--provider` 强制认证方式 · `--portal` 指定门户 ·
`--interval` 守护间隔 · `--wifi` 临时指定校园网 · `--carrier` 临时指定运营商 ·
`--option k=v` 直接写 provider 参数 · `--verbose` 打印请求细节

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

主要字段：

| 字段 | 说明 |
| --- | --- |
| `username` | 学号 / 上网账号 |
| `portal_ip` | 认证门户地址，探测到后会自动写入 |
| `wifi_ssid` | **校园 Wi-Fi 名称**，填了才会自动切网（见上文） |
| `provider` | 认证系统，默认 `auto` 自动识别 |
| `timeout` | 单次请求超时（秒） |
| `options.carrier` | 运营商，见[「登录前要先选运营商？」](#登录前要先选运营商) |
| `options.r1` / `r3` / `para` | Dr.COM 逃生舱：直接写死页面上的隐藏字段 |
| `options.username_suffix` | 强制指定账号后缀（如 `@cmcc`） |
| `options.domain` | Srun 的 `domain` 参数 |
| `options.wifi_timeout` | 登录前等 Wi-Fi 连上的最长秒数，默认 30 |

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

**开机后连到别的 Wi-Fi 就不回校园网了？**
填上 `wifi_ssid`（`campusnet wifi set 你的SSID`）。原因和原理见上文
[「换过 Wi-Fi 之后开机连不回校园网」](#换过-wi-fi-之后开机连不回校园网)。

**我们学校登录还要先选运营商，能用吗？**
能。`campusnet carrier 移动`（或 `电信` / `联通` / `校园用户`）设一次就行，
细节见[「登录前要先选运营商？」](#登录前要先选运营商)。

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
