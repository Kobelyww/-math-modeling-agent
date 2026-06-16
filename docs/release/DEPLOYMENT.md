# Zhihu Fiction Deployment

## Local Development

```bash
python -m uvicorn zhihu_fiction.server:app --port 8023
```

Open `http://127.0.0.1:8023/video`.

## Production-Like Docker Compose

1. Copy `zhihu_fiction/.env.production.example` to a private env file.
2. Fill `ZH_WEB_API_TOKEN`, `DEEPSEEK_API_KEY`, and `DASHSCOPE_API_KEY` or `BAILIAN_API_KEY`.
3. Run:

```bash
docker compose up --build
```

This starts the web app, Redis, MinIO, and the `video-worker` process that consumes persisted video jobs from Redis.

4. Check:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

5. Call protected API routes with:

```bash
curl -H "Authorization: Bearer $ZH_WEB_API_TOKEN" http://127.0.0.1:8000/api/drama-video/infrastructure
```

## Production Notes

- Do not commit real `.env` or production token files.
- Redis and MinIO in compose are suitable for staging and local validation, not managed production durability.
- Public deployment must use HTTPS, restricted CORS, and a rotated `ZH_WEB_API_TOKEN`.
- Set `ZH_EXPOSE_ERROR_DETAILS=false` outside local development.
- Keep video shot limits and `ZH_VIDEO_UNIT_PRICE_CNY` updated before enabling automated generation.
