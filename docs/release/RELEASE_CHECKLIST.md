# Zhihu Fiction Release Checklist

Use this checklist before tagging or publishing a build.

- [ ] Secrets are not committed: `.env`, API keys, cookies, and `zhihu_fiction/data/auth/` are absent from git.
- [ ] Production auth is enabled with `ZH_REQUIRE_AUTH=true` and `ZH_WEB_API_TOKEN` set.
- [ ] CORS origins are restricted with `ZH_CORS_ORIGINS`.
- [ ] Production error details are disabled with `ZH_EXPOSE_ERROR_DETAILS=false`.
- [ ] Video cost guardrails are configured with `ZH_VIDEO_UNIT_PRICE_CNY`, shot limits, and human confirmation.
- [ ] Workspace storage backend is selected: JSONL for local, SQLite/Postgres-compatible migration path for production.
- [ ] Queue backend is selected: local for development, Redis for worker deployment.
- [ ] Asset backend is selected: local for development, MinIO for production.
- [ ] Health checks pass: `GET /health` and `GET /ready`.
- [ ] CI is green for unit tests and release artifact checks.
- [ ] `/video` loads without console-blocking API errors in the target environment.
- [ ] A rollback tag or previous image is available.
