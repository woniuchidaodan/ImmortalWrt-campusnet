# 更新日志

本文件记录所有值得注意的改动。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- 收集更多学校的门户指纹，把 `srun` / `ruijie` / `eportal` 从"已实现"推进到"已实测"
- Docker 镜像（给路由器 / 树莓派用户）
- 登录失败时的自动重试退避策略

## [0.1.0] - 2026-09-13

首个公开版本。

### 新增

- **多厂商认证支持**：`drcom`（城市热点）、`srun`（深澜）、`ruijie`（锐捷）、
  `eportal`（华为 / 通用 ACSetting）、`custom`（自定义模板）
- **门户自动指纹识别**：探测门户页面并按置信度排序 provider，`auto` 模式自动选择
- **双重联网判定**：`generate_204` 劫持探测 + 真实网页内容校验，避免被白名单误判为已联网
- **CLI**：`setup` / `detect` / `login` / `watch` / `status` / `providers` / `autostart`
- **开机自启**：Windows 注册表 `Run` 项、macOS LaunchAgent、Linux systemd 用户服务
  （无 systemd 时退回 crontab `@reboot`）
- **守护模式**：常驻轮询，联网正常时完全不产生日志
- **凭据管理**：环境变量 / `keyring` / 配置文件 / 交互输入四级优先级，默认不落盘

### 修复

- **在默认编码非 UTF-8 的控制台上会崩溃**（英文版 Windows、CI runner）。
  输出里的中文和 `─` `✔` 这类字符编不出来时会抛 `UnicodeEncodeError`，
  导致 `campusnet providers` / `status` 等命令直接以退出码 1 结束。
  现在：需要时自动切到 UTF-8，切不了就降级成 ASCII 字符，绝不崩。
- CI 增加 `PYTHONIOENCODING=cp1252` 的冒烟步骤，在三个平台上锁定这个回归
- `campusnet status` 不再因为"未联网"返回非零退出码（报告状态不是错误）；
  需要脚本判断的用新增的 `status --check`

### 实测

- 在 **江苏海洋大学** 真实门户上验证通过：自动识别出 `Server: DrcomServer1.0`，
  `drcom` 置信度 1.00，正确提取本机 IP 与门户地址

### 说明

- `srun` / `ruijie` / `eportal` 三个 provider 目前只有单元测试覆盖
  （请求参数拼装与响应解析），**尚未在真实服务器上验证**，欢迎反馈
- Python 3.8+，无第三方依赖

[Unreleased]: https://github.com/demo133/campusnet/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/demo133/campusnet/releases/tag/v0.1.0
