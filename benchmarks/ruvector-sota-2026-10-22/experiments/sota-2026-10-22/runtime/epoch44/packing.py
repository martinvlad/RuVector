"""Matched whole-neighbor windows with fixed equal marginal token budgets."""
import hashlib
import json


def hash_text(text): return hashlib.sha256(text.encode()).hexdigest()


def render(P, claim, first, second):
    # Exact official two-message ChatML branch. Empty windows are budget probes
    # only; final requests require both nonempty windows.
    if first and second: return P.build_prompt(claim, [first, second])
    if "<|" in claim or "<|" in first or "<|" in second: raise ValueError("SOURCE_CONTROL_MARKER")
    user = ("SOURCE EXCERPT 1:\n" + first + "\n\nSOURCE EXCERPT 2:\n" + second +
            "\n\nCLAIM:\n" + claim + "\n\nANSWER (N, E, or C):")
    return ("<|im_start|>system\n" + P.SYSTEM + "<|im_end|>\n" +
            "<|im_start|>user\n" + user + "<|im_end|>\n<|im_start|>assistant\n")


def build(C, P, catalog, record, ranking, arm, reader, journal):
    spans = record["evidence"]; catalog.validate_spans(spans)
    C.require(sorted(ranking) == list(range(len(spans))) and
              all(type(i) is int for i in ranking), "EXACT_RANKING_REQUIRED")
    claim = record["claim"]
    def measure(ids1, ids2, stage, index):
        texts = ["\n\n".join(spans[i]["sentence"] for i in sorted(ids)) for ids in (ids1, ids2)]
        prompt = render(P, claim, *texts); tokens, receipt = reader.tokenize(prompt)
        row = {"ordinal": len(journal) + 1, "case_id": record["id"], "arm": arm,
               "stage": stage, "window_index": index, "selected_unit_ids": [sorted(ids1), sorted(ids2)],
               "prompt_sha256": hash_text(prompt), "claim_sha256": hash_text(claim),
               "prompt_token_count": len(tokens), "token_ids_sha256": C.sha_json(tokens),
               "token_ids": tokens, "http_exchange": receipt}
        journal.append(row)
        return prompt, tokens, row
    _, base_tokens, base_row = measure([], [], "EMPTY_WINDOWS_BASE", None)
    budget = (767 - len(base_tokens)) // 2
    C.require(budget > 0, "FULL_CLAIM_INSTRUCTIONS_CANNOT_FIT")
    windows = []; first = set(); receipts = []
    for number in range(2):
        selected = set(); decisions = []
        for anchor in ranking:
            if number == 1 and anchor in first: continue
            group = set(range(max(0, anchor - 1), min(len(spans), anchor + 2)))
            if group <= selected: continue
            proposed = selected | group
            ids = (proposed, set()) if number == 0 else (set(), proposed)
            _, tokens, row = measure(*ids, "WHOLE_GROUP_PROPOSAL", number)
            marginal = len(tokens) - len(base_tokens)
            accepted = marginal <= budget
            decisions.append({"anchor": anchor, "group_unit_ids": sorted(group),
                              "proposed_unit_ids": sorted(proposed), "marginal_tokens": marginal,
                              "accepted": accepted, "journal_ordinal": row["ordinal"]})
            if accepted: selected = proposed
        duplicate = False
        if not selected:
            C.require(number == 1 and first, "NO_WHOLE_NEIGHBOR_GROUP_FITS")
            selected = set(first); duplicate = True
        if number == 0: first = set(selected)
        windows.append(sorted(selected))
        receipts.append({"window_index": number, "source_unit_ids": sorted(selected),
                         "text_sha256":hash_text("\n\n".join(spans[i]["sentence"] for i in sorted(selected))),
                         "duplicate_first": duplicate, "equal_marginal_budget": budget,
                         "selection_decisions": decisions,
                         "source_spans": [{"unit_id": i, "start": spans[i]["start"], "end": spans[i]["end"],
                                           "sha256": hash_text(spans[i]["sentence"])} for i in sorted(selected)]})
    prompt, tokens, final = measure(*windows, "FINAL_COMBINED_PROMPT", None)
    C.require(len(tokens) <= 767, "COMBINED_PROMPT_OVERFLOW_NO_TRUNCATION_OR_RETRY")
    C.require(all(windows), "TWO_NONEMPTY_WINDOWS_REQUIRED")
    return {"prompt": prompt, "tokens": tokens, "windows": receipts,
            "base_prompt_tokens": len(base_tokens), "equal_window_budget": budget,
            "final_journal_ordinal": final["ordinal"], "prompt_sha256": hash_text(prompt),
            "token_ids_sha256": C.sha_json(tokens), "prompt_token_count": len(tokens),
            "no_truncation": True, "full_claim_preserved": True,
            "union_selected_unit_ids": sorted(set(windows[0]) | set(windows[1]))}
