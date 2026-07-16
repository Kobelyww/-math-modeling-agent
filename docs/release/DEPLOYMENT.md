# Zhihu Fiction Deployment

## Local Development

```bash
python -m uvicorn zhihu_fiction.server:app --port 8023
```

Open `http://127.0.0.1:8023/video`.

## Production-Like Docker Compose

1. Copy `zhihu_fiction/.env.production.example` to a private env file, for example `zhihu_fiction/.env.production.local`.
2. Fill `ZH_WEB_API_TOKEN`, `DEEPSEEK_API_KEY`, and `DASHSCOPE_API_KEY` or `BAILIAN_API_KEY`.
3. Point Compose at the private env file and run:

```bash
docker compose --env-file zhihu_fiction/.env.production.local up --build
```

Compose interpolation for `PYTHON_IMAGE`, `ZH_WEB_PORT`, `ZH_REDIS_PORT`, `ZH_MINIO_API_PORT`, `ZH_MINIO_CONSOLE_PORT`, and `ZH_COMPOSE_ENV_FILE` reads from the shell, the project `.env`, or the `docker compose --env-file` file. The service `env_file` alone is not used for build args, host ports, or selecting another env file.

This starts the web app, Redis, MinIO, and the `video-worker` process that consumes persisted video jobs from Redis.

4. Check:

```bash
curl http://127.0.0.1:${ZH_WEB_PORT:-8000}/health
curl http://127.0.0.1:${ZH_WEB_PORT:-8000}/ready
```

5. Call protected API routes with:

```bash
curl -H "Authorization: Bearer $ZH_WEB_API_TOKEN" http://127.0.0.1:${ZH_WEB_PORT:-8000}/api/drama-video/infrastructure
```

## Production Notes

- Do not commit real `.env` or production token files.
- Redis and MinIO in compose are suitable for staging and local validation, not managed production durability.
- Public deployment must use HTTPS, restricted CORS, and a rotated `ZH_WEB_API_TOKEN`.
- Set `ZH_EXPOSE_ERROR_DETAILS=false` outside local development.
- Keep video shot limits and `ZH_VIDEO_UNIT_PRICE_CNY` updated before enabling automated generation.
- If the default host ports are occupied, override `ZH_WEB_PORT`, `ZH_REDIS_PORT`, `ZH_MINIO_API_PORT`, and `ZH_MINIO_CONSOLE_PORT`.
- If the configured Docker registry cannot fetch `python:3.13-slim`, set `PYTHON_IMAGE` to an approved local mirror image before building.
