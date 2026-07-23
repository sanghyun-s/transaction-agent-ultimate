# backend/app/services/gl_review/service.py
# ============================================================
# GL Audit Review Packet facade. The full compact pipeline:
#
#   clean GL  →  integrity mini-checks  →  six signals  →  IsolationForest
#   raw_tier  →  materiality cascade + qualitative override  →  top-N
#   selection  →  GPT memos (packet + per-row evidence)
#
# "ML finds (IsolationForest), audit logic adjusts (materiality + override),
#  GPT explains (memo)." The deterministic pipeline runs without any API key;
# only the memo step calls OpenAI.
# ============================================================

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from . import features, integrity, memo, scoring
from .anomaly import DEFAULT_SENSITIVITY, run_isolation_forest


def fs_pct_for_entity(entity_type: str) -> float:
    return 0.05 if entity_type == "Public company" else 0.04


def compute_materiality(entity_type: str, benchmark: float) -> dict:
    fs_pct = fs_pct_for_entity(entity_type)
    fs_mat = benchmark * fs_pct
    perf_mat = fs_mat * 0.50
    txn_mat = fs_mat * 0.80
    return {"fs_pct": fs_pct, "fs_materiality": round(fs_mat, 2),
            "performance_materiality": round(perf_mat, 2),
            "transaction_materiality": round(txn_mat, 2)}


def _lang_instruction(lang: str) -> str:
    """Language rule for the memo body.

    The block LABELS are pinned in English by the prompt (memo.py) so they stay
    stable across runs — gpt-4o-mini was otherwise translating them on some rows
    and not others within the same batch. Only the body text follows this rule.
    """
    if lang == "한국어":
        return ("LANGUAGE: Write all body text in Korean. Keep the block labels "
                "exactly as specified in English — do not translate the labels.")
    if lang == "Bilingual":
        return (
            "LANGUAGE — BILINGUAL, MANDATORY: every block must contain BOTH "
            "languages. Under each block label, write the Korean text first, then "
            "END THE LINE WITH TWO SPACES and start the English text on its own "
            "new line. Do not run the two languages together in one paragraph. "
            "Never output only one language: a block with just Korean or just "
            "English is invalid. Keep the block labels exactly as specified in "
            "English — do not translate the labels, and write each label only once "
            "per block.\n"
            "Example shape (note the line break between languages):\n"
            "**Why this row matters**\n"
            "이 거래는 ... (Korean)\n"
            "This transaction ... (English)")
    return ("LANGUAGE: Write all body text in English. Keep the block labels "
            "exactly as specified.")


def analyze_gl(
    df: pd.DataFrame,
    entity_type: str = "Private company",
    benchmark: float = 150000.0,
    sensitivity: str = DEFAULT_SENSITIVITY,
    period_start: date | None = None,
    period_end: date | None = None,
    top_n: int = 3,
    language: str = "English",
    generate_memos: bool = True,
) -> dict:
    """Run the compact GL review. Deterministic parts always run; memo
    generation runs only when generate_memos and a key is available."""
    ok, missing = features.validate_required_columns(df)
    if not ok:
        return {"success": False,
                "error": f"Missing required columns: {', '.join(missing)}",
                "required": features.REQUIRED_COLUMNS}

    mat = compute_materiality(entity_type, benchmark)

    # ---- deterministic pipeline (no API key needed) ----
    clean = features.clean_gl_data(df)
    findings = integrity.run_integrity_checks(clean, period_start, period_end)
    integrity_summary = integrity.summarize_findings(findings)

    feat = features.add_signals(clean)
    scored = run_isolation_forest(feat, detection_sensitivity=sensitivity)
    scored = scoring.score_dataframe(
        scored, mat["performance_materiality"], mat["transaction_materiality"])

    flagged = scored[scored["flagged_status"] == "Flagged"].copy()
    # order: High before Medium, then most anomalous
    tier_rank = {"High": 0, "Medium": 1, "Low": 2, "Monitor": 3}
    flagged["_rank"] = flagged["final_tier"].map(tier_rank).fillna(9)
    flagged = flagged.sort_values(["_rank", "anomaly_score"], ascending=[True, True])

    n_high = int((scored["final_tier"] == "High").sum())
    n_medium = int((scored["final_tier"] == "Medium").sum())
    n_flagged = int(len(flagged))

    top = flagged.head(top_n)
    top_rows = [{
        "date": str(r.get("date", ""))[:10],
        "account": r.get("account_name", ""),
        "vendor": r.get("vendor", ""),
        "amount": round(float(r.get("abs_amount", 0) or 0), 2),
        "priority": r.get("final_tier", ""),
        "pcaob_label": r.get("pcaob_label", ""),
        "signals": r.get("active_flags", ""),
        "override": int(r.get("is_qualitative_override", 0) or 0) == 1,
    } for _, r in top.iterrows()]

    result = {
        "success": True,
        "materiality": mat,
        "summary_cards": {
            "transactions_analyzed": int(len(scored)),
            "flagged_for_follow_up": n_flagged,
            "high_priority": n_high,
            "medium_priority": n_medium,
            "data_quality": integrity_summary,
        },
        "integrity_findings": [
            {"name": f.name, "status": f.status, "summary": f.summary} for f in findings
        ],
        "top_rows": top_rows,
        "flagged_dataframe": flagged,   # for CSV export (not JSON-serialized)
        "scored_dataframe": scored,
    }

    if not generate_memos:
        return result

    # ---- GPT memos (needs OPENAI_API_KEY) ----
    instr = _lang_instruction(language)
    client = memo._client()

    top_accounts = scored["account_name"].value_counts().head(5).index.tolist()
    top_vendors = scored["vendor"].value_counts().head(5).index.tolist()

    # Two different things, deliberately labelled apart. The population counts
    # describe the whole ledger; the flagged-queue counts describe the rows the
    # reviewer will actually work. Passing only the former made the packet
    # recommend starting with signals that weren't in the queue at all.
    pop_signals = {
        lbl: int((scored[col] == 1).sum())
        for col, lbl in features.FLAG_LABELS.items() if col in scored
    }
    flagged_signals = {
        lbl: int((flagged[col] == 1).sum())
        for col, lbl in features.FLAG_LABELS.items() if col in flagged
    }
    if "amount_zscore_by_account" in flagged.columns:
        flagged_signals["Unusual amount for account"] = int(
            (flagged["amount_zscore_by_account"].abs() >= 2.0).sum())
    n_override = int((flagged.get("is_qualitative_override", pd.Series(dtype=int)) == 1).sum()) \
        if "is_qualitative_override" in flagged.columns else 0

    overview = {
        "transactions": int(len(scored)),
        "period": f"{period_start} .. {period_end}" if period_start else "not specified",
        "top_accounts": top_accounts,
        "top_vendors": top_vendors,
        "flagged": n_flagged, "high": n_high, "medium": n_medium,
        "materiality": mat,
        "integrity": [{"name": f.name, "status": f.status, "summary": f.summary} for f in findings],
        "signals_in_flagged_queue": flagged_signals,
        "rows_escalated_by_override": n_override,
        "key_signals_population": pop_signals,
    }
    packet = _packet_memo(client, overview, language)
    result["packet_memo"] = packet["memo"]
    result["packet_guardrail_ok"] = packet["guardrail_ok"]

    # Row memos run CONCURRENTLY. Each call is I/O-bound (waiting on OpenAI), so
    # threads work well despite the GIL. This matters most in Bilingual mode,
    # which issues two calls per row — Top 5 bilingual is 10 row calls, ~60s
    # sequentially versus a few seconds in parallel (and well inside the
    # frontend's fetch timeout).
    rows = [r.to_dict() for _, r in top.iterrows()]

    def _one(row_dict: dict) -> dict:
        m = _row_memo(client, row_dict, language)
        return {
            "date": str(row_dict.get("date", ""))[:10],
            "vendor": row_dict.get("vendor", ""),
            "amount": round(float(row_dict.get("abs_amount", 0) or 0), 2),
            "priority": row_dict.get("final_tier", ""),
            **m,
        }

    if rows:
        with ThreadPoolExecutor(max_workers=min(10, len(rows))) as pool:
            row_memos = list(pool.map(_one, rows))   # order preserved
    else:
        row_memos = []

    result["row_memos"] = row_memos
    result["guardrail"] = memo.GUARDRAIL
    return result


def _row_memo(client, row_dict: dict, language: str) -> dict:
    """One row memo. In Bilingual mode, generate each language as its own
    PRIMARY memo and interleave them — asking a single call for both languages
    reliably produced a full English memo and a Korean summary."""
    if language != "Bilingual":
        return memo.build_row_memo(client, row_dict, _lang_instruction(language))

    ko = memo.build_row_memo(client, row_dict, _lang_instruction("한국어"))
    en = memo.build_row_memo(client, row_dict, _lang_instruction("English"))
    return {
        "memo": memo.merge_bilingual(ko["memo"], en["memo"], memo.ROW_LABELS),
        "guardrail_ok": ko["guardrail_ok"] and en["guardrail_ok"],
        "guardrail_hits": list(ko["guardrail_hits"]) + list(en["guardrail_hits"]),
        "anchors_used": ko.get("anchors_used", []),
    }


def _packet_memo(client, overview: dict, language: str) -> dict:
    """Same two-pass treatment for the packet memo."""
    if language != "Bilingual":
        return memo.build_packet_memo(client, overview, _lang_instruction(language))

    ko = memo.build_packet_memo(client, overview, _lang_instruction("한국어"))
    en = memo.build_packet_memo(client, overview, _lang_instruction("English"))
    return {
        "memo": memo.merge_bilingual(ko["memo"], en["memo"], memo.PACKET_LABELS),
        "guardrail_ok": ko["guardrail_ok"] and en["guardrail_ok"],
        "guardrail_hits": list(ko["guardrail_hits"]) + list(en["guardrail_hits"]),
    }
