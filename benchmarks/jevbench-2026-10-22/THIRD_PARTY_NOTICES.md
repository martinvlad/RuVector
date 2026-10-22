# Source and license notices

This directory preserves measured source bytes and upstream notices. It does not
relicense third-party benchmark data, code, models, or the native package.

* JevBench: Florian Standhartinger and contributors, MIT. The exact notice is
  [data/jevbench/LICENSE](data/jevbench/LICENSE). It applies to the copied public
  original/hard task snapshot and the byte-identical task/scorer/adapter helpers.
  Official helper source is pinned to
  https://github.com/fstandhartinger/jevbench/tree/609a664e81f46e03731600bd7bd9f1b7a61257c5 .
  PROVENANCE.json records individual source URLs and exact hashes. The task files
  are an older public183 snapshot, not a current release or sealed evaluation.
* `@ruvector/typesafe@0.2.0`: package-declared MIT, source
  https://github.com/ruvnet/ruvector/tree/main/npm/packages/typesafe .
  package-lock.json pins the immutable npm version, registry tarball, and integrity.
  Its binaries and installed node_modules are not distributed in this source kit.
* BGE-small-en-v1.5: the BAAI base model declares MIT at the pinned model metadata
  revision in assets.lock.json. Source: https://huggingface.co/BAAI/bge-small-en-v1.5 .
  The measured ONNX conversion and tokenizer come from
  https://huggingface.co/Xenova/bge-small-en-v1.5/tree/ea104dacec62c0de699686887e3f920caeb4f3e3 .
  assets.lock.json pins exact model/tokenizer SHA256, byte lengths, and acquisition
  URLs. No model weights or tokenizer asset bytes are included in this source kit.
* RuVector-owned adapter/solver/packaging contributions retain the destination
  RuVector repository's existing license. Existing source files are unmodified;
  this notice makes no new claim of third-party authorship or relicensing.
