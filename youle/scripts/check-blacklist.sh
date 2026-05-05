#!/usr/bin/env bash
# 代码模式黑名单 grep(对齐 CLAUDE.md §3)。本地或 pre-commit 跑。
set -euo pipefail
cd "$(dirname "$0")/.."

violations=0

check() {
  local pattern="$1"
  local desc="$2"
  if grep -rn -E --include="*.py" "$pattern" backend/app agents mcp_servers flywheel 2>/dev/null; then
    echo "✗ violation: $desc"
    violations=$((violations + 1))
  fi
}

check 'import openai' '禁止直接 import openai(铁律 7,走 app.router)'
check 'import anthropic' '禁止直接 import anthropic'
check 'from openai import' '同上'
check 'OpenAI\(' '同上'
check 'call_other_agent\(' 'ADR-002:Agent 不能跨调'
check 'except:\s*$' '禁止 except: pass(铁律 12)'
check 'except Exception:\s*$' '同上'
check '\bprint\(' '禁止 print(铁律 12,改 structlog)' || true  # 警告而非阻断

if [ $violations -gt 0 ]; then
  echo ""
  echo "存在 $violations 处违规,见 CLAUDE.md §3。"
  exit 1
fi
echo "✓ 代码模式黑名单全部通过"
