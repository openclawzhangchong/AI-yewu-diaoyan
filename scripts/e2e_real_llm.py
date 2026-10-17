"""真 LLM 端到端冒烟脚本（需 API Key，联网）。

跑法（在仓库根目录）:
    uv run python scripts/e2e_real_llm.py

Key 来源（三选一，优先级同配置链）:
    1. 环境变量 LLM_API_KEY / LLM_PROVIDER / LLM_BASE_URL / LLM_MODEL_NAME
    2. 仓库根 config.local.yaml（已 gitignore，本地常用）
    3. config.yaml

验证点:
    - 三种输入格式（md/txt/json fixture）全部解析成功
    - 三种输出格式（markdown/json/excel）全部生成文件
    - 报告 generated_at 不再是「未指定」
    - 机会点数量 > 0
退出码 0 = 全过，1 = 有失败。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CASES = [
    ("tests/fixtures/survey_kefu.md", "markdown"),
    ("tests/fixtures/survey_caiwu.txt", "json"),
    ("tests/fixtures/survey_cangchu.json", "excel"),
]


def main() -> int:
    if not os.environ.get("LLM_API_KEY") and not (ROOT / "config.local.yaml").exists() \
            and not (ROOT / "config.yaml").exists():
        print("未找到 LLM_API_KEY（环境变量）且仓库根没有 config.local.yaml / config.yaml")
        return 1

    outdir = Path(tempfile.mkdtemp(prefix="e2e_real_llm_"))
    failures: list[str] = []

    for rel_input, fmt in CASES:
        src = ROOT / rel_input
        out_file = outdir / f"report_{src.stem}.{ 'md' if fmt == 'markdown' else fmt}"
        cmd = [
            sys.executable, "main.py", "--cli", "analyze",
            "--input", str(src),
            "--output-dir", str(outdir),
            "--output-format", fmt,
        ]
        print(f"=== {src.name} -> {fmt} ===")
        r = subprocess.run(
            cmd, cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600,
        )
        if r.returncode != 0:
            tail = (r.stdout or r.stderr).strip().splitlines()[-3:]
            failures.append(f"{src.name}: exit={r.returncode} {' | '.join(tail)}")
            continue

        # 找本次生成的报告文件（时间戳命名）
        ext = {"markdown": "md", "json": "json", "excel": "xlsx"}[fmt]
        produced = sorted(outdir.glob(f"report_*{src.stem}*.{ext}")) or sorted(outdir.glob(f"*.{ext}"))
        if not produced:
            failures.append(f"{src.name}: 未生成 .{ext} 文件")
            continue

        content = produced[-1].read_text(encoding="utf-8", errors="replace")
        if fmt == "json":
            data = json.loads(content)
            if data.get("report_metadata", {}).get("generated_at") in (None, "", "未指定"):
                failures.append(f"{src.name}: json generated_at 缺失")
            elif not data.get("departments"):
                failures.append(f"{src.name}: json departments 为空")
        else:
            if "未指定" in content:
                failures.append(f"{src.name}: 报告 generated_at 显示「未指定」")
        print(f"  OK: {produced[-1].name}")

    if failures:
        print("\n失败:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\n全部通过（{len(CASES)}/{len(CASES)}），报告在 {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
