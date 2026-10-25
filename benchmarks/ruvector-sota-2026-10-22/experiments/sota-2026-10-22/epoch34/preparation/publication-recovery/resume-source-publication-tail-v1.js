// Outside-project SOURCE recovery: definitions only. Never invoke publishPhase.
// The coordinator loads the exact root controller, frozen publisher, then this
// helper and explicitly invokes resumeSourcePublicationTail() after approval.
const sourceTailConfig = Object.freeze({
  workspace: "/workspace/ruvector-epoch34-047dbc740dc2",
  helper: "/workspace/ruvector-e34-publication-impl/resume-source-publication-tail-v1.js",
  validator: "/workspace/ruvector-e34-publication-impl/verify-source-publication-tail-inputs-v1.py",
  validatorBytes: 16529,
  validatorSha256: "465e23f7770bbc805d588500b5dc6b5e2594ae2d332bb39a8955f30507ce166c",
  approval: "/workspace/ruvector-e34-independent-audit/source-publication-tail-independent-v1.json",
  parent: "eafd332309fef5873086cf66c911b1787c320820",
  parentRoot: "821b12fe6f0608aef0afe1dd77b27da3aa6f94b1",
  parentBench: "889dcddc771c8712f6210a2a40fa9cb3df20a02d",
  parentScope: "f229146613b61b3ca6b38cf8356d428efcf02802",
  createdRoot: "e8093d1ac7cf51182f7e74cd15bca110b2cd65a1",
  createdBench: "bc3e85292fb9397791f3185ee532002bbea37efc",
  createdScope: "ef33a23a99eafea16a3526ab6de2065db398b4f6",
  commitMessage: "benchmarks: freeze epoch34 lexical-anchor native-complement NLI source and engineering-gated DEV roles",
  controllerSha256: "9837cf7e16c5210af1a8a8b0ade1d89e2c1dadb767b042a3464ca949fa42f7b3",
  publisherSha256: "d3d75b8b90acec78258291a2ef6d78dbc3b79291ea7a6c2896c87fe996277ead",
  metadataSha256: "d5b92f29be2f18e85ccff3001e0364d587dde0d0caa177f4743b21c34e7ad9a3",
  leavesSha256: "bc8e6a5bfd60cc1eea92ced7fe8508f692117dfd6455c9335bece7f658859632",
  stageProofSha256: "42ede904e8f7ad49e64b8223725b13f4889d867d34f87e4ac262e44baa34cd63"
});
let sourceTailInvocationStarted = false;
const sourceTailRequire = (ok, message) => { if (!ok) throw Error(message); };
const sourceTailCanonical = value => Array.isArray(value) ? value.map(sourceTailCanonical) : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map(k => [k, sourceTailCanonical(value[k])])) : value;
const sourceTailSame = (left, right) => JSON.stringify(sourceTailCanonical(left)) === JSON.stringify(sourceTailCanonical(right));

const sourceTailCheckMutation = (step, id, tool, args, committedSha) => {
  const c = sourceTailConfig;
  if (step === 0) {
    sourceTailRequire(id === "e34-source-commit" && tool === "mcp__codex_apps__github_create_commit" && sourceTailSame(args, {
      repository_full_name: "ruvnet/RuVector", parent_sha: c.parent, tree_sha: c.createdRoot, message: c.commitMessage
    }), "Only the unused exact SOURCE commit mutation is permitted first");
  } else if (step === 1) {
    sourceTailRequire(typeof committedSha === "string" && /^[0-9a-f]{40}$/.test(committedSha), "Known verified created commit required before CAS");
    sourceTailRequire(id === "e34-source-ref" && tool === "mcp__codex_apps__github_update_ref" && sourceTailSame(args, {
      repository_full_name: "ruvnet/RuVector", branch_name: "benchmarks/ruvector-sota-2026-10-22", expected_sha: c.parent, force: false, sha: committedSha
    }), "Only the unused exact nonforce SOURCE ref CAS is permitted second");
  } else throw Error("No third tail mutation, object upload, or publisher replay is permitted");
};

const sourceTailPersistNew = async (path, value) => {
  const permitted = [S + "/publication-source.json", S + "/source-publication-tail-execution-v1.json"];
  sourceTailRequire(permitted.includes(path), "Tail receipt path outside the fixed publication scope");
  const code = "from pathlib import Path\nimport os,json,hashlib\nTARGET_PATH = " + JSON.stringify(path) + "\nBODY_TEXT = " + JSON.stringify(JSON.stringify(value) + "\n") + "\np=Path(TARGET_PATH)\nassert p==p.resolve() and not any(x.is_symlink() for x in (p,*p.parents)) and not os.path.lexists(p)\nwith p.open('x') as f:\n f.write(BODY_TEXT);f.flush();os.fsync(f.fileno())\nd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)\nb=p.read_bytes();print(json.dumps(dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())))";
  return JSON.parse(await sh("python3 -c " + q(code)));
};

const resumeSourcePublicationTail = async () => {
  const c = sourceTailConfig;
  sourceTailRequire(!sourceTailInvocationStarted, "Tail already invoked in this controller; stop");
  sourceTailInvocationStarted = true;
  sourceTailRequire(S === c.workspace && repo === "ruvnet/RuVector" && branch === "benchmarks/ruvector-sota-2026-10-22", "Exact owned SOURCE controller scope required");
  const stage = S + "/stage-source";
  const publisherPath = S + "/project/experiments/sota-2026-10-22/epoch34/preparation/reviewed_publish_phase.js";
  let intent = null, committedSha = null, publication = null, publicationReceipt = null;
  const events = [];
  try {
    const approval = await read(c.approval), helperPin = await readRequestMeta(c.helper), validatorPin = await readRequestMeta(c.validator);
    sourceTailRequire(approval.checks_passed === true && sourceTailSame(approval.helper, helperPin) && sourceTailSame(approval.local_validator, validatorPin), "Hash-bound independent tail source approval required");
    sourceTailRequire(validatorPin.bytes === c.validatorBytes && validatorPin.sha256 === c.validatorSha256, "Reviewed local validator changed");
    const controllerPin = await readRequestMeta(S + "/controller.js"), publisherPin = await readRequestMeta(publisherPath);
    sourceTailRequire(controllerPin.bytes === 3571 && controllerPin.sha256 === c.controllerSha256 && publisherPin.bytes === 12009 && publisherPin.sha256 === c.publisherSha256, "Frozen controller/publisher definitions changed");
    const controllerText = await readText(S + "/controller.js"), publisherText = await readText(publisherPath);
    const mutateStart = controllerText.indexOf("const mutate="), mutateEnd = controllerText.indexOf("; const readRequestMeta=", mutateStart);
    sourceTailRequire(mutateStart >= 0 && mutateEnd > mutateStart && Function.prototype.toString.call(mutate) === controllerText.slice(mutateStart + "const mutate=".length, mutateEnd), "Loaded root mutation controller is not the exact reviewed function");
    const reference = new Function("mutate", publisherText + "\nreturn {publisherTupleKeys,publisherCanonical,publisherSame,publisherRelative,publisherMap,publisherCheckLeaves,publisherCheckSiblings,publisherMutate};")(async () => { throw Error("Reference definitions may never mutate"); });
    const loaded = {publisherCanonical,publisherSame,publisherRelative,publisherMap,publisherCheckLeaves,publisherCheckSiblings,publisherMutate};
    sourceTailRequire(sourceTailSame(publisherTupleKeys, reference.publisherTupleKeys), "Loaded frozen tuple keys changed");
    for (const [name, value] of Object.entries(loaded)) sourceTailRequire(Function.prototype.toString.call(value) === Function.prototype.toString.call(reference[name]), "Loaded frozen publisher helper changed: " + name);
    const preflight = JSON.parse(await sh("python3 -B " + q(c.validator) + " preflight"));
    sourceTailRequire(preflight.checks_passed === true && preflight.parent === c.parent && preflight.expected_Git_leaves === 5096 && preflight.all195source_pins_unchanged === true && preflight.CP_rows_verified === 5022 && preflight.WAL.WAL_rows === 40 && preflight.WAL.successful_pairs === 20 && preflight.WAL.uncertain_mutations === 0 && preflight.guardian.held === true, "Exact unused-tail preflight did not pass");
    const metadataPin = await readRequestMeta(stage + "/metadata.json"), leavesPin = await readRequestMeta(stage + "/expected-leaves.json"), proofPin = await readRequestMeta("/workspace/ruvector-e34-independent-audit/source-stage-independent-v1.json");
    sourceTailRequire(metadataPin.bytes === 64890 && metadataPin.sha256 === c.metadataSha256 && leavesPin.bytes === 914051 && leavesPin.sha256 === c.leavesSha256 && proofPin.bytes === 3211 && proofPin.sha256 === c.stageProofSha256, "Exact actual SOURCE stage/proof changed");
    const meta = await read(stage + "/metadata.json"), expected = publisherMap(await read(stage + "/expected-leaves.json"));
    sourceTailRequire(meta.stage === "source" && meta.publication_parent === c.parent && expected.size === 5096 && meta.large_blob_requests.length === 6 && meta.create_tree_groups.length === 10, "Wrong exact source stage/tail size");
    const prefix = "https://api.github.com/repos/" + repo;
    const head = await get(prefix + "/git/ref/heads/" + branch), mainBefore = await get(prefix + "/git/ref/heads/main");
    sourceTailRequire(head.object.sha === c.parent && /^[0-9a-f]{40}$/.test(mainBefore.object.sha), "Actual current branch changed or main observation malformed");
    const parent = await get(prefix + "/git/commits/" + c.parent);
    sourceTailRequire(parent.tree.sha === c.parentRoot && parent.parents.length === 1 && parent.parents[0].sha === "047dbc740dc2d4fdbdbad90ac167ebc64b31a49c", "Actual planning parent identity changed");
    const baselineRoot = await read(S + "/baseline-0.json"), baselineBench = await read(S + "/baseline-1.json");
    const parentRoot = await get(prefix + "/git/trees/" + c.parentRoot), parentBench = await get(prefix + "/git/trees/" + c.parentBench);
    publisherCheckSiblings(parentRoot, baselineRoot, "benchmarks", c.parentBench);
    publisherCheckSiblings(parentBench, baselineBench, "ruvector-sota-2026-10-22", c.parentScope);
    const createdRoot = await get(prefix + "/git/trees/" + c.createdRoot), createdBench = await get(prefix + "/git/trees/" + c.createdBench), createdScope = await get(prefix + "/git/trees/" + c.createdScope + "?recursive=1");
    sourceTailRequire(createdRoot.sha === c.createdRoot && createdBench.sha === c.createdBench && createdScope.sha === c.createdScope, "Actual created object identity changed");
    publisherCheckSiblings(createdRoot, baselineRoot, "benchmarks", c.createdBench);
    publisherCheckSiblings(createdBench, baselineBench, "ruvector-sota-2026-10-22", c.createdScope);
    const leaves = publisherCheckLeaves(createdScope, expected);
    sourceTailRequire(leaves === 5096, "Actual created full tuple count changed");
    const beforeTail = await get(prefix + "/git/ref/heads/" + branch), mainBeforeTail = await get(prefix + "/git/ref/heads/main");
    sourceTailRequire(beforeTail.object.sha === c.parent && /^[0-9a-f]{40}$/.test(mainBeforeTail.object.sha), "Late branch changed before unused commit/ref tail");
    const observations = {actual_parent_head:c.parent, created_trees:{root:c.createdRoot,bench:c.createdBench,scope:c.createdScope}, full_tuples_verified:leaves, read_only_main_before:mainBefore.object.sha, read_only_main_before_tail:mainBeforeTail.object.sha};
    const observation64 = (await sh("python3 -c " + q("import base64;print(base64.b64encode(" + JSON.stringify(JSON.stringify(observations)) + ".encode()).decode())"))).trim();
    intent = JSON.parse(await sh("python3 -B " + q(c.validator) + " intent --observations " + q(observation64)));
    sourceTailRequire(intent.intent && intent.preflight.checks_passed === true && intent.preflight.WAL.successful_pairs === 20, "Exclusive exact unused-tail intent missing");
    const tailMutation = async (id, tool, args) => {
      sourceTailCheckMutation(events.length, id, tool, args, committedSha);
      const event = {id,tool,args,call_started:true}; events.push(event);
      const result = await publisherMutate(id,tool,args);
      event.response = result; event.received_response = true;
      return result;
    };
    const commit = await tailMutation("e34-source-commit", "mcp__codex_apps__github_create_commit", {repository_full_name:repo,parent_sha:c.parent,tree_sha:c.createdRoot,message:c.commitMessage});
    sourceTailRequire(typeof commit.sha === "string" && /^[0-9a-f]{40}$/.test(commit.sha), "Created commit response has no exact identity; stop");
    committedSha = commit.sha;
    const actualCommit = await get(prefix + "/git/commits/" + committedSha);
    sourceTailRequire(actualCommit.parents.length === 1 && actualCommit.parents[0].sha === c.parent && actualCommit.tree.sha === c.createdRoot, "Actual created commit differs; stop before ref");
    const beforeRef = await get(prefix + "/git/ref/heads/" + branch), mainBeforeRef = await get(prefix + "/git/ref/heads/main");
    sourceTailRequire(beforeRef.object.sha === c.parent && /^[0-9a-f]{40}$/.test(mainBeforeRef.object.sha), "Actual branch changed before exact tail CAS");
    await tailMutation("e34-source-ref", "mcp__codex_apps__github_update_ref", {repository_full_name:repo,branch_name:branch,expected_sha:c.parent,force:false,sha:committedSha});
    const after = await get(prefix + "/git/ref/heads/" + branch), mainAfter = await get(prefix + "/git/ref/heads/main");
    sourceTailRequire(after.object.sha === committedSha && /^[0-9a-f]{40}$/.test(mainAfter.object.sha), "Actual post-CAS branch differs; stop without retry");
    const wal = JSON.parse(await sh("python3 -B " + q(c.validator) + " postflight --commit " + q(committedSha)));
    sourceTailRequire(wal.WAL_rows === 44 && wal.successful_pairs === 22 && wal.prior40rows_unchanged === true && wal.uncertain_mutations === 0, "Tail WAL not completely resolved");
    publication = {read_only_main_observations:{staged:meta.read_only_main_observation,before:mainBefore.object.sha,before_ref_update:mainBeforeRef.object.sha,after:mainAfter.object.sha},phase:"source",commit:committedSha,root:c.createdRoot,bench:c.createdBench,scope:c.createdScope,parent:c.parent,leaves,verified_actual_full_tree:true,stage_metadata_sha256:metadataPin.sha256,expected_leaves_sha256:leavesPin.sha256};
    publicationReceipt = await sourceTailPersistNew(S + "/publication-source.json", publication);
    await sourceTailPersistNew(S + "/source-publication-tail-execution-v1.json", {schema_version:1,epoch:34,phase:"source",status:"COMPLETED_TWO_UNUSED_MUTATIONS_ONLY",result:publication,publication_receipt:publicationReceipt,intent:intent.intent,helper:helperPin,local_validator:validatorPin,approval:await readRequestMeta(c.approval),tail_events:events,WAL:wal,blob_or_tree_replays:0,full_publisher_replays:0,model_native_tokenizer_gold_calls:0,further_tail_attempts:0});
    return publication;
  } catch (error) {
    if (intent) {
      try { await sourceTailPersistNew(S + "/source-publication-tail-execution-v1.json", {schema_version:1,epoch:34,phase:"source",status:"STOP_NO_REPLAY_SEE_ROOT_WAL",error:String(error),intent:intent.intent,known_commit:committedSha,tail_events:events,verified_publication_result:publication,publication_receipt:publicationReceipt,external_mutation_status:"INSPECT_ACTUAL_ROOT_WAL_AND_BRANCH_NO_RETRY",blob_or_tree_replays:0,full_publisher_replays:0,model_native_tokenizer_gold_calls:0,further_tail_attempts:0}); } catch (receiptError) { throw Error(String(error) + "; outside receipt write also failed: " + String(receiptError)); }
    }
    throw error;
  }
};
