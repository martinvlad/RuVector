from pathlib import Path
import json,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).parent
bpath=ROOT/'experiments/sota-2026-10-22/legal-transfer/epoch15/build.py'
spec=importlib.util.spec_from_file_location('frozen_epoch15_label_free_input_builder',bpath);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
sourcepath=ROOT/'experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'
source,docs,prepared,validation=b.validate_before_gold(sourcepath,ROOT)
out={'schema_version':1,'scope':'Fixedroles sourceinputs for tokenization/capacity only; no annotation choices/model/nativecalls','development':[],'confirmation':[]}
for item,h,normsha,inputs,inputsha,norminputsha in prepared:
 out['development'].append({'id':f"original-contractnli:train:epoch15:dev:{item['document_id']}:{h}",'input':inputs,'input_sha256':inputsha})
allow=json.loads((ROOT/'experiments/sota-2026-10-22/legal-transfer/epoch15/confirmation-allowlist.json').read_text())
for r in allow['records']:
 doc=docs[int(r['source_group'].split(':')[-1])];positive=source['labels'][r['hypothesis_id']]['hypothesis']
 inputs={'state':doc['text'],'questions':{'decision':{'type':'choice','instructions':b.INSTRUCTION,'criteria':{'Yes':positive,'No':'The agreement does not establish the following: '+positive}}}}
 inputsha=hashlib.sha256(b.canonical(inputs).encode()).hexdigest();assert inputsha==r['input_sha256']
 out['confirmation'].append({'id':r['id'],'input':inputs,'input_sha256':inputsha})
assert len(out['development'])==24 and len(out['confirmation'])==48
for name,value in [('preflight-inputs.json',out),('pre-gold-input-validation.json',validation)]:
 with (HERE/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write(chr(10))
print(json.dumps({'status':'LABEL_FREE_INPUTS_VALIDATED','development':24,'confirmation':48,'DEV_annotation_choices_accessed':0,'CONF_annotation_choices_accessed':0,'root_borrowed_source_hypothesis_definitions':True,'input_file_sha256':hashlib.sha256((HERE/'preflight-inputs.json').read_bytes()).hexdigest()}))

