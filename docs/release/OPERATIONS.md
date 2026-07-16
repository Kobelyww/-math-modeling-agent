# Zhihu Fiction Operations

## Health Checks

- `GET /health`: process is alive.
- `GET /ready`: workspace backend, queue backend, asset backend, model provider, cost guardrail, and recovery counters are available.

## API Protection

Production API routes under `/api/` should run with:

```env
ZH_APP_ENV=production
ZH_REQUIRE_AUTH=true
ZH_WEB_API_TOKEN=<rotated-token>
ZH_EXPOSE_ERROR_DETAILS=false
ZH_CORS_ORIGINS=https://your-domain.example
```

Call protected endpoints with:

```bash
curl -H "Authorization: Bearer $ZH_WEB_API_TOKEN" https://your-domain.example/api/drama-video/infrastructure
```

## Video Job Recovery

On startup, submitted provider jobs are restored by queuing a `refresh_status` job. Unsubmitted in-memory jobs are marked failed with a clear recovery error. Check `/ready` for `video_job_recovery`.

For production, use:

```env
ZH_VIDEO_QUEUE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

Run a separate video worker beside the web process:

```bash
python -m zhihu_fiction.app.services.drama_video_worker
```

The worker dequeues Redis video job ids, reloads the persisted job payload from the workspace repository, and dispatches `generate_video`, `retry_shot`, or `refresh_status` work. Keep the web and worker pointed at the same workspace backend, Redis URL, object storage, and model credentials.

## Cost Controls

- Keep `shot_limit` low by default.
- Configure `ZH_VIDEO_UNIT_PRICE_CNY`.
- Require human confirmation before the billable video stage.
- Review `/api/drama-video/infrastructure` before production runs.
- Prefer one-shot smoke generation before enabling batch runs.

## Storage

Local development can use:

```env
ZH_OBJECT_STORAGE_BACKEND=local
ZH_OBJECT_STORAGE_ROOT=zhihu_fiction/data/objects
```

Production-like deployments can use MinIO:

```env
ZH_OBJECT_STORAGE_BACKEND=minio
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=zhihu-fiction
MINIO_SECURE=false
```

## Common Failures

- `Missing DEEPSEEK_API_KEY`: set `DEEPSEEK_API_KEY`.
- `Missing DASHSCOPE_API_KEY`: set `DASHSCOPE_API_KEY`, `BAILIAN_API_KEY`, or `EMBEDDING_API_KEY`.
- Redis unavailable: switch to `ZH_VIDEO_QUEUE_BACKEND=memory` for local development or restore Redis.
- MinIO unavailable: switch to `ZH_OBJECT_STORAGE_BACKEND=local` for local development or restore MinIO.
- `401 Unauthorized`: send `Authorization: Bearer <ZH_WEB_API_TOKEN>` or disable auth only in development.
- Docker build cannot fetch `python:3.13-slim`: set `PYTHON_IMAGE` to an approved local mirror image and rebuild.
- Host port already allocated: override `ZH_WEB_PORT`, `ZH_REDIS_PORT`, `ZH_MINIO_API_PORT`, or `ZH_MINIO_CONSOLE_PORT`.
