# License and attribution notes

New replay/extraction code is supplied under the destination RuVector
repository's applicable license. Original author metric sources in `upstream/`
retain the included MIT license, copyright2025 ZeroEntropy. Their exact source
revision and file hashes are bound in the extraction provenance and older audit
proofs; the fresh upstream license response is also preserved.

The pinned Hugging Face mirror card declares `license: other` and
`per-source-licenses`, rather than one license for the whole corpus. It reports:

| Component | Terms described by the pinned mirror card | Attribution |
|---|---|---|
| LegalBench-RAG questions/spans/construction | MIT | Nicholas Pipitone and Ghita Houir Alami(2024), arXiv2408.10343 |
| PrivacyQA | MIT | Ravichander et al.(2019), arXiv1911.00841 |
| ContractNLI | CC BY4.0 | Koreeda and Manning(2021), arXiv2110.01799 |
| CUADv1 | CC BY4.0 | Hendrycks et al.(2021), arXiv2103.06268; Zenodo4595826 |
| MAUD | Not stated/verified in the card's cited MAUD repository | Wang et al.(2023), arXiv2301.00876 |

These descriptions come from the pinned mirror card, not a new legal assessment.
The LegalBench-RAG authors ask users to accept each source dataset's usage
policies. Underlying contract/privacy-policy texts remain the property of their
owners. This replay kit omits all raw query, answer and corpus text and all
model weights/vectors. Reusing the full source data requires checking the
original terms, including unresolved MAUD terms; this metadata kit does not
grant additional rights.

Pinned card and source locations:

- https://huggingface.co/datasets/awinml/legalbench-rag/blob/2b9c248bc8179ef0908fd6ba01d50b156facd48b/README.md
- https://github.com/zeroentropy-ai/legalbenchrag/blob/431bc8f2488a81569ab7259fa633dcc50ab77f9a/legalbenchrag/run_benchmark.py
- https://github.com/zeroentropy-ai/legalbenchrag/blob/master/LICENSE
- https://arxiv.org/abs/2408.10343
- https://arxiv.org/abs/1911.00841
- https://arxiv.org/abs/2110.01799
- https://arxiv.org/abs/2103.06268
- https://arxiv.org/abs/2301.00876
