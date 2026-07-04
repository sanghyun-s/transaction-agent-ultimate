# backend/app/routers/history.py
# ============================================================
# Work History endpoints.
#   GET    /api/history            list (?tool=... filter) + available tools
#   POST   /api/history/save       any tool saves a result (button-driven)
#   GET    /api/history/{id}       one item (click-to-reopen)
#   GET    /api/history/{id}/download   re-download its artifact, if any
#   DELETE /api/history/reset      clear all
#   DELETE /api/history/{id}       delete one
#   DELETE /api/history            legacy "clear all" (kept for old frontend)
# ============================================================

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.models.history_schemas import HistorySaveRequest
from app.services import history_service

router = APIRouter(prefix="/api/history", tags=["history"])


def _legacy(item: dict) -> dict:
    """Backward-compat aliases so the CURRENT (pre-refactor) frontend history
    page keeps rendering (it reads .transaction / .content / .timestamp).
    Remove these three keys once the frontend Work History page ships."""
    return {
        **item,
        "transaction": item.get("title", ""),
        "content": item.get("output_content", ""),
        "timestamp": item.get("created_at", ""),
    }


@router.get("")
def get_history_list(tool: Optional[str] = Query(None, description="Filter by tool_name")):
    items = history_service.list_history(tool_name=tool)
    return {
        "history": [_legacy(i) for i in items],
        "tools": history_service.list_tools(),
    }


@router.post("/save")
def save_history(req: HistorySaveRequest):
    item = history_service.save_to_history(**req.model_dump())
    return {"success": True, "item": item}


# NOTE: literal routes (/save, /reset) are declared BEFORE the /{item_id}
# catch-all so they are matched first.
@router.delete("/reset")
def reset_history_endpoint():
    n = history_service.reset_history()
    return {"success": True, "deleted": n}


@router.get("/{item_id}")
def get_history_item(item_id: str):
    item = history_service.get_history(item_id)
    if not item:
        return {"success": False, "error": "Not found"}
    return {"success": True, "item": item}


@router.get("/{item_id}/download")
def download_history_artifact(item_id: str):
    item = history_service.get_history(item_id)
    if not item or not item.get("artifact_path"):
        return {"success": False, "error": "No artifact for this item"}
    path = Path(item["artifact_path"])
    if not path.exists():
        return {"success": False, "error": "Artifact file missing on server"}
    return FileResponse(path, filename=path.name)


@router.delete("/{item_id}")
def delete_history_item(item_id: str):
    ok = history_service.delete_history(item_id)
    return {"success": ok}


@router.delete("")
def clear_history_legacy():
    """Old behavior: DELETE /api/history cleared everything."""
    n = history_service.reset_history()
    return {"message": "히스토리가 초기화되었습니다.", "deleted": n}
