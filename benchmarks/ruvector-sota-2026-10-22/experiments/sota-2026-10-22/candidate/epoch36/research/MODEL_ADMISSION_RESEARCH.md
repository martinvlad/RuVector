# E36 original XXLarge model source review

The new candidate is `microsoft/deberta-v2-xxlarge-mnli@8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06`, a distinct official 48-layer, approximately1.5B-parameter three-way MNLI checkpoint. Its original PyTorch payload is3,133,958,098bytes, expected SHA256`5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db`. No weight bytes were downloaded.

Architecture is materially larger, but superiority over b354 is unverified. The official matched dev table gives XXLarge91.7/91.9 and V3-Large91.8/91.9. Existing b35491.2/90.8 numbers are test results under a different protocol. None establish greater numerical or source-scope competency.

Model and official software declare MIT. Exact training-record, selection, calibration and foundation lineage and original production-code linkage remain incomplete. Benchmark confirmation, promotion and official eligibility remain HOLD.

The existing CPU runtime contains the relevant safe-loading APIs, but archive format, tensor dtype/count, measured memory and CPU2/600-second timing are unverified. The3.13GB payload cannot fit the current391MB free space without a reviewed cache/resource plan. A prospective source-only design uses safe original tensors, meta construction and strict assignment; unsupported formats must fail closed without unsafe-pickle or alternate-weight fallbacks.

Six metadata/source GETs succeeded, with no redirects/retries, ML imports, tokenization, native execution, weight download, new benchmark or confirmation labels, paid calls, GPU calls, contacts or external mutations. This report admits metadata only. Any future engineering comparison must be separately frozen and cannot be called benchmark generalization or native retrieval gain when contexts are identical.
