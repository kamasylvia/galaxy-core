# galaxy-web 部署指南(Docker / NixOS 原生)

> 两种方式二选一,行为一致(监听 0.0.0.0:8001,20 widgets + portfolio/dashboard)。
> 前置:PostgreSQL/TimescaleDB `galaxy` 库可达(K 线/报表/资金流);纯 AmazingData,无 akshare 依赖。

## 共同配置

```bash
cp openbb-app.env.example .env   # 填 APP_API_KEY + GALAXY_PG_* (见下)
```

| 变量 | 含义 | 默认 |
|---|---|---|
| `APP_API_KEY` | Workspace 后端鉴权 key(Bearer) | 必填 |
| `GALAXY_PG_HOST` | PG 主机 | `127.0.0.1`(原生) |
| `GALAXY_PG_PORT` | PG 端口 | `5432` |
| `GALAXY_PG_DB/USER/PASSWORD` | 库/用户/密码 | 自定(与 galaxy-core 的 PG 一致) |
| `DATA_FOLDER_PATH` | SQLite 落点(`equity.db`) | `data` |
| `OPENROUTER_API_KEY` | AI 链(builder agent) | 可空 |

## Docker

```bash
docker build -t galaxy-web:latest .
docker compose up -d
curl http://127.0.0.1:8001/api/widgets.json
```

- `GALAXY_PG_HOST`:容器内 `127.0.0.1` 指向容器自身;宿主 PG 用
  `host.docker.internal`,LAN/QNAP PG 直接填 IP/Tailscale 名。
- supervisord.conf 另带 opencode(`:4096`)+vibe(`:8899`);单 API 部署可裁到只留 uvicorn 段。

## NixOS 原生

module: `nixos-config/modules/services/galaxy-web.nix`(待按新入口重写:
`openbb_app.main:app`,端口 8001)。

```bash
# 1. 敏感项落盘(不进 nix store):
cat > ~/.config/galaxy-web.env <<'EOF'
APP_API_KEY=<...>
GALAXY_PG_HOST=127.0.0.1
GALAXY_PG_PORT=5432
GALAXY_PG_DB=galaxy
GALAXY_PG_USER=postgres
GALAXY_PG_PASSWORD=<db-password>
OPENROUTER_API_KEY=<...>
EOF
chmod 600 ~/.config/galaxy-web.env

# 2. rebuild + 起服务:
sudo nixos-rebuild switch --flake ~/nixos-config#lenovo
systemctl --user daemon-reload
systemctl --user enable --now galaxy-web
journalctl --user -u galaxy-web -f
```

- 本地开发等价命令:`uv run uvicorn openbb_app.main:app --reload --port 8001`(3.13 venv)。

## Workspace 联调

OpenBB Workspace → Add Backend → URL 填
`http://<host>:8001`(LAN 用宿主 IP/Tailscale 名) →
出现 **A股** app → 三模块出数(Profile/Financials/Stock Price)。
鉴权:Bearer `APP_API_KEY`。
