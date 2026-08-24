# Nonlinear Studio 部署说明（feizhang233.com 子站）

## 访问地址

| 站点 | URL | 说明 |
| --- | --- | --- |
| DocFlow（主站） | https://feizhang233.com | 不受 Nonlinear 影响 |
| Nonlinear Studio | https://nonlinear.feizhang233.com | 独立子域名 |

## 架构

```text
浏览器
  -> Cloudflare DNS/CDN
  -> 专用 tunnel "nonlinear" (a347daa4-...) 
  -> 127.0.0.1:8007  FastAPI + 静态 workbench (docker: nonlinear-studio)
       |-- /api/*  /health  /docs
       |-- /*      frontend/dist
       +-- SQLite  /data (volume: nonlinear_data)
```

主站 DocFlow 仍使用既有 tunnel `sillytavern` → `127.0.0.1:8000`。
Frame Studio 仍走 sillytavern → `127.0.0.1:8002`。

## 本机路径

- 代码：`/home/fei/Solver/2D-nonlinear-project`
- Tunnel 配置：`/home/fei/.cloudflared/config-nonlinear.yml`
- Tunnel 凭据：`/home/fei/.cloudflared/a347daa4-2658-4aca-91e8-d0a19fa23711.json`

## 进程

线性核（CI 冻结版本）需先拉到 `dependencies/`：

```bash
cd /home/fei/Solver/2D-nonlinear-project
bash scripts/fetch-linear-cores.sh
```

```bash
# API + workbench
cd /home/fei/Solver/2D-nonlinear-project && docker compose up -d --build

# Dedicated tunnel
cd /home/fei/Solver/2D-nonlinear-project
pm2 start ecosystem.config.cjs
# 或：
pm2 restart nonlinear-tunnel
pm2 save
```

## 更新前端

```bash
cd /home/fei/Solver/2D-nonlinear-project/frontend
npm ci
NODE_OPTIONS='--max-old-space-size=768' npm run build
cd /home/fei/Solver/2D-nonlinear-project
docker compose up -d --build
```

## 健康检查

```bash
curl -sS http://127.0.0.1:8007/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8007/
curl -sS https://nonlinear.feizhang233.com/health
curl -sS -o /dev/null -w '%{http_code}\n' https://nonlinear.feizhang233.com/
```
