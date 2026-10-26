"""E47 Git response shape validation; never executes or replays requests."""
import re
import json
from archive_protocol import require,FORBIDDEN_OBJECTS

def acknowledged_sha(kind,result,request,fresh_ref=None):
 require(isinstance(result,dict),'Typed Git result required')
 if kind.endswith('github_update_ref'):
  require(request['branch_name']=='benchmarks/ruvector-sota-2026-10-22'and request['force']is False,'Dedicated non-force CAS')
  if set(result)=={'success'}and result['success']is True:
   require(isinstance(fresh_ref,dict)and fresh_ref.get('ref')=='refs/heads/'+request['branch_name']and isinstance(fresh_ref.get('object'),dict)and fresh_ref['object'].get('sha')==request['sha'],'Bare success requires fresh post-CAS GET matching exact new commit')
   return None
  require(result.get('ref')=='refs/heads/'+request['branch_name'],'Dedicated branch reference ACK required')
  obj=result.get('object');require(isinstance(obj,dict),'Branch object ACK required');value=obj.get('sha')
  require(value==request['sha'],'Branch object ACK differs from exact reserved commit')
 else:value=result.get('sha')
 require(isinstance(value,str)and re.fullmatch(r'[0-9a-f]{40}',value)and value not in FORBIDDEN_OBJECTS,'Typed nonforbidden Git object SHA required')
 return value

def persist_validated_response(path,raw,kind,request,persist,record,expected_blob=None):
 """Retain exact passed bytes before validation; record only a validated response."""
 persist(path,raw)
 payload=json.loads(raw);require(type(payload.get('ok'))is bool,'Typed response status')
 if payload['ok']:
  ack=acknowledged_sha(kind,payload.get('result'),request,payload.get('fresh_ref'))
  if expected_blob is not None:require(ack==expected_blob,'Blob ACK mismatch; retained response is not a journal ACK')
 record(payload)
 return payload
