"""Authenticate root-authorized source/physical closure before any gold decode."""
import hashlib,json,re
from pathlib import Path
import finfact_io as I
import finfact_metrics as M
import finfact_data as D
import finfact_execution as X

def checked_bundle(admission_ref,project):
 a=I.load_ref(admission_ref,project);I.envelope(a)
 I.require(a.get('source_checkpoint')==I.SOURCE and a.get('root_custodian_authorized')is True and a.get('approved_late_gold_read')is True,'EXACT_ROOT_LATE_GOLD_AUTHORIZATION_REQUIRED')
 refs=a['evidence'];I.require(set(refs)=={'plan','raw','execution','dispatch','observer','physical_closure','source_admission'},'FULL_SOURCE_AND_PHYSICAL_REFERENCE_BUNDLE_REQUIRED')
 # All refs are authenticated by root's exact admission SHA. No ref is inferred
 # from a boolean, and no worker-self-reported count authorizes label access.
 I.read_ref(refs['observer'],project);body={k:I.load_ref(v,project)for k,v in refs.items()if k!='observer'};plan=body['plan'];raw=body['raw'];closure=body['physical_closure'];execution=body['execution'];dispatch=body['dispatch'];source=body['source_admission'];plan_sha=refs['plan']['sha256']
 I.require(a['source_plan_sha256']==plan_sha,'ROOT_ADMISSION_PLAN_MISMATCH')
 for name,x,key in [('raw',raw,'plan_sha256'),('execution',execution,'plan_sha256'),('dispatch',dispatch,'plan_sha256'),('physical_closure',closure,'source_plan_sha256')]:
  I.envelope(x);I.require(x[key]==plan_sha,'RETAINED_ARTIFACT_PLAN_MISMATCH:'+name)
 I.envelope(source);I.require(type(a['source_commit'])is str and re.fullmatch('[0-9a-f]{40}',a['source_commit'])and source['checks_passed']is True and source['verified_actual_remote_readback']is True and source['actual_source_commit']==source['published_source_commit']==a['source_commit']and source['source_plan_sha256']==source['plan_sha256']==plan_sha,'ACTUAL_SOURCE_ADMISSION_BINDING_REQUIRED')
 independent=I.load_ref(source['independent_actual_source_readback'],project);I.envelope(independent);I.require(independent['checks_passed']is True and independent['verified_actual_remote_readback']is True and independent['commit']==a['source_commit']and independent['source_plan_sha256']==plan_sha,'ACTUAL_INDEPENDENT_SOURCE_READBACK_BINDING_REQUIRED')
 I.require(independent['source_freeze_sha256']==source['source_freeze_sha256']==plan['source_freeze_sha256']==plan['source_freeze']['sha256']and independent['tree_sha']==source['tree_sha']and re.fullmatch('[0-9a-f]{64}',source['source_freeze_sha256'])and re.fullmatch('[0-9a-f]{40}',source['tree_sha']),'INDEPENDENT_SOURCE_FREEZE_TREE_MISMATCH')
 I.require(plan['phase']=='dev'and plan['epoch']==39 and plan['kind']==I.KIND,'FROZEN_DEV_PLAN_REQUIRED');roles=plan['data_roles'];ids=roles['dev'];I.require(len(ids)==len(set(ids))==12 and roles['train']==roles['calibration']==roles['confirmation']==[]and plan['used_confirmation_identities']==[],'EXACT_DEV_ONLY_IDENTITIES_REQUIRED');I.require(plan['arms']==M.ARMS and plan['actual_NLI_forwards']==48,'FROZEN_FOUR_ARMS_48_REQUIRED')
 I.read_ref(plan['observer_helper_source'],project)
 I.require(execution['raw']==refs['raw'],'EXECUTOR_CAPTURED_RAW_REF_MISMATCH')
 I.require(raw['status']=='DEV_FORECASTS_COMPLETE_NO_GOLD'and raw['errors']==[]and raw['source_checkpoint']==I.SOURCE,'ERROR_FREE_GOLD_BLIND_FORECASTS_REQUIRED');rows=raw['cases'];I.require([r['id']for r in rows]==ids,'ALL_FIXED_IDENTITIES_IN_ORDER_REQUIRED');readouts=[]
 for row in rows:
  I.require(set(row['readouts'])==set(M.ARMS),'FOUR_PHYSICAL_READOUTS_PER_CASE_REQUIRED')
  for arm in M.ARMS:M.readout_check(row['readouts'][arm],row['id'],arm);readouts.append(row['readouts'][arm]['readout_id'])
 want=[i+'::'+arm for i in ids for arm in M.ARMS];I.require(len(readouts)==len(set(readouts))==48 and set(readouts)==set(want),'FORTY_EIGHT_ACTUAL_UNIQUE_REPLAYED_READOUTS_REQUIRED')
 for name in ['required_readout_ids','completed_readout_ids']:I.require(len(raw[name])==48 and set(raw[name])==set(want),'RAW_READOUT_COMPLETENESS_REQUIRED')
 offline=raw['offline_policy'];I.require(offline['clean']is True and offline['literal_capability_bind_closed']is True and type(offline['allowed_capability_count'])is int and offline['allowed_capability_count']==raw['counters']['Python_literal_loopback_capability_binds_allowed']and offline['violations_count']==0,'ACTUAL_CLEAN_OFFLINE_POLICY_REQUIRED');I.require(raw['native_state']['capture_complete']is True and raw['native_state']['child_closed']is True,'CAPTURED_NATIVE_CHILD_CLOSURE_REQUIRED')
 X.execution_audit(raw,plan,plan['expected_counters_source'],project)
 f=raw['closure_facts'];I.require(f['physical_readouts_completed']==48 and type(f['physical_readouts_completed'])is int and f['model_profiles_disposed']==['xxlarge','b354']and f['native_child_closed']is True and f['all_forecasts_closed_before_gold']is True,'RETAINED_READER_NATIVE_LIFECYCLE_REQUIRED')
 # The independent external closure proof binds all actual dispatch lifecycle
 # artifacts. Its execution must be the exact retained execution in this bundle.
 evidence=closure['evidence'];I.require(evidence['dispatch_attempt']==refs['dispatch']and evidence['execution']==refs['execution'],'PHYSICAL_PROOF_DISPATCH_EXECUTION_REF_MISMATCH')
 for name in ['reservation','completion']:I.load_ref(evidence[name],project)
 completion=I.load_ref(evidence['completion'],project);supervisor_qualification=X.supervisor_qualification(execution,completion,raw,refs,closure,project,dispatch)
 I.require(closure['physical_supervisor_closed']is True and closure['physical_closure_passed']is True and closure['unknown_physical_ownership']is False and closure['owned_worker_group_members']==[],'FULL_PHYSICAL_CLOSURE_REQUIRED')
 I.require('physical_supervisor_absent'in closure and type(closure['physical_supervisor_absent'])is bool and 'observed_supervisor_state'in closure,'ABSENCE_VS_CLOSED_DISTINCTION_REQUIRED')
 # The source-pinned observer program in the plan is separately hashed. It is
 # not imported or executed by this custodian.
 observer_ref=plan['observer_source'];I.require(refs['observer']==observer_ref,'SOURCE_PINNED_OBSERVER_REF_MISMATCH')
 physical_pin=dict(refs['physical_closure']);physical_pin['path']=str(Path(project)/physical_pin['path'])if not Path(physical_pin['path']).is_absolute()else physical_pin['path']
 full=dict(f,required_readout_ids=want,completed_readout_ids=want,source_plan_sha256=plan_sha,physical_closure_evidence=physical_pin)
 D.check_physical_gold_fence(full,ids)
 return {'admission':a,'references':refs,'objects':body,'ids':ids,'closure':full,'readout_ids':readouts,'source_plan_sha256':plan_sha,'supervisor_qualification':supervisor_qualification}
