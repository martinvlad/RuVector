"""Pure metadata merge only; no source/data/model imports or production modes."""
from __future__ import annotations
import copy

def same_fact(left,right):
 if type(left)is not type(right):return False
 if isinstance(left,dict):return set(left)==set(right)and all(same_fact(left[k],right[k])for k in left)
 if isinstance(left,list):return len(left)==len(right)and all(same_fact(a,b)for a,b in zip(left,right))
 return left==right

def merge_fragments(fragments):
 """Require exact overlap; merge public source refs by path without guessing."""
 answer={'plan_fields':{},'required_refs':{},'inherited_source_refs':[]}
 inherited={}
 for fragment in fragments:
  if not isinstance(fragment,dict)or not {'plan_fields','required_refs','inherited_source_refs'}<=set(fragment):raise ValueError('Exact metadata fragment fields required')
  for field in ('plan_fields','required_refs'):
   if not isinstance(fragment[field],dict):raise ValueError('Metadata dictionaries required')
   for key,value in fragment[field].items():
    if key in answer[field]and not same_fact(answer[field][key],value):raise ValueError('Conflicting exact metadata field: '+field+'.'+key)
    answer[field][key]=copy.deepcopy(value)
  for row in fragment['inherited_source_refs']:
   if not isinstance(row,dict)or set(row)!={'path','bytes','sha256'}or type(row['bytes'])is not int:raise ValueError('Canonical inherited public ref required')
   path=row['path']
   if path in inherited and not same_fact(inherited[path],row):raise ValueError('Conflicting inherited source identity')
   inherited[path]=copy.deepcopy(row)
 answer['inherited_source_refs']=[inherited[k]for k in sorted(inherited)]
 return answer
