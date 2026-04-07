# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}

RUN npm run build

# ── Serve stage ──────────────────────────────────────────────────────────────
FROM nginx:alpine

# Public entry point:
#   /api/*    → reverse-proxied to backend:8000 (internal Docker network)
#   /health   → reverse-proxied to backend:8000
#   /assets/* → static files (immutable cache)
#   /*        → React SPA (index.html fallback)
#
# The backend container has no public ports — all traffic goes through here.
RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    # Reverse proxy — backend API (internal Docker network only)\n\
    location /api/ {\n\
        proxy_pass http://backend:8000;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto $scheme;\n\
        # SSE / streaming support\n\
        proxy_set_header Connection "";\n\
        proxy_buffering off;\n\
        proxy_cache off;\n\
        proxy_read_timeout 120s;\n\
    }\n\
\n\
    # Health check endpoint (proxied so load balancers can probe via :80)\n\
    location /health {\n\
        proxy_pass http://backend:8000/health;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Host $host;\n\
    }\n\
\n\
    # Static assets — immutable cache\n\
    location /assets/ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
\n\
    # React SPA — all other routes serve index.html\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
        add_header Cache-Control "no-cache, no-store, must-revalidate";\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
