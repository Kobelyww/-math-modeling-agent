"""FastAPI 应用入口。

启动: uvicorn agent_app.web.main:app --reload --port 8000
"""

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import _token_drainer, router

WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="数模多智能体协作系统", version="2.0")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
app.include_router(router)


@app.on_event("startup")
async def startup():
    asyncio.create_task(_token_drainer())


def main() -> None:
    import uvicorn
    uvicorn.run("agent_app.web.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
