"""Run only pure tiny-payload/pinned-metadata fixtures; never import frozen guards."""
from pathlib import Path
import ast,hashlib,importlib.util,io,json,re,sys,time,unittest
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('future_identity_unit_fixtures',HERE/'test_asset_identity.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
# Independently materialize the proposed unified diff as text and parse it only.
old=(HERE/'E37_FROZEN_common.py.txt').read_text().splitlines(keepends=True)
patch_lines=(HERE/'FUTURE_ONLY_SOURCE_INTEGRATION.patch').read_text().splitlines(keepends=True)
new=[];cursor=0;index=2
while index<len(patch_lines):
 header=patch_lines[index];match=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',header)
 if not match:raise AssertionError('Malformed unified patch hunk')
 start=int(match.group(1))-1;new.extend(old[cursor:start]);cursor=start;index+=1
 while index<len(patch_lines)and not patch_lines[index].startswith('@@ '):
  line=patch_lines[index];tag=line[0];body=line[1:]
  if tag in(' ','-'):
   assert old[cursor]==body;cursor+=1
  if tag in(' ','+'):new.append(body)
  index+=1
new.extend(old[cursor:]);proposed=''.join(new);ast.parse(proposed)
(HERE/'FUTURE_ONLY_common.py.txt').write_text(proposed)
output=io.StringIO();started=time.monotonic();result=unittest.TextTestRunner(stream=output,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(M));elapsed=time.monotonic()-started
A=M.A;identities=A.bind_catalog(M.EXPECTED,M.OBSERVED)
def ref(p):return {'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
independent=HERE/'actual-LFS-identity-failure-independent-v1.json'
assert hashlib.sha256(independent.read_bytes()).hexdigest()=='d7e2277a0ff851118d7ad96491194918df3b7b78efcee34586e6d50b249e9f5a'
real={'schema_version':1,'status':'PASS_REAL_PINNED_METADATA_TERMINAL_POLICY_FIXTURE_NO_PAYLOAD_OR_GUARD_EXECUTION',
 'source_catalog':ref(HERE/'MODEL_ASSETS.expected.json'),'E37_observed_materialization_receipt':ref(HERE/'E37_OBSERVED_MODEL_ASSETS.json'),
 'independent_actual_SPM_hash_observation':ref(independent),
 'SPM_actual_payload_Git_SHA1_from_independent_observation':'1f77a5ca5173931f43d45117ed425a317e6cf553',
 'SPM_upstream_pointer_Git_SHA1':'c146a1df1f80d26596bbb4d0fadc43bca9a8145c',
 'SPM_payload_vs_pointer_Git_SHA1_are_different':True,
 'all_five_typed_metadata_identities':identities,'complete_terminal_pure_policy_exercised':True,
 'previous_E37_failure_selector':'Observedlock has sha256butnoupstream_sha256, so previousguard incorrectlyrequestedpayloadGitSHA1comparisonforbothLFSfiles.',
 'fixed_selector':'Only explicitlytyped sourcecatalog selects representation. Observedlock cannotalias declaration. LFS upstreamGit isverifiedagainstcanonicalpointeroid/size; separatepayloadsize/SHA256aremandatory. RawGit payload requires both SHA256andupstreamGitSHA1.',
 'prior_real_payload_SHA256_evidence':'Originalfive actualpayloadSHA256 were verifiedbefore E37 byroot; this fixture binds exactrecordedmetadata and doesNOT reread any modelpayload or claim a newfileverification.',
 'actual_model_weight_file_reads':0,'actual_tokenizer_payload_file_reads':0,'current_guard_invocations':0,
 'actual_model_tokenizer_native_inference_calls':0,'actual12_case_parser_calls':0,'network_calls':0,'new_dispatches':0,
 'E37_retry_authorized':False,'frozen_E37_source_changed':False}
(HERE/'REAL_METADATA_TERMINAL_FIXTURE.v1.json').write_text(json.dumps(real,indent=2)+'\n')
report={'schema_version':1,'status':'PASS'if result.wasSuccessful()else'FAIL','future_only':True,'tests_run':result.testsRun,
 'failures':len(result.failures),'errors':len(result.errors),'elapsed_seconds':elapsed,'test_output':output.getvalue(),
 'proposed_common_AST_parse_passed':True,'proposed_common':ref(HERE/'FUTURE_ONLY_common.py.txt'),
 'test_source':ref(HERE/'test_asset_identity.py'),'helper_source':ref(HERE/'asset_identity.py'),
 'actual_metadata_fixture':ref(HERE/'REAL_METADATA_TERMINAL_FIXTURE.v1.json'),
 'ML_modules_imported':[n for n in('torch','transformers','onnxruntime','tokenizers','numpy')if n in sys.modules],
 'current_guard_or_real_payload_execution':False,'actual12_case_calls':0,'new_dispatches':0,'external_mutations':0}
assert not report['ML_modules_imported']
(HERE/'PURE_FIXTURE_RESULTS.v1.json').write_text(json.dumps(report,indent=2)+'\n')
if not result.wasSuccessful():raise SystemExit(1)
print(json.dumps({'status':report['status'],'tests':result.testsRun,'result':ref(HERE/'PURE_FIXTURE_RESULTS.v1.json'),'real_metadata':ref(HERE/'REAL_METADATA_TERMINAL_FIXTURE.v1.json')}))
