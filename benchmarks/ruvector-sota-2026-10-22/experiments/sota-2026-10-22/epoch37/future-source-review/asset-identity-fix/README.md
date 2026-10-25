Future source review only. This patch is not applied, and it authorizes no E37 retry.

E37 stopped before worker reservation because its asset guard used the observed materialization lock as the reviewed source declaration. That removed the Git LFS representation discriminator. The guard compared the complete SentencePiece payload's Git hash with the hash of its upstream LFS pointer.

The proposed repair restores the separately pinned historical source declaration and admits exactly one explicit identity type per asset. Ordinary Git bodies require payload SHA256 and Git SHA1. LFS assets require the declared payload SHA256/size and the independently checked upstream pointer identity; a pointer hash is never compared to the payload's Git hash. An observed `sha256` field cannot substitute for either source declaration type.

Eighteen small unit tests pass. The exact historical five-file source declaration and actual E37 materialization metadata also pass the pure terminal identity policy. The real SPM payload Git hash comes from the retained independent observation report. No model/tokenizer/native execution, model weight read, current frozen guard invocation, case parse, network call or new dispatch occurred during this repair work.

The integration patch deliberately names `FUTURE_EPOCH`. A future root must choose a new epoch and its source catalog, helper, wrappers, dispatcher hash, runtime/resource plan and exact source publication/readback. The frozen E37 source and failed dispatch remain unchanged.
