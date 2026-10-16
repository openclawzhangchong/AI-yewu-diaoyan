# AI业务调研提效分析系统

通过结构化调研收集各部门业务场景信息，利用AI大模型分析识别各业务环节中可引入AI提效的具体环节，输出可执行的AI提效建议报告。

## 快速开始

### 1. 安装依赖
```bash
uv sync
```

### 2. 配置API Key
```bash
# 方式1：环境变量（推荐）
export QWEN_API_KEY="sk-xxx"

# 方式2：config.yaml
# 编辑 config.yaml，填入你的API Key
```

### 3. 准备调研总结
创建一个Markdown/TXT文件，格式如下：
```markdown
# 运营部
## 用户增长
当前流程：人工分析渠道数据，手动制定投放策略
耗时：每天约2小时
痛点：数据量大，人工统计慢
```

### 4. 运行程序
```bash
# GUI模式（推荐）
python entry/gui.py

# CLI模式
python main.py analyze --input ./调研总结.md
```

### 5. 查看报告
生成的报告保存在 `./output/` 目录。

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

## 打包成exe
```bash
pyinstaller --onefile --name "AI业务调研提效分析系统" --windowed entry/gui.py
```

## 打包成Skill
```bash
python main.py pack-skill --mode light --output ./ai-efficiency-skill
```

## 日志配置

程序使用结构化JSON日志，便于AI Agent和自动化系统读取。

- **日志位置**：`./logs/app.log`
- **日志格式**：JSON
- **日志级别**：DEBUG / INFO / WARNING / ERROR
- **日志轮转**：10MB / 5个备份

### 日志示例
```json
{"timestamp": "2026-10-16T10:00:00", "level": "INFO", "module": "ai_engine", "message": "分析开始", "department": "运营部"}
```

### AI Agent 操作指南
1. 通过读取 `./logs/app.log` 监控程序运行状态
2. 通过读取 `./output/` 目录获取生成的报告
3. 通过修改 `config.yaml` 调整模型配置
4. 通过设置环境变量 `QWEN_API_KEY` 配置API密钥
5. 使用 `python main.py --help` 查看所有命令

## 许可证
MIT License
