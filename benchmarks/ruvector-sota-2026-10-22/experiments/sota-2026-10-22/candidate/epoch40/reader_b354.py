"""Stock DeBERTa-v3-large NLI via safe F16-to-F32 mmap/meta assignment; lazy ML imports."""
import hashlib
import json
import math
from pathlib import Path
import struct
import time

LABELS=('Entailment','NotMentioned','Contradiction')
WEIGHT_SHA='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
CONFIG_SHA='7f9d420b616691c5b575bab8839719aefbddc656d8e1316519414b097ce43e3d'


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1048576),b''):h.update(part)
    return h.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _object(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('Duplicate safe header key')
        out[k]=v
    return out


def safe_header(file):
    size=Path(file).stat().st_size
    with Path(file).open('rb') as stream:
        first=stream.read(8)
        if len(first)!=8:raise ValueError('Missing safetensors header')
        length=struct.unpack('<Q',first)[0]
        if not 1<=length<=2_000_000 or length+8>=size:raise ValueError('Invalid bounded safe header')
        raw=stream.read(length)
    value=json.loads(raw,object_pairs_hook=_object,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite header')))
    tensors={k:v for k,v in value.items() if k!='__metadata__'}
    at=0
    for name,row in sorted(tensors.items(),key=lambda item:item[1]['data_offsets'][0]):
        if not isinstance(name,str) or set(row)!={'dtype','shape','data_offsets'} or row['dtype'] not in ('F16','I64'):
            raise ValueError('Unexpected tensor/header schema')
        shape=row['shape'];offsets=row['data_offsets']
        if not isinstance(shape,list) or any(type(n) is not int or n<0 for n in shape):raise ValueError('Invalid tensor shape')
        if not isinstance(offsets,list) or len(offsets)!=2 or any(type(n) is not int for n in offsets):raise ValueError('Invalid tensor offsets')
        expected=math.prod(shape)*(2 if row['dtype']=='F16' else 8)
        if offsets[0]!=at or offsets[1]-offsets[0]!=expected:raise ValueError('Overlapping/gapped/wrong-sized safe tensor')
        at=offsets[1]
    if at!=size-length-8:raise ValueError('Unaccounted safe weight bytes')
    return tensors,{'header_bytes':length,'header_sha256':hashlib.sha256(raw).hexdigest(),'tensor_count':len(tensors),'data_bytes':at}


class FrozenMoritzProofReader:
    def __init__(self,directory,counters,progress):
        self.counters,self.progress=counters,progress;directory=Path(directory)
        weight=directory/'model.safetensors'
        if weight.stat().st_size!=870182606 or file_sha(weight)!=WEIGHT_SHA:raise ValueError('Original F16 safe file size changed')
        if hashlib.sha256((directory/'config.json').read_bytes()).hexdigest()!=CONFIG_SHA:raise ValueError('Exact trained head config changed')
        header,header_receipt=safe_header(weight)
        self.counters['model_initializations_attempted']+=1;progress({'event':'NLI_MODEL_INITIALIZATION_BEFORE'})
        started=time.perf_counter()
        import torch
        import transformers
        import safetensors
        from safetensors import safe_open
        from transformers import DebertaV2Config,DebertaV2ForSequenceClassification,AutoTokenizer
        if (torch.__version__!='2.7.1+cpu' or transformers.__version__!='4.52.4' or safetensors.__version__!='0.5.3'):
            raise ValueError('Exact admitted CPU runtime versions required')
        torch.set_num_threads(2)
        if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
        self.torch=torch
        config=DebertaV2Config.from_json_file(str(directory/'config.json'))
        if ({int(k):v.lower() for k,v in config.id2label.items()}!={0:'entailment',1:'neutral',2:'contradiction'}
                or config.num_labels!=3 or config.architectures!=['DebertaV2ForSequenceClassification']
                or config.hidden_size!=1024 or config.num_hidden_layers!=24 or config.max_position_embeddings!=512):
            raise ValueError('Wrong original trained E,N,C head/config')
        config._attn_implementation='eager'
        with torch.device('meta'):
            model=DebertaV2ForSequenceClassification(config)
        expected=model.state_dict();position='deberta.embeddings.position_ids'
        extra=set(header)-set(expected)
        if set(expected)-set(header) or extra-set([position]):raise ValueError('Missing/unexpected learned tensor keys')
        for name,tensor in expected.items():
            if header[name]['shape']!=list(tensor.shape) or header[name]['dtype']!='F16':raise ValueError('Learned state shape/dtype differs: '+name)
        if header.get('classifier.weight',{}).get('shape')!=[3,1024] or header.get('classifier.bias',{}).get('shape')!=[3]:raise ValueError('Native classifier changed')
        if sum(math.prod(row['shape']) for row in header.values() if row['dtype']=='F16')!=435064835:raise ValueError('Original learned parameter count differs')
        if any(row['dtype']=='I64' and name!=position for name,row in header.items()):raise ValueError('Unexplained integer state')
        with safe_open(str(weight),framework='pt',device='cpu') as mapped:
            if set(mapped.keys())!=set(header):raise ValueError('Mmap/header key mismatch')
            state={}
            for name in expected:
                source_tensor=mapped.get_tensor(name)
                if source_tensor.dtype!=torch.float16 or source_tensor.device.type!='cpu':raise ValueError('Original learned state must be F16 CPU: '+name)
                state[name]=source_tensor.to(dtype=torch.float32)
                if state[name].dtype!=torch.float32 or state[name].device.type!='cpu':raise ValueError('Lossless F16-to-F32 materialization failed: '+name)
            loaded=model.load_state_dict(state,strict=True,assign=True)
            if loaded.missing_keys or loaded.unexpected_keys:raise ValueError('Incomplete exact parameter assignment')
            position_expected=torch.arange(512,dtype=torch.long,device='cpu').unsqueeze(0)
            if position in header:
                if header[position]['shape']!=[1,512] or header[position]['dtype']!='I64':raise ValueError('Wrong source position_ids buffer')
                position_actual=mapped.get_tensor(position)
                if not torch.equal(position_actual,position_expected):raise ValueError('Nonstandard source position_ids')
                model.deberta.embeddings.position_ids=position_actual
                buffer_source='Exact mmap source int64 arange512 checked against stock nonpersistent buffer'
            else:
                model.deberta.embeddings.position_ids=position_expected
                buffer_source='Only deterministic nonpersistent stock position_ids constructed from source/config; no learned fallback'
        for name,tensor in list(model.named_parameters())+list(model.named_buffers()):
            if tensor.is_meta or tensor.device.type!='cpu' or tensor.dtype!=(torch.int64 if name==position else torch.float32):
                raise ValueError('Unmaterialized/non-CPU/wrong-dtype tensor: '+name)
        if set(dict(model.named_buffers()))!={position}:raise ValueError('Unexplained stock buffers')
        if sum(p.numel() for p in model.parameters())!=435064835:raise ValueError('Actual assigned graph count differs')
        for parameter in model.parameters():parameter.requires_grad_(False)
        model.eval();self.model=model
        self.counters['tokenizer_initializations_attempted']+=1
        tokenizer=AutoTokenizer.from_pretrained(str(directory),local_files_only=True,trust_remote_code=False,use_fast=True)
        if type(tokenizer).__name__!='DebertaV2TokenizerFast' or not tokenizer.is_fast:raise ValueError('Exact stock fast tokenizer required')
        original_backend=tokenizer.backend_tokenizer.to_str()
        tokenizer.backend_tokenizer.no_truncation();tokenizer.backend_tokenizer.no_padding()
        if tokenizer.backend_tokenizer.truncation is not None or tokenizer.backend_tokenizer.padding is not None:raise ValueError('Hidden backend clipping/padding')
        if tokenizer.num_special_tokens_to_add(pair=True)!=3:raise ValueError('Stock true-pair formatting changed')
        if [tokenizer.pad_token_id,tokenizer.cls_token_id,tokenizer.sep_token_id,tokenizer.unk_token_id,tokenizer.mask_token_id]!=[0,1,2,3,128000]:raise ValueError('Original special IDs changed')
        self.tokenizer=tokenizer;self.counters['tokenizer_initializations_completed']+=1
        self._parameter_versions={name:(param.data_ptr(),param._version) for name,param in model.named_parameters()}
        self._head_manifest=self.head_manifest()
        self.runtime_checks={**header_receipt,'model_class':type(model).__name__,'learned_parameters':435064835,
            'loading_missing_keys':[],'loading_unexpected_keys':[],'CPU_FP32':True,'meta_tensors_remaining':0,
            'safe_mmap_meta_assign':True,'source_parameter_dtype':'F16','compute_dtype':'F32',
            'source_learned_tensor_count':len(expected),'all_source_values_preserved_exactly':True,'all_source_values_losslessly_converted_F16_to_F32':True,
            'config_declared_torch_dtype':str(config.torch_dtype),'position_ids_buffer_source':buffer_source,'nonpersistent_buffers':[position],
            'tokenizer_class':type(tokenizer).__name__,'backend_before_sha256':hashlib.sha256(original_backend.encode()).hexdigest(),
            'backend_after_sha256':hashlib.sha256(tokenizer.backend_tokenizer.to_str().encode()).hexdigest(),
            'pair_special_tokens':3,'attention':'eager','no_training_or_classifier_reinitialization':True,
            'initialization_seconds':time.perf_counter()-started,'actual_model_warmup_forwards':0,'weights_sha256':WEIGHT_SHA,'classifier_manifest':self._head_manifest}
        self.counters['model_initializations_completed']+=1;progress({'event':'NLI_MODEL_INITIALIZATION_AFTER','runtime_checks':self.runtime_checks})

    def head_manifest(self):
        return {name:{'shape':list(t.shape),'dtype':'float32','sha256':hashlib.sha256(t.detach().numpy().tobytes(order='C')).hexdigest()}
            for name,t in self.model.named_parameters() if name in ('classifier.weight','classifier.bias','pooler.dense.weight','pooler.dense.bias')}

    def unchanged(self):
        good=(all(not p.requires_grad for p in self.model.parameters()) and not self.model.training
            and {name:(p.data_ptr(),p._version) for name,p in self.model.named_parameters()}==self._parameter_versions
            and self.head_manifest()==self._head_manifest)
        if not good:raise ValueError('Frozen original model/head state changed')
        return {'unchanged':True,'classifier_manifest':self._head_manifest,'scope':'Parameter storage identity/version counters plus exact head bytes; immutable source weight SHA reverified outside reader. No complete tensor clone.'}

