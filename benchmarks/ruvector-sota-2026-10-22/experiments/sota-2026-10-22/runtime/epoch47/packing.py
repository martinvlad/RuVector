"""Two disjoint whole source-unit anchors under one frozen compact prefill cap.

Only fixed ranking order and exact tokenizer-length receipts decide admission.
No source text is truncated, rewritten or synthesized. Missing admissible units
stop the run and never become an insufficient-evidence decision.
"""
import hashlib
import json

FULL_PROMPT_TOKEN_CAP = 320
PACKING_POLICY = "TWO_DISJOINT_WHOLE_SOURCE_UNIT_ANCHORS"


def hash_text(text): return hashlib.sha256(text.encode()).hexdigest()


def render(P, claim, first, second):
    # Empty windows occur only in exact token-budget probes.
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
    C.require(P.MAX_PROMPT_TOKENS == FULL_PROMPT_TOKEN_CAP,
              "COMPACT_PROTOCOL_CAP_MISMATCH")
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
    _, base_tokens, _ = measure([], [], "EMPTY_WINDOWS_BASE", None)
    budget = (FULL_PROMPT_TOKEN_CAP - len(base_tokens)) // 2
    C.require(budget > 0, "FULL_CLAIM_INSTRUCTIONS_CANNOT_FIT")
    windows = []; chosen = set(); receipts = []
    for number in range(2):
        selected = None; decisions = []
        for anchor in ranking:
            if anchor in chosen: continue
            proposal = {anchor}
            ids = (proposal, set()) if number == 0 else (set(), proposal)
            _, tokens, row = measure(*ids, "WHOLE_UNIT_PROPOSAL", number)
            marginal = len(tokens) - len(base_tokens)
            accepted = marginal <= budget
            decisions.append({"anchor": anchor, "group_unit_ids": [anchor],
                              "proposed_unit_ids": [anchor], "marginal_tokens": marginal,
                              "accepted": accepted, "journal_ordinal": row["ordinal"]})
            if accepted:
                selected = anchor
                break
        C.require(selected is not None, "NO_WHOLE_SOURCE_UNIT_FITS" if number == 0 else
                  "NO_SECOND_DISJOINT_WHOLE_SOURCE_UNIT_FITS")
        chosen.add(selected); window = [selected]; windows.append(window)
        receipts.append({"window_index": number, "source_unit_ids": window,
                         "text_sha256": hash_text(spans[selected]["sentence"]),
                         "duplicate_first": False, "equal_marginal_budget": budget,
                         "selection_decisions": decisions,
                         "source_spans": [{"unit_id": selected, "start": spans[selected]["start"],
                                           "end": spans[selected]["end"],
                                           "sha256": hash_text(spans[selected]["sentence"])}]})
    prompt, tokens, final = measure(*windows, "FINAL_COMBINED_PROMPT", None)
    C.require(len(tokens) <= FULL_PROMPT_TOKEN_CAP,
              "COMBINED_PROMPT_OVERFLOW_NO_TRUNCATION_OR_RETRY")
    C.require(len(windows) == 2 and all(len(w) == 1 for w in windows) and
              windows[0][0] != windows[1][0], "TWO_DISJOINT_WHOLE_SOURCE_UNIT_ANCHORS_REQUIRED")
    return {"prompt": prompt, "tokens": tokens, "windows": receipts,
            "packing_policy": PACKING_POLICY,
            "base_prompt_tokens": len(base_tokens), "equal_window_budget": budget,
            "final_journal_ordinal": final["ordinal"], "prompt_sha256": hash_text(prompt),
            "token_ids_sha256": C.sha_json(tokens), "prompt_token_count": len(tokens),
            "no_truncation": True, "full_claim_preserved": True,
            "union_selected_unit_ids": sorted(chosen)}
