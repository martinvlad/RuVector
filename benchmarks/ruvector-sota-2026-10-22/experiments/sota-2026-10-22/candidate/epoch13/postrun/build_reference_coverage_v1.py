"""Exact exposed-DEV annotation intersections on saved selected contexts only."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,statistics
PIN='ed8178dd1aa820590f7859f755c3f3471d9f1461bb17fdf37f97405c11f40218'
ARM={'ruvector_top2':'ruvector_top2','same_nli_lexical_top2':'lexical_top2','same_nli_positional_first2':'positional_first2'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def merge(spans):
 out=[]
 for a,b in sorted(spans):
  if not 0<=a<b:raise ValueError('Invalid reference span')
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return out
def length(spans):return sum(b-a for a,b in merge(spans)) if spans else 0
def intersection(left,right):return length([[max(a,c),min(b,d)] for a,b in merge(left) for c,d in merge(right) if max(a,c)<min(b,d)])
def analyze(records,projection):
 if len(records)!=24 or len(projection['records'])!=24 or projection['reserved_confirmation_annotations_accessed']:
  raise ValueError('Only exposedDEV24 projection allowed')
 refs={r['id']:r for r in projection['records']}
 if set(refs)!={r['id'] for r in records}:raise ValueError('Projection IDs differ')
 examples=[]
 for row in records:
  ref=refs[row['id']];state=row['input']['state']
  if hashlib.sha256(state.encode()).hexdigest()!=ref['source_state_sha256'] or row['evaluation']['original_threeway_label']!=ref['original_threeway_label']:
   raise ValueError('Exposed DEV state/label identity differs')
  spans=ref['original_gold_character_spans']
  if any(b>len(state) for a,b in spans):raise ValueError('Reference span outside exact source')
  total=length(spans)
  for name,alias in ARM.items():
   res=row['response'];arm=res['diagnostics']['decision']['arms'][alias];selected=arm['coverage']['selected_source_spans']
   response=res if name=='ruvector_top2' else res['ablation_responses'][name]
   kept=intersection(spans,selected);any_overlap=kept>0
   every_span_overlap=bool(spans) and all(intersection([[a,b]],selected)>0 for a,b in spans)
   full=bool(spans) and kept==total
   examples.append({'id':row['id'],'source_group':row['source_group'],'arm':name,'gold_typed':ref['original_threeway_label'],
                    'original_reference_span_ids':ref['original_gold_span_ids'],'reference_spans':spans,
                    'reference_union_characters':total,'retained_reference_union_characters':kept,
                    'reference_character_fraction':kept/total if total else None,'any_span_overlap':any_overlap,
                    'every_span_overlap':every_span_overlap,'all_reference_characters_retained':full,
                    'binary_correct':response['answers']['decision']['choice']==row['evaluation']['gold'],
                    'typed_prediction':min(arm['decoding']['raw_threeway_probabilities'],key=lambda k:(-arm['decoding']['raw_threeway_probabilities'][k],k))})
 summary={}
 for arm in ARM:
  rows=[e for e in examples if e['arm']==arm];annotated=[e for e in rows if e['reference_union_characters']>0]
  full=[e for e in annotated if e['all_reference_characters_retained']]
  summary[arm]={'n':24,'queries_with_references':len(annotated),'queries_without_references':len(rows)-len(annotated),
                'any_span_overlap_n':sum(e['any_span_overlap'] for e in annotated),'every_span_overlap_n':sum(e['every_span_overlap'] for e in annotated),
                'all_reference_characters_retained_n':len(full),'fully_retained_binary_correct_n':sum(e['binary_correct'] for e in full),
                'fully_retained_binary_wrong_ids':[e['id'] for e in full if not e['binary_correct']],
                'fully_retained_typed_gold_counts':dict(Counter(e['gold_typed'] for e in full)),
                'fully_retained_typed_correct_n':sum(e['typed_prediction']==e['gold_typed'] for e in full),
                'mean_per_query_reference_character_fraction':statistics.mean(e['reference_character_fraction'] for e in annotated),
                'sum_reference_characters_per_query':sum(e['reference_union_characters'] for e in annotated),
                'sum_retained_reference_characters_per_query':sum(e['retained_reference_union_characters'] for e in annotated)}
 return {'schema_version':1,'status':'EXPOSED_DEV_REFERENCE_COVERAGE_ONLY','n':24,'document_groups':8,'summary':summary,'examples':examples,
         'scope':'Exact intersection of original source annotation character unions and saved selected source spans on already exposedDEV24 only. Repeated per-query reference counts. Annotation references may be alternatives or incomplete; partial or full retention proves neither entailment, contradiction nor sufficient evidence. Retrieval miss cannot establish NotMentioned. No annotation-conditioned inference or fitting.',
         'new_model_calls':0,'new_native_calls':0,'new_fits':0,'confirmation_labels_or_annotations_read':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--records',type=Path,required=True);p.add_argument('--projection',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if sha(a.projection)!=PIN:raise ValueError('Frozen DEV-only projection hash differs')
 projection=json.loads(a.projection.read_text())
 if projection['actual_records_sha256']!=sha(a.records):raise ValueError('Actual records identity differs')
 d=analyze([json.loads(x) for x in a.records.read_text().splitlines() if x],projection);d.update(saved_records_sha256=sha(a.records),DEV_only_projection_sha256=PIN)
 with a.out.open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'reference_coverage_sha256':sha(a.out),'summary':d['summary']}))
