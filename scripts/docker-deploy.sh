#!/usr/bin/env bash
# ── 一键部署到远端服务器 ──────────────────────────────
# 用法:
#   ./scripts/docker-deploy.sh user@192.168.1.100:/opt/novel
#   ./scripts/docker-deploy.sh user@192.168.1.100:/opt/novel --restart   # 重启服务
set -euo pipefail

TARGET="${1:-}"
ACTION="${2:-}"

if [ -z "$TARGET" ]; then
    echo "用法: $0 user@host:/path/to/novel [--restart]"
    echo "示例: $0 root@10.0.0.5:/opt/novel"
    exit 1
fi

cd "$(dirname "$0")/.."

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }

# ── Step 1: 本地构建镜像 ────────────────────────────
info "Step 1/4: 构建镜像..."
bash scripts/docker-build.sh

# ── Step 2: 上传到服务器 ────────────────────────────
TAG="${IMAGE_TAG:-latest}"
info "Step 2/4: 上传到 $TARGET"

# 确保远端目录存在
ssh "${TARGET%%:*}" "mkdir -p ${TARGET##*:}"

# 上传镜像 tar
scp "novel-images-${TAG}.tar" "${TARGET}/"

# 上传 compose 和配置
SCRIPT_DIR="$(dirname "$0")"
scp "${SCRIPT_DIR}/docker-compose.yml" "${TARGET}/"
scp "${SCRIPT_DIR}/.env" "${TARGET}/"

# ── Step 3: 服务器上加载镜像 ────────────────────────
info "Step 3/4: 远端加载镜像..."
ssh "${TARGET%%:*}" bash -s << REMOTE_SCRIPT
set -euo pipefail
cd "${TARGET##*:}"

echo "加载镜像..."
docker load -i novel-images-${TAG}.tar

echo "清理 tar 文件..."
rm -f novel-images-${TAG}.tar
REMOTE_SCRIPT

# ── Step 4: 启动服务 ────────────────────────────────
if [ "$ACTION" = "--restart" ]; then
    info "Step 4/4: 重启服务..."
    ssh "${TARGET%%:*}" "cd ${TARGET##*:} && IMAGE_TAG=${TAG} docker compose up -d --force-recreate"
else
    info "Step 4/4: 启动服务..."
    ssh "${TARGET%%:*}" "cd ${TARGET##*:} && IMAGE_TAG=${TAG} docker compose up -d"
fi

ok "部署完成！"
echo "  前端: http://${TARGET%%:*}"
echo "  API:  http://${TARGET%%:*}:8080/docs"
