# backend/app/services/gl_review/memo.py
# ============================================================
# The "GPT explains" layer. Two memo products:
#   1. AI Review Packet (packet-level) — Data Overview / Review Queue Summary /
#      Data Quality Notes / Key Review Signals / Recommended Actions.
#   2. Row evidence memo (per flagged row) — three blocks:
#        · Why this row matters   (anchors woven in as design rationale)
#        · Evidence to request    (anchors woven in)
#        · Not a conclusion       (the hedge)
#
# Guardrails are adapted from LUCENT's prompts.py: the BANNED_PHRASES list and
# the framing rule are reused verbatim so the memo can never drift into fraud
# conclusions or audit opinions. A post-generation scan enforces it.
# ============================================================

from __future__ import annotations

import json
import re
import os

from .anchors import (FRAMING_RULE, MOVE_ANCHORS, SIGNAL_ANCHORS,
                      anchors_for_flags)

_MODEL = "gpt-4o-mini"

# Reused verbatim from LUCENT prompts.py — the phrases the model must never emit.
BANNED_PHRASES: tuple[str, ...] = (
    "fraud occurred", "this is fraudulent", "this is fraud", "this proves fraud",
    "proves fraud", "confirms fraud", "confirmed misstatement",
    "confirms a material weakness", "confirms a significant deficiency",
    "the vendor is suspicious", "the perpetrator", "management committed fraud",
    "employee committed fraud", "definitively", "the transaction is fake",
    "this is a pcaob violation", "the employee stole", "the manager stole",
)

REQUIRED_DISCLAIMER = (
    "This analysis identifies risk indicators only. "
    "It does not determine intent, fraud, or an audit conclusion."
)

GUARDRAIL = (
    "LUCENT indicates review priority only. "
    "It does not conclude fraud or issue audit opinions."
)

_SYSTEM = (
    "You are a careful audit-review assistant that helps a reviewer TRIAGE a "
    "general ledger before formal work. You identify RISK INDICATORS and the "
    "EVIDENCE a reviewer should request. You never determine fraud, intent, or "
    "an audit conclusion, and you never issue an audit opinion.\n\n"
    "HARD RULES:\n"
    "1. Hedged language only. Use 'potential', 'may indicate', 'worth reviewing'. "
    "Never state that fraud occurred, that a transaction is fraudulent, or that "
    "anything is confirmed or definitive.\n"
    "2. The SUBJECT is the transaction or control — never the person who recorded "
    "it. Do not speculate about intent, motive, or who booked the entry.\n"
    "3. Audit standards are DESIGN RATIONALE only. " + FRAMING_RULE + "\n"
    "4. Ground every statement in the observable facts provided (amount, active "
    "flags, materiality annotation, override status, anomaly tier). Do not invent "
    "figures or citations.\n"
    "5. The anomaly score is a statistical outlier measure, not a probability of "
    "fraud."
)


def _client():
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=key)


def _chat(client, system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=_MODEL, temperature=0,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return resp.choices[0].message.content or ""


def scan_guardrail(text: str) -> list[str]:
    """Return any banned phrases found (case-insensitive). Empty list = clean."""
    low = (text or "").lower()
    return [p for p in BANNED_PHRASES if p in low]


# The pinned labels, used both in the prompts and to split a memo back apart.
ROW_LABELS: tuple[str, ...] = (
    "Why this row matters", "Evidence to request", "Not a conclusion")
PACKET_LABELS: tuple[str, ...] = (
    "Data Overview", "Review Queue Summary", "Data Quality Notes",
    "Key Review Signals", "Recommended Actions")


def split_blocks(text: str, labels: tuple[str, ...]) -> dict[str, str]:
    """Split a memo into {label: body} using the pinned bold labels."""
    if not text:
        return {}
    pattern = "|".join(re.escape(f"**{l}**") for l in labels)
    parts = re.split(f"({pattern})", text)
    out: dict[str, str] = {}
    current: str | None = None
    for part in parts:
        s = (part or "").strip()
        if not s:
            continue
        m = re.fullmatch(r"\*\*(.+?)\*\*", s)
        if m and m.group(1) in labels:
            current = m.group(1)
            out.setdefault(current, "")
        elif current:
            out[current] = (out.get(current, "") + "\n" + s).strip()
    return out


def merge_bilingual(ko_text: str, en_text: str, labels: tuple[str, ...]) -> str:
    """Interleave two single-language memos block by block:

        **Label**
        (Korean body)
        (English body)

    Each half was generated as a PRIMARY memo in its own language, so both
    carry full detail — unlike asking one call to produce both languages,
    where the model reliably treated the second language as a summary.
    Falls back to plain concatenation if either side can't be parsed.
    """
    ko, en = split_blocks(ko_text, labels), split_blocks(en_text, labels)
    if not ko or not en:
        return f"{(ko_text or '').strip()}\n\n{(en_text or '').strip()}".strip()

    lines: list[str] = []
    for label in labels:
        k, e = ko.get(label, "").strip(), en.get(label, "").strip()
        if not k and not e:
            continue
        lines.append(f"**{label}**  ")   # trailing 2 spaces = markdown hard break,
                                         # else the label and the Korean line render
                                         # as one paragraph in the browser
        if k:
            lines.append(k + "  ")      # markdown hard break
        if e:
            lines.append(e)
        lines.append("")
    return "\n".join(lines).strip()


def _flag_keys_from_row(row: dict) -> list[str]:
    keys = [k for k in SIGNAL_ANCHORS
            if k != "amount_zscore_by_account" and int(row.get(k, 0) or 0) == 1]
    try:
        if abs(float(row.get("amount_zscore_by_account", 0) or 0)) >= 2.0:
            keys.insert(0, "amount_zscore_by_account")
    except (TypeError, ValueError):
        pass
    return keys


def build_row_memo(client, row: dict, lang_instruction: str) -> dict:
    """Three-block evidence memo for one flagged row, anchors woven in."""
    flag_keys = _flag_keys_from_row(row)
    anchor_list = anchors_for_flags(flag_keys)
    anchor_ctx = "\n".join(
        f"- {a['signal']}: designed around {a['source']} — {a['rationale']}. "
        f"Evidence hint: {a['evidence']}."
        for a in anchor_list) or "- (no discrete flags; statistical anomaly only)"

    override = int(row.get("is_qualitative_override", 0) or 0) == 1
    override_note = str(row.get("qualitative_override_note", "") or "")
    facts = {
        "date": str(row.get("date", "")),
        "account": row.get("account_name", ""),
        "vendor": row.get("vendor", ""),
        "amount": row.get("abs_amount", row.get("amount", "")),
        "priority_tier": row.get("final_tier", ""),
        "pcaob_label": row.get("pcaob_label", ""),
        "active_flags": row.get("active_flags", ""),
        "materiality": row.get("materiality_annotation", ""),
        "qualitative_override": "yes" if override else "no",
    }

    # When the override fired, the fact that materiality alone would have
    # DEPRIORITIZED this row — and that co-occurrence rescued it — is the single
    # most informative thing about it. Left as optional context the model
    # ignored it, producing a memo that never explained the "escalated" badge
    # the UI shows. So it is now a REQUIRED sentence.
    if override:
        override_block = (
            "\nESCALATION — THIS ROW WAS RESCUED BY THE QUALITATIVE OVERRIDE.\n"
            f"Engine note: {override_note}\n"
            "MANDATORY: the 'Why this row matters' block MUST state, in plain "
            "language, that the dollar amount on its own would have placed this row "
            "at a LOWER review priority, and that the co-occurrence of two or more "
            "indicators is why it is elevated instead — qualitative materiality, "
            "designed around PCAOB AS 2401 / AS 2201. Do not omit this. Do not "
            "describe it as a finding; it is a prioritization step.\n")
    else:
        override_block = ""

    user = (
        f"Flagged GL row facts:\n{json.dumps(facts, ensure_ascii=False, default=str)}\n\n"
        f"Signals that fired, with their audit-standard design rationale (use these "
        f"as DESIGN RATIONALE only — never as findings or performed procedures):\n"
        f"{anchor_ctx}\n"
        + override_block
        + "\nWrite a compact evidence memo with EXACTLY three blocks.\n\n"
        "BLOCK REQUIREMENTS — this is a description of what to WRITE ABOUT. It is NOT "
        "text to reproduce. Never copy, translate, or echo these requirement lines into "
        "your answer; replace each one with real content about this transaction.\n"
        "  Why this row matters: what makes this row worth a reviewer's time, weaving in "
        "the relevant standard as design rationale.\n"
        "  Evidence to request: the specific documents or records a reviewer should ask "
        "for, informed by the evidence hints above.\n"
        "  Not a conclusion: one sentence noting this indicates review priority only, "
        "not fraud or a finding.\n\n"
        "OUTPUT FORMAT (follow exactly):\n"
        "- Emit these three labels, in this order, each alone on its own line, in bold "
        "markdown, VERBATIM in English, never translated or reworded:\n"
        "  **Why this row matters**\n  **Evidence to request**\n  **Not a conclusion**\n"
        "- Put NOTHING after a label on its line — no em-dash, no colon, no text.\n"
        "- Under each label write 1-3 sentences of real content on the following "
        "line(s).\n"
        "- Name the specific account and vendor from the facts above. Do not write "
        "vaguely about 'a specific account' or 'the vendor' when the names are given.\n\n"
        + lang_instruction)

    text = _chat(client, _SYSTEM, user)
    hits = scan_guardrail(text)
    return {"memo": text, "guardrail_ok": not hits, "guardrail_hits": hits,
            "anchors_used": [a["source"] for a in anchor_list]}


def build_packet_memo(client, overview: dict, lang_instruction: str) -> dict:
    """AI Review Packet — five compact sections over the whole GL."""
    user = (
        f"GL review context:\n{json.dumps(overview, ensure_ascii=False, default=str)}\n\n"
        "Write a compact AI Review Packet with EXACTLY five sections.\n\n"
        "SECTION REQUIREMENTS — this is a description of what to WRITE ABOUT. It is "
        "NOT text to reproduce. Never copy, translate, or echo these requirement "
        "lines into your answer; replace each one with real content drawn from the "
        "review context above.\n"
        "  Data Overview: the period, how many transactions, the main accounts and "
        "vendors.\n"
        "  Review Queue Summary: how many of the total transactions were narrowed to "
        "follow-up, and the priority split.\n"
        "  Data Quality Notes: what the integrity checks found (date-in-period, "
        "cross-footing, hash total, account mapping).\n"
        "  Key Review Signals: which signals are actually driving the queue. Use "
        "signals_in_flagged_queue; key_signals_population is whole-ledger context only.\n"
        "  Recommended Actions: what the reviewer should look at first and in what "
        "order. Base this ONLY on signals_in_flagged_queue — never recommend starting "
        "with a signal that is absent from the flagged queue, however common it is in "
        "the population.\n\n"
        "OUTPUT FORMAT (follow exactly):\n"
        "- Emit these five labels, in this order, each alone on its own line, in bold "
        "markdown, VERBATIM in English, never translated or reworded:\n"
        "  **Data Overview**\n  **Review Queue Summary**\n  **Data Quality Notes**\n"
        "  **Key Review Signals**\n  **Recommended Actions**\n"
        "- Put NOTHING after a label on its line — no em-dash, no colon, no text.\n"
        "- Under each label write 1-3 sentences of real content on the following "
        "line(s).\n\n"
        "Materiality (benchmark → FS 4-5% → performance 50% → transaction 80%) sets the "
        "review floor; the qualitative override lifts a row off it when two or more "
        "indicators co-occur. Standards are design rationale only.\n\n" + lang_instruction)

    text = _chat(client, _SYSTEM, user)
    hits = scan_guardrail(text)
    return {"memo": text, "guardrail_ok": not hits, "guardrail_hits": hits}
