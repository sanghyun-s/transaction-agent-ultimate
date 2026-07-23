# backend/app/routers/gl_review.py
# ============================================================
# GL Audit Review Packet (LUCENT add-on) endpoints.
#   POST /api/gl-review/analyze                 — GL + settings -> review packet
#   GET  /api/gl-review/download/{req_id}/{kind} — flagged CSV | memo markdown
# ============================================================

from __future__ import annotations

import io
import uuid
from datetime import date, datetime

import pandas as pd
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from app.services import gl_review as gl_service
from app.services.gl_review import memo as memo_mod

router = APIRouter(prefix="/api/gl-review", tags=["gl-review"])

# req_id -> {"flagged_csv": str, "memo_md": str, "filename": str}
_EXPORTS: dict[str, dict] = {}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def _read_upload(data: bytes, filename: str) -> pd.DataFrame:
    lower = (filename or "").lower()
    if lower.endswith((".xlsx", ".xls", ".xltx")):
        return pd.read_excel(io.BytesIO(data))
    return pd.read_csv(io.BytesIO(data))


def _build_memo_markdown(result: dict, filename: str) -> str:
    m = result.get("materiality", {})
    c = result.get("summary_cards", {})
    lines = [
        "# GL Audit Review Packet",
        "",
        f"**File:** {filename}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"**Materiality** — FS ${m.get('fs_materiality', 0):,.0f} · "
        f"Performance ${m.get('performance_materiality', 0):,.0f} · "
        f"Transaction ${m.get('transaction_materiality', 0):,.0f}",
        "",
        "## Summary",
        "",
        f"- Transactions analyzed: {c.get('transactions_analyzed', 0)}",
        f"- Flagged for follow-up: {c.get('flagged_for_follow_up', 0)}",
        f"- High priority: {c.get('high_priority', 0)} · Medium: {c.get('medium_priority', 0)}",
        "",
    ]
    if result.get("packet_memo"):
        lines += ["## AI Review Packet", "", result["packet_memo"], ""]

    if result.get("integrity_findings"):
        lines += ["## Data Quality Checks", ""]
        for f in result["integrity_findings"]:
            lines.append(f"- **{f['name']}** — {f['status']}: {f['summary']}")
        lines.append("")

    if result.get("row_memos"):
        lines += ["## Evidence Memos — Top Flagged Rows", ""]
        for i, rm in enumerate(result["row_memos"], start=1):
            lines += [
                f"### {i}. {rm['date']} · {rm['vendor']} · ${rm['amount']:,.2f} "
                f"({rm['priority']})",
                "",
                rm.get("memo", ""),
                "",
            ]

    lines += ["---", "", f"_{memo_mod.GUARDRAIL}_", ""]
    return "\n".join(lines)


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    entity_type: str = Form("Private company"),
    benchmark: float = Form(150000.0),
    sensitivity: str = Form("Balanced (0.05)"),
    period_start: str = Form(""),
    period_end: str = Form(""),
    top_n: int = Form(3),
    language: str = Form("English"),
    generate_memos: bool = Form(True),
):
    try:
        data = await file.read()
        df = _read_upload(data, file.filename)
    except Exception as e:
        return {"success": False, "error": f"Could not read the file: {e}"}

    try:
        result = gl_service.analyze_gl(
            df,
            entity_type=entity_type,
            benchmark=float(benchmark),
            sensitivity=sensitivity,
            period_start=_parse_date(period_start),
            period_end=_parse_date(period_end),
            top_n=max(1, min(int(top_n), 5)),
            language=language,
            generate_memos=bool(generate_memos),
        )
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not result.get("success"):
        return result

    # stash exports, drop the dataframes from the JSON response
    flagged_df = result.pop("flagged_dataframe", None)
    result.pop("scored_dataframe", None)

    req_id = uuid.uuid4().hex[:12]
    export_cols = [c for c in [
        "date", "account_code", "account_name", "vendor", "description",
        "journal_ref", "amount", "abs_amount", "final_tier", "pcaob_label",
        "active_flags", "materiality_annotation", "anomaly_score", "raw_tier",
        "fraud_flag_count", "is_qualitative_override", "qualitative_override_note",
    ] if flagged_df is not None and c in flagged_df.columns]

    _EXPORTS[req_id] = {
        "flagged_csv": flagged_df[export_cols].to_csv(index=False) if flagged_df is not None else "",
        "memo_md": _build_memo_markdown(result, file.filename),
        "filename": file.filename or "gl.csv",
    }
    result["req_id"] = req_id
    result["guardrail"] = memo_mod.GUARDRAIL
    return result


@router.get("/download/{req_id}/{kind}")
async def download(req_id: str, kind: str):
    item = _EXPORTS.get(req_id)
    if not item:
        return {"success": False, "error": "Export not found (it may have expired)."}

    stem = (item["filename"].rsplit(".", 1)[0] or "gl_review")[:60]
    if kind == "csv":
        return Response(
            content=item["flagged_csv"],
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{stem}_flagged.csv"'},
        )
    if kind == "memo":
        return Response(
            content=item["memo_md"],
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{stem}_review_packet.md"'},
        )
    return {"success": False, "error": f"Unknown export kind: {kind}"}
