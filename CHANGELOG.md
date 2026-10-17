# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.9.0] - 2026-10-17

### Added
- `config.local.yaml` 本地密钥支持：与 `config.yaml` 同目录同结构，只写需要覆盖的字段，已被 `.gitignore` 忽略（新增 3 个单测覆盖优先级）
- 配置优先级链更新为：命令行 > 环境变量 > `config.local.yaml` > `config.yaml` > 内置默认
- 真实 LLM 端到端验证：agnes-3.0-flash（OpenAI 兼容，`LLM_BASE_URL=https://api.agnes-ai.cn/v1`）markdown / json / excel 三种输出格式全部实测通过
- README 与开发手册（§七配置说明、§十九 API Key 指引、§二十五 Agent 约定）同步为新配置语义与环境变量名

### Fixed
- 报告 `generated_at` 缺失（Markdown 渲染出"未指定"）：CLI/GUI 构造 `FullAnalysisReport` 时补 `generated_at`
- 清理 cli.py 中 `__import__("datetime")` 内联写法，改为顶部标准 import
- Windows GBK 控制台崩溃：进度条 `█`/`░` 与 `✓` 等字符在输出重定向/GBK 控制台下触发 `UnicodeEncodeError`，改为 ASCII `#`/`-`/`√`；`main.py` 入口对 stdout/stderr 做 UTF-8 reconfigure 双保险

---

## [v0.8.0] - 2026-10-17

### Added
- PyInstaller 端到端打包验证通过：`--onefile --add-data "templates;templates" --add-data "config.yaml;." main.py`，窗口版（双击 GUI）与控制台版均实测
- 开发手册「PyInstaller打包命令」章节更新为实测命令与要点（Windows 分号分隔符、_MEIPASS 回退说明）

### Fixed
- GUI 缺 API Key 时启动即崩溃（create_llm_client 抛 LLMError）：改为启动时不阻塞，提交分析时再校验并弹窗提示
- CLI `analyze` 缺 Key 时在 try 块外抛 LLMError 导致裸 traceback：改为在 analyze 命令内捕获，输出友好错误并退出码 1

---

## [v0.7.0] - 2026-10-16

### Added
- 完整测试套件（tests/）：unit（域模型 / infra / core / output）+ integration（CLI + E2E），143 个用例全离线可跑
- pytest 配置（`[tool.pytest.ini_options]`，asyncio_mode=auto）与 hatchling 打包声明
- `--cli pack-skill --mode light|full` 命令：CLI 一键打包 Skill
- `docs/开发手册.md` 入仓；新增「日志与 AI Agent 操作指引」「AI Agent 接入与调试指南」「仓库维护规范」章节

### Fixed
- `AnalysisResult.process` 必填导致 `_parse_llm_response` 构造失败（TypeError）：加默认值 `""`
- `ConfigManager` 先 `set_from_args` 后 `load()` 时 CLI 参数被 yaml/env 覆盖：load 末尾 re-apply，保证「命令行 > 环境变量 > yaml」
- CLI `analyze` 把单部门 `AnalysisResult` 直接传给只接受 `FullAnalysisReport` 的报告生成器：包装为完整报告
- GUI 同样的 FullAnalysisReport 包装问题
- `TemplateManager`/`ReportGenerator` 模板目录定位：CWD → PyInstaller `_MEIPASS` → 源码相对位置回退（保证 exe 双击可用）

---

## [v0.6.0] - 2026-10-16

### Added
- output 输出层：ReportBuilder（md/xlsx/json 报告构建 + 事件发布）、SkillPackager（light/full 双模式 Skill 打包）
- 5 个部门业务调研模板（运营/客服/设计/仓储/财务）+ Jinja2 报告模板
- 修复 .gitignore 过度忽略（`*.json`/`output/` 曾导致源码与模板不被 git 跟踪）

## [v0.5.0] - 2026-10-16

### Added
- entry 入口层：Tkinter GUI（选文件 → 提交 → 等报告）+ click/rich CLI（analyze/collect/departments/quick-start）
- 主入口 `python main.py`（默认 GUI，`--cli` 透传子命令）

## [v0.4.0] - 2026-10-16

### Added
- core 核心层：TemplateManager（自动扫描 templates/）、DataCollector（md/txt/docx/json 解析 + 验证）、AIAnalysisEngine（异步并发 + Semaphore 限流 + 6 维度 Prompt）、ReportGenerator（Jinja2 md / xlsx / json）

## [v0.3.0] - 2026-10-16

### Added
- infra 基础设施层：异常层次（AppError + 7 子类固定 code）、事件总线（sync/async handler）、JSON 结构化日志（轮转）、SQLite 缓存、ConfigManager（命令行 > 环境变量 > config.yaml > 默认）、LLMClient（OpenAI/Qwen/Zhipu 策略模式 + 指数退避重试）

## [v0.2.0] - 2026-10-16

### Added
- domain 数据模型层：调研模板（Question/BusinessTemplate）、分析结果（OpportunityPoint/AnalysisResult/FullAnalysisReport）、配置（ModelConfig/Config）

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
