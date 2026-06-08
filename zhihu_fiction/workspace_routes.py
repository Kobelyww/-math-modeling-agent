"""FastAPI routes for workspace workflows."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .workspace.schemas import (
    CreateTaskRequest,
    DraftUpdateRequest,
    GeneratePackageRequest,
    ImportScrapedRequest,
    ManualMaterialRequest,
    TopicCardRequest,
)


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{name} not found")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=409, detail=message)


def _model_dump(model, *, exclude_unset: bool = False) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=exclude_unset)
    return model.dict(exclude_unset=exclude_unset)


def _record_dict(record) -> dict:
    return record.to_dict()


def create_workspace_router(service, queue, exporter_factory) -> APIRouter:
    router = APIRouter(prefix="/api/workspace", tags=["workspace"])
    repo = service.repo

    @router.get("/materials")
    def list_materials():
        return [_record_dict(material) for material in repo.list_materials()]

    @router.post("/materials/import-scraped")
    def import_scraped(req: ImportScrapedRequest):
        return service.import_scraped_items(req.items)

    @router.post("/materials/manual")
    def create_manual_material(req: ManualMaterialRequest):
        try:
            material = service.create_manual_material(**_model_dump(req))
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(material)

    @router.patch("/materials/{material_id}")
    def update_material(material_id: str, changes: dict):
        try:
            material = repo.update_material(material_id, changes)
        except KeyError as exc:
            raise _not_found("material") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(material)

    @router.get("/topic-cards")
    def list_topic_cards():
        return [_record_dict(card) for card in repo.list_topic_cards()]

    @router.post("/topic-cards")
    def create_topic_card(req: TopicCardRequest):
        try:
            card = service.create_topic_card(**_model_dump(req))
        except KeyError as exc:
            raise _not_found("material") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(card)

    @router.patch("/topic-cards/{card_id}")
    def update_topic_card(card_id: str, changes: dict):
        try:
            card = repo.update_topic_card(card_id, changes)
        except KeyError as exc:
            raise _not_found("topic card") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(card)

    @router.post("/topic-cards/{card_id}/approve")
    def approve_topic_card(card_id: str):
        try:
            card = service.approve_topic_card(card_id)
        except KeyError as exc:
            raise _not_found("topic card") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(card)

    @router.post("/topic-cards/{card_id}/create-task")
    def create_task_from_topic_card(
        card_id: str,
        req: CreateTaskRequest | None = None,
    ):
        req = req or CreateTaskRequest()
        try:
            task = service.create_task_from_topic_card(card_id, **_model_dump(req))
        except KeyError as exc:
            raise _not_found("topic card") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        queue.kick()
        return _record_dict(task)

    @router.get("/tasks")
    def list_tasks():
        return [_record_dict(task) for task in repo.list_tasks()]

    @router.post("/tasks/{task_id}/retry")
    def retry_task(task_id: str):
        try:
            task = queue.retry(task_id)
        except KeyError as exc:
            raise _not_found("task") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        queue.kick()
        return _record_dict(task)

    @router.post("/tasks/{task_id}/cancel")
    def cancel_task(task_id: str):
        try:
            task = queue.cancel(task_id)
        except KeyError as exc:
            raise _not_found("task") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(task)

    @router.get("/drafts")
    def list_drafts():
        return [_record_dict(draft) for draft in repo.list_review_drafts()]

    @router.get("/drafts/{task_id}")
    def get_draft(task_id: str):
        draft = repo.get_review_draft(task_id)
        if draft is None:
            raise _not_found("draft")
        return _record_dict(draft)

    @router.patch("/drafts/{task_id}")
    def update_draft(task_id: str, req: DraftUpdateRequest):
        try:
            draft = service.update_review_draft(
                task_id,
                _model_dump(req, exclude_unset=True),
            )
        except KeyError as exc:
            raise _not_found("draft") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(draft)

    @router.post("/drafts/{task_id}/ready")
    def mark_draft_ready(task_id: str):
        try:
            draft = service.mark_draft_ready(task_id)
        except KeyError as exc:
            raise _not_found("draft") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(draft)

    @router.get("/packages")
    def list_packages():
        return [_record_dict(package) for package in repo.list_publish_packages()]

    @router.post("/packages/generate")
    def generate_package(req: GeneratePackageRequest):
        try:
            package = service.generate_publish_package(
                req.task_id,
                req.platform,
                exporter_factory(),
            )
        except KeyError as exc:
            raise _not_found("package input") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(package)

    @router.post("/packages/{package_id}/confirm")
    def confirm_package(package_id: str):
        try:
            package = service.confirm_package(package_id)
        except KeyError as exc:
            raise _not_found("package") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _record_dict(package)

    @router.get("/packages/{package_id}/files")
    def get_package_files(package_id: str):
        package = repo.get_publish_package(package_id)
        if package is None:
            raise _not_found("package")
        return _record_dict(package)

    return router
