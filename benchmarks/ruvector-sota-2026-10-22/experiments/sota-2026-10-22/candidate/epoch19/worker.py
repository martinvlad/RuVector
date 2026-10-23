"""One bounded engineering worker; exactly three FP32 then three INT8 pairs."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import common as C


def now():return datetime.now(timezone.utc).isoformat()
def remaining(deadline):
    value=deadline-time.time()
    if value<=0:raise TimeoutError('Qualification worker deadline reached')
    return value


def resources():
    own=resource.getrusage(resource.RUSAGE_SELF);child=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'worker_cpu_user_seconds':own.ru_utime,'worker_cpu_system_seconds':own.ru_stime,
      'worker_peak_RSS_bytes':own.ru_maxrss*1024,'terminated_children_cpu_user_seconds':child.ru_utime,
      'terminated_children_cpu_system_seconds':child.ru_stime,'largest_terminated_child_peak_RSS_bytes':child.ru_maxrss*1024,
      'allowed_CPU_ids':sorted(os.sched_getaffinity(0)),
      'scope':'Linux process high-water marks; child maximum is separate, never a simultaneous RSS sum. CPU self and terminated children are separate observations.'}


def verify_assets(plan):
    lock=C.read(C.checked(plan['model_assets_lock_path']));rows=lock['assets']
    if lock['repo']!='microsoft/deberta-v2-xlarge-mnli'or lock['revision']!='2b65bccdedcead4bc685988bcc30153d4922a789'or len(rows)!=6:raise ValueError('Exact shared six model assets required')
    native=C.read(C.checked(plan['native_closure_path']));core=([r for package in native['packages']for r in package['files']]if 'packages'in native else[r for r in native['files']if r['path'].startswith('retrieval/node_modules/')])
    if len(core)!=8:raise ValueError('Exact eight-file actual native closure required')
    receipts=[]
    for row in rows+core:
        file=C.checked(row['path'])
        if file.stat().st_size!=row['bytes']or C.sha(file)!=row['sha256']:raise ValueError('Selected actual asset identity changed: '+row['path'])
        receipts.append({k:row[k]for k in ('path','bytes','sha256')})
    versions={}
    wheels=C.read(C.checked(plan['wheel_lock_path']))['wheels']
    if len(wheels)!=31:raise ValueError('Exact31-wheel CPU runtime required')
    for wheel in wheels:
        name,expected=wheel['filename'].split('-',2)[:2];actual=importlib.metadata.version(name)
        if actual!=expected:raise ValueError('Installed wheel version changed: '+name)
        versions[name]=actual
    folder=C.checked(next(r['path']for r in rows if r['remote_path']=='config.json')).parent
    return folder,receipts[:6],receipts[6:],versions


def native_trace(plan,rows,raw,folder,deadline):
    bundle,reference=C.engineering_vectors(rows)
    raw['counters']['native_invocations_attempted']+=1;C.replace_report(folder/'raw.json',raw)
    with tempfile.TemporaryDirectory(prefix='ruvector-e19-engineering-')as temp:
        work=Path(temp);source=work/'bundle.json';target=work/'native.json'
        C.write_new(source,bundle)
        command=['node',str(C.checked(C.NATIVE_SCRIPT)),str(source),str(target)]
        process=subprocess.Popen(command,cwd=work,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        raw['counters']['native_queries_attempted']=None
        raw['cleanup']['native_helper_pid']=process.pid;C.replace_report(folder/'raw.json',raw)
        try:
            C.write_new(folder/'native-attempt.json',{'pid':process.pid,'pgid':os.getpgid(process.pid),
              'worker_pid':os.getpid(),'started_at':now(),'source_script_sha256':C.NATIVE_SCRIPT_SHA})
            stdout,stderr=process.communicate(timeout=min(30,remaining(deadline)))
        finally:
            if process.poll()is None:process.kill();process.wait()
        if process.returncode!=0:raise RuntimeError('Actual native helper failed: '+stderr[-1000:])
        result=C.read(target)
        if result.get('native')is not True or result.get('native_binary_sha256')!=C.NATIVE_BINARY_SHA or result.get('package_version')!='0.1.33' or result.get('vectors')!=3 or len(result.get('queries',[]))!=3:
            raise ValueError('Actual native index/identity receipt invalid')
        raw['counters']['native_invocations_completed']+=1;raw['counters']['native_invocations']=1
        raw['counters']['native_queries_attempted']=len(result['queries']);raw['counters']['native_queries_completed']=len(result['queries']);raw['counters']['native_queries']=len(result['queries'])
        raw['native_trace']={'sourceIDs':[row['id']for row in rows],'premises':[row['premise']for row in rows],
          'hypotheses':[row['hypothesis']for row in rows],'bundle':bundle,'reference':reference,
          'raw_native_output':result,'initial_length':0,'initial_length_scope':'Successful exact helper source explicitly asserts empty db before any insertion',
          'final_length':result['vectors'],'raw_scores_available':False,'native_selection_affects_NLI':False,
          'bundle_serialization':'UTF8 JSON ensure_ascii=False indent=2 allow_nan=False followed by LF','selectedIDs':[q['ids'][0]for q in result['queries']],
          'source_script_sha256':C.NATIVE_SCRIPT_SHA,'native_helper_pid':process.pid,
          'helper_exit_code':process.returncode,'helper_exited':process.poll()is not None,
          'NLI_pair_policy':'Each original literal canary premise/H stays direct; actual retrieved IDs never determine a model input'}


def inventory(tensors):
    counts={}
    for _,tensor in tensors:
        dtype=str(tensor.dtype);counts[dtype]=counts.get(dtype,0)+tensor.numel()
    return counts


def classifier(model):
    layer=model.classifier
    weight=layer.weight()if callable(layer.weight)else layer.weight
    bias=layer.bias()if callable(layer.bias)else layer.bias
    return {'weight_shape':list(weight.shape),'bias_shape':list(bias.shape)if bias is not None else None,
            'weight_dtype':str(weight.dtype),'bias_dtype':str(bias.dtype)if bias is not None else None}


def fp32_identity(model,reader,torch):
    digest=hashlib.sha256()
    for name,tensor in sorted(model.named_parameters()):reader._hash_tensor(digest,'parameter:'+name,tensor,torch)
    for name,tensor in sorted(model.named_buffers()):reader._hash_tensor(digest,'buffer:'+name,tensor,torch)
    return digest.hexdigest()


def tensor_state(model,torch):
    parameters=list(model.named_parameters());buffers=list(model.named_buffers())
    return {'parameter_count':sum(t.numel()for _,t in parameters),'parameter_dtypes':sorted(inventory(parameters)),'parameter_dtype_element_counts':inventory(parameters),
      'buffer_dtypes':sorted(inventory(buffers)),'buffer_dtype_element_counts':inventory(buffers),'devices':sorted({t.device.type for _,t in parameters+buffers}),
      'classifier':classifier(model),'eligible_linear_modules':sorted(name for name,module in model.named_modules()if isinstance(module,torch.nn.Linear)),
      'model_instance_token':hex(id(model)),'eval':not model.training,'inference_mode':torch.is_inference_mode_enabled(),
      'autocast':torch.is_autocast_enabled('cpu'),'threads':torch.get_num_threads(),
      'interop_threads':torch.get_num_interop_threads(),'deterministic_algorithms':torch.are_deterministic_algorithms_enabled()}


def tokenizer(folder,transformers):
    high=transformers.DebertaV2TokenizerFast.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
    backend=high.backend_tokenizer;backend.no_padding();backend.no_truncation()
    state=json.loads(backend.to_str())
    if state['model']['type']!='Unigram'or state.get('padding')or state.get('truncation'):raise ValueError('Exact unpadded/untruncated Unigram required')
    return high,backend,{'spm_sha256':C.sha(folder/'spm.model'),
      'converted_backend_sha256':hashlib.sha256(backend.to_str().encode()).hexdigest(),
      'cls_id':high.cls_token_id,'sep_id':high.sep_token_id,'pad_id':high.pad_token_id,'unk_id':high.unk_token_id,
      'pair_format':'[CLS]premise[SEP]hypothesis[SEP]','padding':False,'truncation':False,
      'conversion':'Builtin Transformers4.52.4 DebertaV2TokenizerFast from exact official SPM; no remote code'}


def perform(plan,rows,raw,folder,deadline):
    model=None;source_state=None
    asset_folder,assets,native_assets,versions=verify_assets(plan)
    raw['model_provenance']={'repo':'microsoft/deberta-v2-xlarge-mnli','revision':'2b65bccdedcead4bc685988bcc30153d4922a789',
      'original_checkpoint_sha256':C.sha(asset_folder/'pytorch_model.bin'),'config_sha256':C.sha(asset_folder/'config.json'),
      'asset_identities':assets,'native_asset_identities':native_assets,
      'versions':{k:versions[k]for k in ('torch','transformers','sentencepiece','tokenizers','safetensors','protobuf')},'all31_installed_versions':versions,
      'expected_architecture':{'layers':24,'hidden_size':1536,'attention_heads':24,'classes':3},'architecture':None}
    native_trace(plan,rows,raw,folder,deadline);C.replace_report(folder/'raw.json',raw)
    remaining(deadline)
    # Every model/framework import and all runtime actions are inside this worker.
    import torch
    import transformers
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    if 'fbgemm'not in torch.backends.quantized.supported_engines:raise ValueError('Required fbgemm unavailable')
    torch.backends.quantized.engine='fbgemm'
    path=C.checked(C.PREFIX+'candidate/epoch18/torch_reader.py')
    spec=importlib.util.spec_from_file_location('epoch19_frozen18_pure_reader',path)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    config=C.read(asset_folder/'config.json');mapping=reader.label_indices(config)
    if mapping!={'contradiction':0,'neutral':1,'entailment':2}:raise ValueError('Original C0/N1/E2 mapping required')
    high,backend,token_receipt=tokenizer(asset_folder,transformers);raw['tokenizer']=token_receipt
    # Meta tensors expose actual serialized dtype/shape without retaining a second full CPU state.
    raw['counters']['checkpoint_metadata_loads']+=1;C.replace_report(folder/'raw.json',raw)
    source_state=torch.load(asset_folder/'pytorch_model.bin',map_location='meta',weights_only=True)
    if not isinstance(source_state,dict)or not source_state or any(not isinstance(t,torch.Tensor)for t in source_state.values()):raise ValueError('Expected original tensor-only checkpoint state')
    raw['model_provenance'].update(source_storage_dtype_inventory={dtype:sum(str(t.dtype)==dtype for t in source_state.values())for dtype in sorted({str(t.dtype)for t in source_state.values()})},
      source_storage_dtype_element_counts=inventory(list(source_state.items())),
      source_storage_tensor_count=len(source_state),source_storage_inspection='torch.load(weights_only=True,map_location=meta); original serialized dtype/shape, not original device claim',
      source_classifier={k:list(source_state[k].shape)for k in ('classifier.weight','classifier.bias')})
    del source_state;source_state=None;gc.collect();remaining(deadline)
    raw['counters']['model_initializations_attempted']+=1;C.replace_report(folder/'raw.json',raw)
    model,loading=transformers.DebertaV2ForSequenceClassification.from_pretrained(str(asset_folder),
      local_files_only=True,trust_remote_code=False,use_safetensors=False,weights_only=True,
      torch_dtype=torch.float32,output_loading_info=True)
    raw['counters']['model_initializations_completed']+=1;raw['counters']['model_initializations']=1
    if any(loading.get(k)for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):raise ValueError('Strict original model loading coverage failed')
    model.eval();model.requires_grad_(False)
    actual_config=model.config
    raw['model_provenance']['architecture']={'layers':actual_config.num_hidden_layers,'hidden_size':actual_config.hidden_size,
      'attention_heads':actual_config.num_attention_heads,'classes':actual_config.num_labels}
    if raw['model_provenance']['architecture']!=raw['model_provenance']['expected_architecture']:raise ValueError('Actual constructed model architecture changed')
    raw['model_provenance'].update(raw_label_indices=mapping,typed_order=list(reader.TYPED_ORDER),loading_info=loading,
      loading_flags={'local_files_only':True,'trust_remote_code':False,'use_safetensors':False,
        'weights_only':True,'torch_dtype':'torch.float32','output_loading_info':True})
    with torch.inference_mode():raw['fp32_state']=tensor_state(model,torch)
    if set(raw['fp32_state']['parameter_dtypes'])!={'torch.float32'}or raw['fp32_state']['devices']!=['cpu']or raw['fp32_state']['classifier']['weight_shape']!=[3,1536]:raise ValueError('Actual loaded CPU FP32 architecture invalid')
    with torch.inference_mode():raw['fp32_state']['sha256']=fp32_identity(model,reader,torch)
    raw['fp32_state']['inference_state_scope']='Actual inference_mode state during tensor inspection; each actual forward independently records inference/gradient context'
    prepared=[]
    for row in rows:
        encoded=backend.encode(row['premise'],row['hypothesis'])
        values={'input_ids':encoded.ids,'attention_mask':encoded.attention_mask,'token_type_ids':encoded.type_ids}
        high_feed=high(row['premise'],row['hypothesis'],padding=False,truncation=False,add_special_tokens=True,return_attention_mask=True,return_token_type_ids=True)
        if any(high_feed[k]!=v for k,v in values.items())or len(encoded.ids)>512 or encoded.ids[0]!=high.cls_token_id or encoded.ids[-1]!=high.sep_token_id or encoded.ids.count(high.sep_token_id)!=2 or encoded.type_ids[0]!=0 or encoded.type_ids[-1]!=1 or any(v!=1 for v in encoded.attention_mask):raise ValueError('Actual direct pair serialization mismatch')
        prepared.append((row,values,encoded.offsets,{k:high_feed[k]for k in values}))
    raw['tokenizer']['high_level_backend_feed_equality_verified']=True
    try:
        for precision in ('FP32','INT8'):
            if precision=='INT8':
                remaining(deadline);raw['counters']['quantization_initializations_attempted']+=1;C.replace_report(folder/'raw.json',raw)
                converted=torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True)
                if converted is not model:raise ValueError('Quantization must preserve same model object')
                model.eval();raw['counters']['quantization_initializations_completed']+=1;raw['counters']['quantization_initializations']=1
                state_sha,modules=reader.quantized_state_identity(model,torch)
                if sorted(m['name']for m in modules)!=raw['fp32_state']['eligible_linear_modules']:raise ValueError('All and only eligible Linear modules must convert')
                with torch.inference_mode():
                    raw['int8_state']={'sha256':state_sha,'quantized_linear_modules':modules,'quantized_linear_count':len(modules),
                      'eligible_linear_modules':raw['fp32_state']['eligible_linear_modules'],'model_instance_token':hex(id(model)),
                      'same_model_object':hex(id(model))==raw['fp32_state']['model_instance_token'],'inplace':True,'fbgemm':torch.backends.quantized.engine=='fbgemm','backend':torch.backends.quantized.engine,
                      'quantization_recipe':'torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True);eval;fbgemm',
                      'eval':not model.training,'inference_mode':torch.is_inference_mode_enabled(),'autocast':torch.is_autocast_enabled('cpu'),'device':'cpu',
                      'precision':reader.PRECISION,'classifier':classifier(model),'threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads()}
            for row,values,offsets,high_feed in prepared:
                remaining(deadline);started=time.perf_counter();tag=precision.lower()
                raw['counters']['nli_forward_pairs_attempted']+=1;raw['counters'][tag+'_forwards_attempted']+=1;C.replace_report(folder/'raw.json',raw)
                feed={k:torch.tensor([v],dtype=torch.int64,device='cpu')for k,v in values.items()}
                with torch.inference_mode():
                    inference_enabled=torch.is_inference_mode_enabled();grad_enabled=torch.is_grad_enabled()
                    output=model(**feed).logits
                elapsed=time.perf_counter()-started
                if elapsed>30 or tuple(output.shape)!=(1,3)or output.dtype!=torch.float32:raise ValueError('Finite singleton raw FP32 output under decision30 required')
                logits=[float(x)for x in output[0].tolist()];probabilities=reader.threeway_probabilities(logits,mapping)
                raw['counters']['nli_forward_pairs_completed']+=1;raw['counters'][tag+'_forwards_completed']+=1
                raw['forwards'].append({'precision':precision,'fixture_id':row['id'],'fixture_sha256':row['sha256'],
                  'premise':row['premise'],'hypothesis':row['hypothesis'],**values,'offsets':offsets,'high_level_pair_feed':high_feed,
                  'raw_logits':logits,'typed_probabilities':probabilities,'prediction':reader.typed_prediction(probabilities),
                  'truncated':False,'padding':False,'feed_dtype':'torch.int64','feed_device':'cpu','batch_size':1,
                  'raw_logit_dtype':str(output.dtype),'raw_logit_shape':list(output.shape),'inference_mode_enabled':inference_enabled,'grad_enabled':grad_enabled,
                  'elapsed_seconds':elapsed,'input_pair_sha256':hashlib.sha256(json.dumps({'premise':row['premise'],'hypothesis':row['hypothesis']},ensure_ascii=False,separators=(',',':')).encode()).hexdigest()})
                C.replace_report(folder/'raw.json',raw)
    finally:
        model=None;source_state=None;gc.collect()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--expected-plan-sha',required=True)
    parser.add_argument('--admission',type=Path,required=True);parser.add_argument('--deadline',type=float,required=True);args=parser.parse_args()
    plan=C.require_plan(args.plan,args.expected_plan_sha);C.verify_admission(args.admission,args.expected_plan_sha)
    folder=C.STUDY/'runs/qualification';attempt=C.read(folder/'attempt.json');reservation=C.read(folder/'popen-attempt.json')
    if attempt.get('pid')!=os.getpid()or attempt.get('pgid')!=os.getpgrp()or attempt.get('plan_sha256')!=args.expected_plan_sha or reservation.get('plan_sha256')!=args.expected_plan_sha or attempt.get('deadline_unix')!=args.deadline or not time.time()<args.deadline<attempt['hard_cleanup_deadline_unix']<=plan['lease_expires_unix']-30 or attempt['hard_cleanup_deadline_unix']-attempt['invocation_started_unix']>600:
        raise ValueError('Only exact reserved owned worker may import models/native')
    keys=['model_initializations','quantization_initializations','nli_forward_pairs','fp32_forwards','int8_forwards','native_invocations']
    counters={stem+'_'+end:0 for stem in keys for end in ('attempted','completed')}
    counters.update(model_initializations=0,quantization_initializations=0,native_invocations=0,native_queries=0,
      checkpoint_metadata_loads=0,native_queries_attempted=0,native_queries_completed=0,other_model_forwards=0,BGE_forwards=0,
      ORT_sessions=0,previous_reader_forwards=0,native104_calls=0,benchmark_HTTP_requests=0,benchmark_corpora=0,paid_API_calls=0,GPU_calls=0,
      train_fits=0,calibration_fits=0,CONF_calls=0)
    raw={'schema_version':1,'epoch':19,'status':'STARTED','at':now(),'plan_sha256':args.expected_plan_sha,
      'worker_pid':os.getpid(),'worker_pgid':os.getpgrp(),
      'spec_sha256':C.SPEC_SHA,'fixture_manifest_sha256':C.FIXTURES_SHA,'model_provenance':{},'tokenizer':{},
      'fp32_state':{},'int8_state':{},'forwards':[],'native_trace':None,'counters':counters,
      'resources':{'before_runtime':resources()},'cleanup':{'worker_post_exit_proof':'External parent execution receipt required'}}
    try:
        perform(plan,C.fixtures(plan),raw,folder,args.deadline)
        raw.update(status='COMPLETED',finished_at=now())
    except BaseException as error:
        raw.update(status='FAILED_PRESERVED_PARTIAL_ENGINEERING_EVIDENCE',error=type(error).__name__+': '+str(error),finished_at=now())
        raise
    finally:
        raw['resources']['worker_terminal']=resources();raw['cleanup'].update(worker_cleanup_recorded=True)
        C.replace_report(folder/'raw.json',raw)


if __name__=='__main__':main()
