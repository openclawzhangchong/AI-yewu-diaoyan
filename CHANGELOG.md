# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0] - 2026-10-16

### Added
- AI业务调研提效分析系统核心功能
- GUI图形界面（Tkinter）
- CLI命令行界面（rich + click）
- 支持输入：Markdown / TXT / Word / JSON
- 支持输出：Markdown / Excel / JSON
- 多部门AI分析引擎（异步并发）
- 模板自动发现机制
- SQLite缓存
- 结构化JSON日志
- PyInstaller Windows安装包打包
- Skill打包（轻量模式 + 完整模式）

### Changed
- 配置优先级：命令行 > 环境变量 > config.yaml > 内置默认值
- LLM客户端支持策略模式（OpenAI / Qwen / Zhipu）

### Fixed
- GUI Radiobutton 参数修复
- LLM并发控制（asyncio.Semaphore）

---

*本 CHANGELOG 遵循 Keep a Changelog 格式，每次 release 更新。*
