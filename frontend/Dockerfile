# ── Stage 1: 构建 Vue 应用 ─────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ── Stage 2: Nginx 静态服务 ─────────────────────────────────
FROM nginx:alpine

# 拷贝构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx 配置：API 反向代理 + SPA 路由
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    \
    # API 反向代理到 backend \
    location /api/ { \
        proxy_pass http://backend:8080; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
        proxy_read_timeout 300s; \
    } \
    \
    # SPA fallback \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    \
    # 静态资源缓存 \
    location /assets/ { \
        expires 1y; \
        add_header Cache-Control "public, immutable"; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
