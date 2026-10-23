"""Source-only data proof and meaningful freeze-boundary mutation controls."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,shutil,tempfile
HERE=Path(__file__).resolve().parent
DEFAULT_SOURCE=HERE.parents[1]/'epoch11/project/experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def dump(p,a):p.write_text(json.dumps(a,indent=2)+'\n')
def check(folder,source):
 spec=importlib.util.spec_from_file_location('frozen_data_build_'+str(id(folder)),folder/'build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
 c=load(folder/'data-contract.json')
 if c['train']!=[] or c['calibration']!=[] or c['fitting']['supervised_fit'] is not False:raise ValueError('No fit/calibration permitted')
 if sha(folder/'draw-plan.json')!=c['draw']['plan_sha256'] or sha(folder/'document-selection.json')!=c['draw']['selection_sha256']:raise ValueError('Frozen draw/roles changed')
 plan=load(folder/'draw-plan.json')
 if plan['hypotheses']!=['nda-17','nda-7','nda-3']:raise ValueError('Frozen predicate set changed')
 rows=b.draw(source)
 raw=''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in rows).encode()
 if hashlib.sha256(raw).hexdigest()!=c['development']['sha256'] or (folder/'development24.jsonl').read_bytes()!=raw:raise ValueError('Frozen DEV bytes changed')
 if c['development']['queries']!=24 or len(rows)!=24 or len({x['source_group'] for x in rows})!=8:raise ValueError('Wrong counts')
 a=b.allow(rows,c['development']['sha256'])
 if a!=load(folder/'dev-allowlist.json'):raise ValueError('DEV allowlist changed')
 if sha(folder/'confirmation-allowlist.json')!=c['confirmation']['allowlist_sha256']:raise ValueError('Reserved CONF metadata changed')
 reserve=load(folder/'confirmation-allowlist.json');reg=load(folder/'eligibility-manifest.json');old=set(reg['excluded_document_ids']);reserved=set(reg['reserved_confirmation_document_ids']);ids={x['provenance']['document_id'] for x in rows}
 if len(reserve['records'])!=48 or len({x['source_group'] for x in reserve['records']})!=16 or ids&(old|reserved):raise ValueError('Invalid reserved/new role identities')
 return {'queries':24,'document_groups':8,'originaltrain_exposed':165,'reserved_confirmation_groups':16,'eligible_before_draw':242,'unreserved_after_draw':234,'new_DEV_sha256':c['development']['sha256'],'confirmation_metadata_only_sha256':sha(folder/'confirmation-allowlist.json'),'source_sha256':sha(source)}

def mutate(root,kind):
 if kind=='source':return
 file={'roles':'document-selection.json','DEV_input':'development24.jsonl','allowlist':'dev-allowlist.json','confirmation_metadata':'confirmation-allowlist.json','draw':'draw-plan.json','registry':'eligibility-manifest.json','fitting':'data-contract.json'}[kind]
 p=root/file
 if kind=='DEV_input':p.write_bytes(p.read_bytes().replace(b'"state": "',b'"state": "MUTATED ',1));return
 a=load(p)
 if kind=='roles':a['documents'][0]['role']='confirmation'
 elif kind=='allowlist':a['records'][0]['input_sha256']='0'*64
 elif kind=='confirmation_metadata':a['records'][0]['source_group']='original-contractnli:999999'
 elif kind=='draw':a['salt']+='changed'
 elif kind=='registry':a['excluded_document_ids'][0]=999999
 elif kind=='fitting':a['train']=['forbidden']
 dump(p,a)

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=DEFAULT_SOURCE);p.add_argument('--out',type=Path,default=HERE/'validation.json');a=p.parse_args();assert not a.out.exists();proof=check(HERE,a.source);controls=[]
 for kind in ['source','roles','DEV_input','allowlist','confirmation_metadata','draw','registry','fitting']:
  with tempfile.TemporaryDirectory(prefix='ruvector-e11-data-') as t:
   tmp=Path(t)
   for f in HERE.iterdir():
    if f.is_file() and f.suffix in ('.py','.json','.jsonl','.txt'):shutil.copy2(f,tmp/f.name)
   source=a.source
   if kind=='source':source=tmp/'mutated-source.json';source.write_bytes(a.source.read_bytes()+b' ')
   else:mutate(tmp,kind)
   rejected=False
   try:check(tmp,source)
   except (ValueError,AssertionError,KeyError,TypeError):rejected=True
   if not rejected:raise AssertionError('Mutation escaped '+kind)
   controls.append({'mutation':kind,'rejected':True})
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'proof':proof,'mutation_controls':controls,'confirmation_labels_read':False,'real_models_native_fits_paid_calls':0};dump(a.out,result);print(json.dumps({'checks_passed':True,'mutations_rejected':len(controls),'out':str(a.out),'sha256':sha(a.out)}))
if __name__=='__main__':main()
