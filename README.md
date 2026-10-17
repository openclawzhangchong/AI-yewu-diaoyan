# AI业务调研提效分析系统

通过结构化调研收集各部门业务场景信息，利用AI大模型分析识别各业务环节中可引入AI提效的具体环节，输出可执行的AI提效建议报告。

双定位：**独立程序**（GUI/CLI 直接出报告）+ **Skill 包**（可打包分发到其他 Agent 平台如 ZCode 复用）。

## 快速开始

### 1. 安装依赖
```bash
uv sync
```

### 2. 配置API Key（三选一）
```bash
# 方式1：环境变量（推荐，Windows 下用 set）
set LLM_API_KEY=sk-xxx
set LLM_PROVIDER=openai
set LLM_BASE_URL=https://api.agnes-ai.cn/v1
set LLM_MODEL_NAME=agnes-3.0-flash
```
```yaml
# 方式2：config.local.yaml（本地密钥，已被 .gitignore 忽略，不会进版本库；
# 字段与 config.yaml 相同，只写需要覆盖的部分即可）
model:
  provider: "openai"
  api_key: "sk-xxx"
  base_url: "https://api.agnes-ai.cn/v1"
  model_name: "agnes-3.0-flash"
```
```
# 方式3：交互式引导
python main.py --cli quick-start
```
> 配置优先级：命令行参数 > 环境变量 > config.local.yaml > config.yaml > 内置默认。

### 3. 准备调研总结
把各部门的调研内容写成 Markdown / TXT / Word / JSON 文件即可（无需特殊格式，自然语言描述当前流程、耗时、痛点）：
```markdown
# 运营部
## 用户增长
当前流程：人工分析渠道数据，手动制定投放策略
耗时：每天约2小时
痛点：数据量大，人工统计慢
```

### 4. 运行程序
```bash
# GUI 模式（推荐，傻瓜式：选文件 → 提交 → 等报告）
python main.py

# CLI 模式
python main.py --cli departments                      # 查看 5 个部门模板（无需 Key，冒烟测试）
python main.py --cli analyze --input ./调研总结.md    # 分析并出报告
python main.py --cli collect                          # 交互式采集
```

### 5. 查看报告
报告默认保存在 `./output/` 目录（格式可在 CLI `--output-format markdown|excel|json` 或 GUI 里选择）。

## 支持的输入格式
- Markdown (.md)
- 纯文本 (.txt)
- Word文档 (.docx)
- JSON (.json)

## 支持的输出格式
- Markdown (.md)
- Excel (.xlsx)
- JSON (.json)

## 技术栈
- Python 3.10+
- uv（包管理）
- rich + click（CLI）
- Tkinter（GUI）
- Jinja2（报告模板）
- openpyxl（Excel）
- python-docx（Word）
- pyyaml（配置）
- SQLite（缓存）
- python-json-logger（日志）

## 打包成exe（Windows 安装包）
```bash
pip install pyinstaller
pyinstaller --onefile --name "AI业务调研提效分析系统" --windowed \
  --add-data "templates;templates" --add-data "config.yaml;." main.py
# 产物在 dist/，双击 exe 即用，无需 Python 环境
```

## 打包成Skill
```bash
python main.py --cli pack-skill --mode light --output ./ai-efficiency-skill
# light: SKILL.md + manifest.json + prompts + 部门模板
# full:  再加 Python 代码与依赖清单（requirements.txt）
```

## 日志配置

程序使用结构化JSON日志，便于AI Agent和自动化系统读取。

- **日志位置**：`./logs/app.log`
- **日志格式**：JSON（每行一个对象：timestamp / level / module / message）
- **日志级别**：DEBUG / INFO / WARNING / ERROR
- **日志轮转**：10MB / 5个备份

### 日志示例
```json
{"timestamp": "2026-10-16T10:00:00", "level": "INFO", "module": "core.ai_engine", "message": "部门 运营部 分析完成, 发现 3 个机会点"}
```

### AI Agent 操作指南
1. 通过读取 `./logs/app.log` 监控程序运行状态（`tail -n 100 ./logs/app.log`，可配合 jq 过滤）
2. 通过读取 `./output/` 目录获取生成的报告
3. 通过修改 `config.yaml` 调整模型配置
4. 通过设置环境变量 `LLM_API_KEY`（或 `LLM_PROVIDER` / `LLM_MODEL_NAME` / `LLM_BASE_URL`）配置密钥与模型
5. 使用 `python main.py --cli --help` 查看所有命令（analyze / collect / departments / pack-skill / quick-start）
6. 详细 Agent 调试 SOP 见 `docs/开发手册.md` 第二十六、二十七章

## 测试
```bash
uv run pytest -q   # 143 个用例，全离线可跑（LLM 用桩替换，无需 API Key）
```

## 许可证
MIT License
