# RuVector Python package portfolio

Focused Python APIs backed by existing RuVector Rust libraries. Release candidates, not yet verified as published.

| Distribution | Import | Rust implementation | Task |
| :--- | :--- | :--- | :--- |
| ruvector | ruvector | ruvector-core, ruvector-rabitq | Vector search, collection API, CLI and MCP |
| ruvector-graph | ruvector_graph | ruvector-graph | Property graphs and bounded traversal |
| ruvector-cluster | ruvector_cluster | ruvector-cluster-rag | Embedding clustering and cohesion |
| ruvector-rerank | ruvector_rerank | ruvector-attention | Attention weights and candidate ordering |

All three new distributions depend on the same exact native runtime, `ruvector==0.1.2`. Installing all three installs that runtime once. They add useful APIs rather than duplicating Rust binaries. They do not reduce native download size. KGE, quantization and independent native wheels remain future work, not claimed features.

## Build and test

```bash
python -m pip install build maturin pytest numpy twine
maturin build --manifest-path crates/ruvector-py/Cargo.toml --out /tmp/native
python -m pip install /tmp/native/*.whl
for package in python/portfolio/ruvector-*; do
  python -m build "$package"
  python -m pip install "$package"/dist/*.whl
done
python -m pytest python/portfolio/tests -q
```

## Automatic publishing

The `python-portfolio-v0.1.0` tag builds and tests all packages, audits dependencies and publishes the exact tested artifacts with PyPI OIDC attestations. No recurring task is required. PRs build and test but cannot publish. The release tag must point to a commit on main. Configure the `pypi` GitHub environment to accept only protected release tags.

Before the first release, register each package's PyPI Trusted Publisher with owner `ruvnet`, repository `RuVector`, workflow `python-portfolio.yml`, environment `pypi`. Confirm name ownership or availability on PyPI; a missing public project is not proof that its name is allocatable. Publish the required runtime version first. The release gate also tests against the published runtime wheel, avoiding accidental dependence on unreleased native APIs.

The native runtime keeps its existing `python-v*` wheel workflow. Portfolio packages share a version and release tag, but PyPI publication is not transactional: a partial upload requires checking receipts and publishing only the missing artifacts. Never overwrite releases or silently skip conflicting files.

## Search discovery

Each package includes a descriptive title, PyPI summary, keywords, repository/documentation links, explicit problem statement, installation command, executable example and limitations. Animated SVGs include accessible titles, descriptions and reduced motion support; static fallback content remains readable. Search rankings are not guaranteed. Prefer measured user adoption and successful installs over package count.
