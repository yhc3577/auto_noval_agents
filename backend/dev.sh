#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 自动切换到 conda local 环境 ──────────────────────
if [ -z "${CONDA_DEFAULT_ENV:-}" ] || [ "${CONDA_DEFAULT_ENV:-}" = "base" ]; then
    if command -v conda &>/dev/null && conda env list 2>/dev/null | grep -q "^local "; then
        exec conda run -n local bash "$0" "$@"
    fi
fi

PORT="${SERVER_PORT:-8080}"

# ── 颜色 ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

ok "Python: $(python --version 2>&1) @ ${CONDA_DEFAULT_ENV:-venv}"

# ── .env ───────────────────────────────────────────────
setup_env() {
    [ -f .env ] && return
    [ -f .env.example ] && cp .env.example .env && warn ".env 已从 .env.example 复制" && return
    err ".env 不存在"; exit 1
}

# ── 服务检查 ──────────────────────────────────────────
check_port() {
    local name="$1" host="$2" port="$3"
    if timeout 1 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
        ok "$name ($host:$port)"
    else
        warn "$name 不可达 ($host:$port)"
    fi
}

check_services() {
    info "检查依赖服务..."
    check_port "MongoDB" "localhost" "27017"
    check_port "Redis"   "localhost" "6379"
    [ -f .env ] && check_port "vLLM" "localhost" "$(grep -oP 'LLM_BASE_URL=http://localhost:\K\d+' .env 2>/dev/null || echo 8000)"
}

# ── 语法检查 ──────────────────────────────────────────
check_syntax() {
    info "语法检查..."
    python -c "
import ast, os, sys
errors = total = 0
for r, _, fs in os.walk('src'):
    for f in fs:
        if f.endswith('.py'):
            total += 1
            p = os.path.join(r, f)
            try:
                with open(p) as fh: ast.parse(fh.read())
            except SyntaxError as e:
                print(f'  ERROR {p}: {e}'); errors += 1
if errors: print(f'{errors}/{total} syntax errors'); sys.exit(1)
print(f'Syntax OK ({total} files)')
"
}

# ── 模块检查 ──────────────────────────────────────────
check_imports() {
    info "LangGraph 图编译..."
    python -c "
import sys; sys.path.insert(0, '.')
from src.core.state import NovelState
from src.agents.pipeline import compile_chapter_graph
g = compile_chapter_graph()
nodes = [n for n in g.get_graph().nodes if n not in ('__start__', '__end__')]
print(f'  State: {len(NovelState.__annotations__)} fields')
print(f'  Nodes: {nodes}')
print('  OK')
"
    ok "图编译成功"
}

# ── 启动 ──────────────────────────────────────────────
start_server() {
    info "启动 FastAPI (port $PORT)..."
    echo ""
    echo -e "${CYAN}┌────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│${NC}  API 文档:  ${GREEN}http://localhost:$PORT/docs${NC}   ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC}  前端代理:  ${GREEN}http://localhost:5173${NC}       ${CYAN}│${NC}"
    echo -e "${CYAN}└────────────────────────────────────────┘${NC}"
    echo ""
    exec python -m uvicorn src.main:app \
        --host 0.0.0.0 --port "$PORT" \
        --reload --reload-dir src --log-level info
}

# ── 入口 ──────────────────────────────────────────────
case "${1:-}" in
    --check|-c)   setup_env; check_services; check_syntax; check_imports ;;
    --syntax|-s)  check_syntax ;;
    --graph|-g)   check_imports ;;
    --install)    pip install -r requirements.txt ;;
    --help|-h)
        echo "用法: ./dev.sh [选项]"
        echo "  (无参数)        完整启动"
        echo "  --check, -c     检查环境+服务+语法+图编译"
        echo "  --syntax, -s    Python 语法检查"
        echo "  --graph, -g     LangGraph 图编译验证"
        echo "  --install       安装依赖"
        ;;
    *)            setup_env; check_services; check_syntax; check_imports; start_server ;;
esac
