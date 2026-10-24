"""CC0 independent authoring, never imports or calls the candidate parser.

Each block/edge below is a manual structural annotation of newly authored text.
The authoring helper only concatenates those literals and calculates offsets.
"""
import hashlib
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def block(label, marker, body, parent=None, indent="", ending="\n"):
    return dict(label=label, marker=marker, body=body, parent=parent,
                indent=indent, ending=ending)


def excerpt(eid, blocks, preamble=""):
    text = preamble
    units = []
    counts = {}
    for b in blocks:
        start = len(text) + len(b["indent"])
        segment = b["indent"] + b["marker"] + " " + b["body"] + b["ending"]
        end = len(text + segment.rstrip())
        counts[b["label"]] = counts.get(b["label"], 0) + 1
        occurrence = counts[b["label"]]
        uid = eid + "::" + b["label"] + ("#" + str(occurrence) if occurrence > 1 else "")
        units.append(dict(id=uid, label=b["label"], parent_id=(eid + "::" + b["parent"]) if b["parent"] else None,
                          marker=[start, start + len(b["marker"])],
                          content=[start + len(b["marker"]) + 1, end], whole=[start, end]))
        text += segment
    return dict(id=eid, text=text), units


def case(number, excerpts, query, refs=(), unknown_codes=(), cycles=(),
         budget=None, parser_budget=False, coverage=""):
    src = [x[0] for x in excerpts]
    units = [u for x in excerpts for u in x[1]]
    byid = {x["id"]: x for x in units}
    edges = {(u["id"], u["parent_id"]) for u in units if u["parent_id"]}
    expected_refs = []
    for eid, owner, trigger, target, resolved, status in refs:
        source = next(x["text"] for x in src if x["id"] == eid)
        unit = byid[eid + "::" + owner]
        lo, hi = unit["whole"]
        ts = source.index(trigger, lo, hi)
        rs = source.index(target, ts + len(trigger), hi)
        if target.lower().startswith(("section ", "sections ", "clause ", "clauses ")):
            prefix, target = target.split(" ", 1)
            rs += len(prefix) + 1
        resolved_id = eid + "::" + resolved if resolved else None
        expected_refs.append(dict(owner_id=unit["id"], trigger_literal=trigger,
                                  trigger=[ts, ts + len(trigger)],
                                  target_literal=target, target=[rs, rs + len(target)],
                                  resolved_target_id=resolved_id, status=status))
        if resolved_id:
            edges.add((unit["id"], resolved_id))
    inp = dict(id=f"e24-raw-{number:02}", query=query, excerpts=src,
               seed_limit=1, budget=budget or dict(max_nodes=32, max_utf8_bytes=8192))
    gold = dict(id=inp["id"], coverage=coverage, units=units,
                references=expected_refs, edges=[list(x) for x in sorted(edges)],
                unknown_codes=list(unknown_codes), cycle_components=[sorted(x) for x in cycles],
                parser_budget_exceeded=parser_budget)
    return inp, gold


def build():
    cases = []
    def add(n, blocks, query, **kwargs):
        cases.append(case(n, [excerpt("x", blocks)], query, **kwargs))

    add(1, [block("1", "1.", "The permitted uses of the copper register are:"),
            block("1(a)", "(a)", "An archivist may count the cobalt seals.", "1"),
            block("1(b)", "(b)", "A courier may inspect the amber hinges.", "1")],
        "May an archivist count the cobalt seals?", coverage="colon heading and lettered applicability")
    add(2, [block("2", "2)", "Transport conditions."),
            block("2.4", "2.4", "The silver crate remains in the east room.", "2"),
            block("2.4.7", "2.4.7", "The violet latch stays closed for 19 days.", "2.4")],
        "How long does the violet latch stay closed?", coverage="numeric dotted transitive hierarchy")
    add(3, [block("1", "1.", "Storage exceptions.\nSubject to Section 2:"),
            block("1(a)", "(a)", "The jade spool may leave the cabinet.", "1"),
            block("2", "2.", "A custodian must sign the vermilion ledger.")],
        "Can the jade spool leave the cabinet?",
        refs=[("x", "1", "Subject to", "Section 2", "2", "resolved")],
        coverage="reference in inherited colon heading closes through parent")
    add(4, [block("1", "Section 1.", "The sapphire parcel remains sealed.\r\n  Subject to Clause 2, only the named keeper may move it.", ending="\r\n"),
            block("2", "2)", "The keeper must record the ivory timestamp.", ending="\r\n")],
        "Who may move the sapphire parcel?",
        refs=[("x", "1", "Subject to", "Clause 2", "2", "resolved")],
        coverage="CRLF continuation reference and optional Section marker")
    add(5, [block("1", "1.", "The ferryman signs the teal receipt."),
            block("2", "2.", "Subject to Section 1, the ochre chest may travel.")],
        "May the ochre chest travel?", refs=[("x", "2", "Subject to", "Section 1", "1", "resolved")],
        coverage="backward explicit reference")
    add(6, [block("1", "1.", "Subject to Section 3, the garnet valve may open."),
            block("2", "2.", "The moonstone tray stays level."),
            block("3", "3.", "The inspector must stamp the cerulean ticket.")],
        "May the garnet valve open?", refs=[("x", "1", "Subject to", "Section 3", "3", "resolved")],
        coverage="forward explicit reference")
    add(7, [block("1", "1.", "The linen packet must remain dry."),
            block("2", "2.", "Except as provided in Section 1, the umber ribbon may be washed.")],
        "May the umber ribbon be washed?", refs=[("x", "2", "Except as provided in", "Section 1", "1", "resolved")],
        coverage="provided-in exception trigger")
    add(8, [block("1", "1.", "The warden must retain the mauve token."),
            block("2", "2.", "Except as set forth in Clause 1, the vermilion bell may be loaned.")],
        "May the vermilion bell be loaned?", refs=[("x", "2", "Except as set forth in", "Clause 1", "1", "resolved")],
        coverage="set-forth-in exception trigger")
    add(9, [block("1", "1.", "The keeper verifies the beryl serial."),
            block("2", "2.", "The apricot carton may depart, provided that the requirements of Section 1 are met.")],
        "May the apricot carton depart?", refs=[("x", "2", "provided that the requirements of", "Section 1", "1", "resolved")],
        coverage="provided-that condition trigger")
    add(10, [block("1", "1.", "The curator files the indigo voucher."),
             block("2", "2.", "The coral key may be copied on condition that the requirements of Clause 1 are met.")],
        "May the coral key be copied?", refs=[("x", "2", "on condition that the requirements of", "Clause 1", "1", "resolved")],
        coverage="on-condition trigger")
    add(11, [block("1", "1.", "The agent counts the pewter pins."),
             block("2", "2.", "The agent weighs the cinnabar dust."),
             block("3", "3.", "Subject to Sections 1 and 2, the topaz box may be released.")],
        "May the topaz box be released?",
        refs=[("x", "3", "Subject to", "Sections 1", "1", "resolved"),
              ("x", "3", "Subject to", "2", "2", "resolved")],
        coverage="full explicit target list")
    add(12, [block("4", "4.", "Disposal conditions are:"),
             block("4(a)", "(a)", "The keeper stamps the ultramarine docket.", "4"),
             block("4(b)", "(b)", "Subject to (a), the marigold reel may be discarded.", "4")],
        "May the marigold reel be discarded?", refs=[("x", "4(b)", "Subject to", "(a)", "4(a)", "resolved")],
        coverage="same-parent relative reference")
    add(13, [block("6", "6.", "Subject to Section 6, the peridot seal remains valid.")],
        "Does the peridot seal remain valid?", refs=[("x", "6", "Subject to", "Section 6", "6", "resolved")],
        cycles=[["x::6"]], coverage="explicit self cycle")
    add(14, [block("7", "7.", "Subject to Section 8, the obsidian tray may rotate."),
             block("8", "8.", "Subject to Section 7, the tourmaline brace may bend.")],
        "May the obsidian tray rotate?",
        refs=[("x", "7", "Subject to", "Section 8", "8", "resolved"),
              ("x", "8", "Subject to", "Section 7", "7", "resolved")],
        cycles=[["x::7", "x::8"]], coverage="two-clause cycle retained deterministically")
    a = excerpt("north", [block("1", "1.", "The north keeper retains the jasper bead."),
                           block("2", "2.", "Subject to Section 1, the north nickel ring may leave.")])
    b = excerpt("south", [block("1", "1.", "The south keeper retains the opal bead."),
                           block("2", "2.", "Subject to Section 1, the south bronze ring may leave.")])
    cases.append(case(15, [a, b], "May the south bronze ring leave?",
                      refs=[("north", "2", "Subject to", "Section 1", "1", "resolved"),
                            ("south", "2", "Subject to", "Section 1", "1", "resolved")],
                      coverage="excerpt-local labels and reference isolation"))
    add(16, [block("9", "section 9)", "Le dépôt coûte 37€; le jeton porte Ω et 🧭.", indent="  "),
             block("9.2", "9.2", "Subject to Clause 9, the café archive stays open for 11 days.", "9", indent="\t")],
        "How long does the café archive stay open?", refs=[("x", "9.2", "Subject to", "Clause 9", "9", "resolved")],
        coverage="Unicode codepoints, byte mapping, indentation and section case")
    add(17, [block("5", "5.", "Dispatch exceptions are:"),
             block("5(a)", "(a)", "The chartreuse lever may be pulled.", "5")],
        "May the chartreuse lever be pulled?", budget=dict(max_nodes=1, max_utf8_bytes=8192),
        coverage="atomic dependency overflow must be incomplete unknown")

    src = dict(id="x", text="q" * 65537)
    cases.append(case(18, [(src, [])], "Is the source structurally admitted?", parser_budget=True,
                      unknown_codes=["budget_exceeded"], coverage="raw-source byte admission limit"))
    add(19, [block("1", "1.", "Subject to Section 44, the aquamarine gate may open.")],
        "May the aquamarine gate open?", refs=[("x", "1", "Subject to", "Section 44", None, "unresolved_reference")],
        unknown_codes=["unresolved_reference"], coverage="missing explicit target")
    add(20, [block("1", "1.", "The first keeper counts the ash pins."),
             block("1", "1.", "The second keeper counts the elm pins."),
             block("2", "2.", "Subject to Section 1, the willow spool may be lent.")],
        "May the willow spool be lent?", refs=[("x", "2", "Subject to", "Section 1", None, "ambiguous_reference")],
        unknown_codes=["ambiguous_scope", "ambiguous_reference"], coverage="duplicate canonical target cannot choose first")
    add(21, [block("1", "1.", "Subject to Sections 2-4, the russet sleeve may be cut."),
             block("2", "2.", "The smaller keeper holds the shell."),
             block("3", "3.", "The taller keeper holds the cord."),
             block("4", "4.", "The oldest keeper holds the stamp.")],
        "May the russet sleeve be cut?", unknown_codes=["unsupported_reference_syntax"],
        coverage="unsupported numeric range cannot resolve first target only")
    add(22, [block("1", "1.", "Subject to the foregoing, the tangerine handle may turn.")],
        "May the tangerine handle turn?", unknown_codes=["unsupported_reference_syntax"],
        coverage="unsupported deictic target cannot infer antecedent")
    src = dict(id="x", text="(ii) The celadon disk must remain flat.\n")
    cases.append(case(23, [(src, [])], "Must the celadon disk remain flat?",
                      unknown_codes=["unsupported_marker_syntax", "no_supported_units"], coverage="unambiguous unsupported Roman marker"))
    add(24, [block("12.3", "12.3", "The magenta sleeve must remain intact.")],
        "Must the magenta sleeve remain intact?", unknown_codes=["ambiguous_scope"],
        coverage="dotted child without earlier numeric parent")
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    pairs = build()
    for name, data in [("engineering-inputs.json", dict(schema_version=1, epoch=24,
                         contract_sha256=hashlib.sha256(args.contract.read_bytes()).hexdigest(),
                         authorship="Independent audit agent; all24rawtexts newly authored without candidate parser/model execution.",
                         scope="Unseen authored structural engineering only; not benchmark confirmation or synthetic generalization.",
                         license="CC0-1.0", cases=[x[0] for x in pairs])),
                       ("manual-gold.json", dict(schema_version=1, epoch=24,
                         author="independent_audit", annotation_method="manual authored blocks and explicit edges; no candidate parser execution",
                         cases=[x[1] for x in pairs]))]:
        path = ROOT / name
        with path.open("x") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(name, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
