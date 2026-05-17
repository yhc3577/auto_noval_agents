#!/usr/bin/env bash
# ── 本地构建镜像 + 导出 tar ────────────────────────────
# 用法:
#   ./scripts/docker-build.sh          # 构建所有镜像
#   ./scripts/docker-build.sh --push   # 构建并推送到 registry
set -euo pipefail

cd "$(dirname "$0")/.."

REGISTRY="${DOCKER_REGISTRY:-}"        # 例如: registry.example.com/novel  或 docker.io/yourname
TAG="${IMAGE_TAG:-latest}"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC} $*"; }

# ── 构建 ─────────────────────────────────────────────
info "构建 backend 镜像..."
docker build -t novel-backend:${TAG} -f backend/Dockerfile backend/

info "构建 frontend 镜像..."
docker build -t novel-frontend:${TAG} -f frontend/Dockerfile frontend/

echo ""
if [ -n "$REGISTRY" ]; then
    info "打 tag 并推送..."
    docker tag novel-backend:${TAG}  ${REGISTRY}/novel-backend:${TAG}
    docker tag novel-frontend:${TAG} ${REGISTRY}/novel-frontend:${TAG}
    docker push ${REGISTRY}/novel-backend:${TAG}
    docker push ${REGISTRY}/novel-frontend:${TAG}
    echo ""
    info "推送完成，服务器端执行:"
    echo "  IMAGE_TAG=${TAG} DOCKER_REGISTRY=${REGISTRY} docker compose pull"
    echo "  IMAGE_TAG=${TAG} DOCKER_REGISTRY=${REGISTRY} docker compose up -d"
else
    info "导出为 tar 文件..."
    docker save -o novel-images-${TAG}.tar novel-backend:${TAG} novel-frontend:${TAG}
    ls -lh novel-images-${TAG}.tar
    echo ""
    echo -e "${GREEN}构建完成！${NC} 部署到服务器:"
    echo ""
    echo "  # 1. 上传文件"
    echo "  scp novel-images-${TAG}.tar docker-compose.yml .env user@server:/opt/novel/"
    echo ""
    echo "  # 2. 服务器上加载镜像"
    echo "  ssh user@server"
    echo "  cd /opt/novel && docker load -i novel-images-${TAG}.tar"
    echo ""
    echo "  # 3. 启动"
    echo "  IMAGE_TAG=${TAG} docker compose up -d"
fi
