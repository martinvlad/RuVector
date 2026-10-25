// Exception-only failure metadata publisher. Defines functions; root invokes
// publishBlocked only after independent stage review. No model/scorer work.
const blockedPublisherTupleKeys = ["path", "mode", "type", "sha", "size"];
const blockedPublisherCanonical = x => {
  if (Array.isArray(x)) return x.map(blockedPublisherCanonical);
  if (x && typeof x === "object") return Object.fromEntries(Object.keys(x).sort().map(k => [k, blockedPublisherCanonical(x[k])]));
  return x;
};
const blockedPublisherSame = (a, b) => JSON.stringify(blockedPublisherCanonical(a)) === JSON.stringify(blockedPublisherCanonical(b));
const blockedPublisherRelative = value => typeof value === "string" && value && !value.startsWith("/") && !value.includes("\\") && !value.split("/").some(p => ["", ".", ".."].includes(p));
const blockedPublisherMap = doc => {
  if (!doc || doc.scope !== "benchmarks/ruvector-sota-2026-10-22/" || !Array.isArray(doc.files)) throw Error("canonical expected scope/file map required");
  const answer = new Map();
  for (const row of doc.files) {
    if (!blockedPublisherRelative(row.path) || row.mode !== "100644" || row.type !== "blob" || !/^[0-9a-f]{40}$/.test(row.sha) || !Number.isSafeInteger(row.size) || row.size < 0 || answer.has(row.path)) throw Error("invalid/duplicate expected tuple");
    answer.set(row.path, Object.fromEntries(blockedPublisherTupleKeys.map(k => [k, row[k]])));
  }
  return answer;
};
const blockedPublisherCheckLeaves = (tree, expected) => {
  if (tree.truncated || !Array.isArray(tree.tree)) throw Error("truncated/missing actual tree");
  const files = tree.tree.filter(x => x.type !== "tree");
  if (files.length !== expected.size) throw Error("actual leaf count differs");
  const seen = new Set();
  for (const row of files) {
    if (seen.has(row.path)) throw Error("duplicate actual path");
    seen.add(row.path);
    const wanted = expected.get(row.path);
    if (!wanted || blockedPublisherTupleKeys.some(k => row[k] !== wanted[k])) throw Error("actual tuple differs: " + row.path);
  }
  return files.length;
};
const blockedPublisherCheckSiblings = (tree, baseline, changed, replacement) => {
  if (tree.truncated || tree.tree.length !== baseline.tree.length) throw Error("root/bench sibling count drift");
  for (const row of baseline.tree) {
    const actual = tree.tree.find(x => x.path === row.path);
    if (!actual || actual.mode !== row.mode || actual.type !== row.type || actual.sha !== (row.path === changed ? replacement : row.sha)) throw Error("sibling drift: " + row.path);
  }
};
const blockedPublisherMutate = async (id, tool, args) => {
  const permitted = new Set(["mcp__codex_apps__github_create_blob", "mcp__codex_apps__github_create_tree", "mcp__codex_apps__github_create_commit", "mcp__codex_apps__github_update_ref"]);
  if (!permitted.has(tool) || args.repository_full_name !== "ruvnet/RuVector") throw Error("unapproved publication mutation");
  const forbiddenMain = value => typeof value === "string" ? ["main", "heads/main", "refs/heads/main"].includes(value) : Array.isArray(value) ? value.some(forbiddenMain) : value && typeof value === "object" ? Object.values(value).some(forbiddenMain) : false;
  if (forbiddenMain(args)) throw Error("main is prohibited in mutation arguments");
  if (tool.endsWith("github_update_ref") && (args.branch_name !== "benchmarks/ruvector-sota-2026-10-22" || args.force !== false || !/^[0-9a-f]{40}$/.test(args.expected_sha) || !/^[0-9a-f]{40}$/.test(args.sha))) throw Error("dedicated branch compare-and-set required");
  return await mutate(id, tool, args);
};
const publishBlocked = async (proofPath) => {
  const phase = "blocked";
  if (S !== "/tmp/ruvector-sota-2026-10-22/epoch37-b4e9e4f7a8a4" || repo !== "ruvnet/RuVector" || branch !== "benchmarks/ruvector-sota-2026-10-22") throw Error("wrong exact isolated blockedPublisher scope");
  const prefix = "https://api.github.com/repos/" + repo;
  const scoped = "benchmarks/ruvector-sota-2026-10-22/";
  const planPath = S + "/project/experiments/sota-2026-10-22/epoch37/plan.json";
  const plan = await read(planPath);
  const planPin = await readRequestMeta(planPath);
  if (plan.epoch !== 37 || plan.kind !== "ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES" || plan.source_checkpoint !== "b4e9e4f7a8a40b95b87ed8e418435b2d5757bb0e") throw Error("wrong frozen engineering-only plan");
  const stage = S + "/stage-blocked";
  if (typeof stage !== "string" || !stage.startsWith("/") || stage.includes("/../") || stage.includes("\\")) throw Error("wrong frozen publication stage path");
  const metaPin = await readRequestMeta(stage + "/metadata.json");
  const proof = await read(proofPath);
  if (proof.checks_passed !== true || proof.stage !== stage || proof.manifest_sha256 !== metaPin.sha256 || proof.manifest_bytes !== metaPin.bytes) throw Error("independent stage proof mismatch");
  const meta = await read(stage + "/metadata.json");
  const guards = meta.CAS_guards;
  if (meta.source_plan_sha256 !== planPin.sha256 || meta.stage !== phase || meta.scope !== scoped || guards.force !== false || guards.expected_branch_sha !== meta.publication_parent || !/^[0-9a-f]{40}$/.test(meta.read_only_main_observation) || "expected_main" in guards) throw Error("stage/parent/main/CAS guard mismatch");
  if (meta.publication_parent !== "a93a1d6922c8a14f356461fb383846157816c70b" || meta.status !== "EXCEPTIONAL_BLOCKED_CHECKPOINT" || guards.expected_root_tree !== "fe62b7d381fc04f6f05957101011c120801c5d10" || guards.expected_benchmarks_tree !== "632da9246ed32e46164c7e3cd46607e3f27f93b9" || guards.expected_scope_tree !== "dae1d90376557c0a6a1bb71fb912ada288a5e230") throw Error("exceptional metadata must extend exact actual SOURCE");
  const manifestPath = S + "/project/" + meta.exceptional_manifest.path;
  const manifestPin = await readRequestMeta(manifestPath);
  const manifest = await read(manifestPath);
  if (manifestPin.sha256 !== meta.exceptional_manifest.sha256 || manifestPin.bytes !== meta.exceptional_manifest.bytes || manifest.status !== "EXCEPTIONAL_BLOCKED_CHECKPOINT" || manifest.scientific_status !== "REJECTED_ENGINEERING_INTEGRITY" || manifest.evaluated_integrity_checks_passed !== false || manifest.engineering_passed !== false || manifest.all_slots_closed !== true || manifest.used_confirmation_identities?.length !== 0 || Object.values(manifest.phase_remaining || {}).some(x => x !== 0) || manifest.benchmark_accuracy !== null || ["benchmark_accepted","champion_promoted","new_submission","official_SOTA_verified"].some(k => manifest[k] !== false)) throw Error("no accepted scientific result or open slot in blocked checkpoint");
  const expectedPin = await readRequestMeta(stage + "/" + meta.expected_leaves.file);
  if (meta.expected_leaves.file !== "expected-leaves.json" || expectedPin.bytes !== meta.expected_leaves.bytes || expectedPin.sha256 !== meta.expected_leaves.sha256) throw Error("staged expected tree identity differs");
  const expected = blockedPublisherMap(await read(stage + "/expected-leaves.json"));
  if (expected.size !== meta.expected_Git_leaves || expected.size !== meta.expected_leaves.count) throw Error("staged expected count mismatch");
  const head = await get(prefix + "/git/ref/heads/" + branch);
  const main = await get(prefix + "/git/ref/heads/main");
  if (head.object.sha !== meta.publication_parent) throw Error("actual dedicated branch changed");
  if (!/^[0-9a-f]{40}$/.test(main.object.sha)) throw Error("malformed read-only main observation");
  const priorDir = meta.prior_controls_name;
  const allowedPrior = ["controls-source"];
  if (!allowedPrior.includes(priorDir)) throw Error("wrong canonical prior controls for phase");
  const priorActive = await read(S + "/" + priorDir + "/ACTIVE_RUN.json");
  const priorCont = await read(S + "/" + priorDir + "/CONTINUATION.json");
  const activeRemote = await get("https://raw.githubusercontent.com/" + repo + "/" + meta.publication_parent + "/" + scoped + "ACTIVE_RUN.json");
  const contRemote = await get("https://raw.githubusercontent.com/" + repo + "/" + meta.publication_parent + "/" + scoped + "CONTINUATION.json");
  if (!blockedPublisherSame(activeRemote, priorActive) || !blockedPublisherSame(contRemote, priorCont) || priorActive.run_id !== "epoch37-b4e9e4f7a8a4" || priorActive.work_active !== true || priorActive.native_allowed !== 0) throw Error("exact owned scoped remote lease required");
  const parent = await get(prefix + "/git/commits/" + meta.publication_parent);
  if (parent.tree.sha !== guards.expected_root_tree) throw Error("actual parent root changed");
  const parentRoot = await get(prefix + "/git/trees/" + parent.tree.sha);
  const parentBenchSha = parentRoot.tree.find(x => x.path === "benchmarks")?.sha;
  if (parentBenchSha !== guards.expected_benchmarks_tree) throw Error("actual parent bench changed");
  const parentBench = await get(prefix + "/git/trees/" + parentBenchSha);
  if (parentBench.tree.find(x => x.path === "ruvector-sota-2026-10-22")?.sha !== guards.expected_scope_tree) throw Error("actual parent scope changed");
  // Read both immutable sibling baselines before ANY object mutation. Missing
  // baselines cannot strand a source publication after a sequence of writes.
  const baselineRoot = await read(S + "/baseline-0.json");
  const baselineBench = await read(S + "/baseline-1.json");
  blockedPublisherCheckSiblings(parentRoot, baselineRoot, "benchmarks", parentBenchSha);
  blockedPublisherCheckSiblings(parentBench, baselineBench, "ruvector-sota-2026-10-22", guards.expected_scope_tree);
  for (let i = 0; i < meta.large_blob_requests.length; i++) {
    const row = meta.large_blob_requests[i];
    if (!blockedPublisherRelative(row.file) || !row.file.startsWith("transport/")) throw Error("unsafe blob request path");
    const pin = await readRequestMeta(stage + "/" + row.file);
    if (pin.bytes !== row.bytes || pin.sha256 !== row.sha256 || pin.bytes >= 8384512) throw Error("blob request drift/cap");
    const args = await read(stage + "/" + row.file);
    const blob = await blockedPublisherMutate("e37-exceptional-blocked-v1-" + "-blob-" + i, "mcp__codex_apps__github_create_blob", {repository_full_name: repo, ...args});
    if (blob.sha !== row.expected_blob_sha1) throw Error("actual created blob differs");
  }
  let root = guards.expected_root_tree;
  for (let i = 0; i < meta.create_tree_groups.length; i++) {
    const row = meta.create_tree_groups[i];
    if (!blockedPublisherRelative(row.file) || !row.file.startsWith("transport/")) throw Error("unsafe tree request path");
    const pin = await readRequestMeta(stage + "/" + row.file);
    if (pin.bytes !== row.bytes || pin.sha256 !== row.sha256 || pin.bytes >= 175904) throw Error("tree request drift/cap");
    const args = await read(stage + "/" + row.file);
    if (args.tree_elements.some(e => !e.path.startsWith(scoped) || !blockedPublisherRelative(e.path) || e.mode !== "100644" || e.type !== "blob")) throw Error("mutation scope escape");
    const created = await blockedPublisherMutate("e37-exceptional-blocked-v1-" + "-tree-" + i, "mcp__codex_apps__github_create_tree", {repository_full_name: repo, base_tree_sha: root, ...args});
    root = created.sha;
  }
  const rtree = await get(prefix + "/git/trees/" + root);
  const bench = rtree.tree.find(x => x.path === "benchmarks")?.sha;
  const btree = await get(prefix + "/git/trees/" + bench);
  const scope = btree.tree.find(x => x.path === "ruvector-sota-2026-10-22")?.sha;
  blockedPublisherCheckSiblings(rtree, baselineRoot, "benchmarks", bench);
  blockedPublisherCheckSiblings(btree, baselineBench, "ruvector-sota-2026-10-22", scope);
  const leaves = blockedPublisherCheckLeaves(await get(prefix + "/git/trees/" + scope + "?recursive=1"), expected);
  const before = await get(prefix + "/git/ref/heads/" + branch);
  const mainBefore = await get(prefix + "/git/ref/heads/main");
  if (before.object.sha !== meta.publication_parent) throw Error("late actual dedicated branch changed");
  if (!/^[0-9a-f]{40}$/.test(mainBefore.object.sha)) throw Error("malformed late main observation");
  const commit = await blockedPublisherMutate("e37-exceptional-blocked-v1-" + "-commit", "mcp__codex_apps__github_create_commit", {repository_full_name: repo, parent_sha: meta.publication_parent, tree_sha: root, message: "benchmarks: preserve epoch37 preworker integrity failure and exceptional blocked closure; no benchmark score"});
  const actualCommit = await get(prefix + "/git/commits/" + commit.sha);
  if (actualCommit.parents.length !== 1 || actualCommit.parents[0].sha !== meta.publication_parent || actualCommit.tree.sha !== root) throw Error("created commit identity differs");
  await blockedPublisherMutate("e37-exceptional-blocked-v1-" + "-ref", "mcp__codex_apps__github_update_ref", {repository_full_name: repo, branch_name: branch, expected_sha: meta.publication_parent, force: false, sha: commit.sha});
  const after = await get(prefix + "/git/ref/heads/" + branch);
  if (after.object.sha !== commit.sha) throw Error("actual post-update ref differs; stop");
  const mainAfter = await get(prefix + "/git/ref/heads/main");
  if (!/^[0-9a-f]{40}$/.test(mainAfter.object.sha)) throw Error("malformed post-publication main observation");
  return {read_only_main_observations: {staged: meta.read_only_main_observation, before: main.object.sha, before_ref_update: mainBefore.object.sha, after: mainAfter.object.sha}, phase, commit: commit.sha, root, bench, scope, parent: meta.publication_parent, leaves, verified_actual_full_tree: true, stage_metadata_sha256: metaPin.sha256, expected_leaves_sha256: expectedPin.sha256};
};
