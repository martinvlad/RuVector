"""Invented SOURCE then FINAL journal; no real owner, Git or scientific calls."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import base64,json,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
import publication_common as c
import mutation_guard as g

class TwoPhase(unittest.TestCase):
 def stage(self,w,phase,parent,source_receipt=None):
  stage=w/('stage-'+phase);stage.mkdir();prefix='e45-'+phase+'-g10';payload=('invented-'+phase).encode();request={'repository_full_name':c.REPO,'encoding':'utf-8','content':payload.decode()};blob=c.encoded(request);c.write(stage/'blob-0.json',blob)
  tree=c.encoded({'tree_elements':[{'path':c.SCOPE+'experiments/sota-2026-10-22/epoch45/invented.txt','mode':'100644','type':'blob','sha':c.git(payload)}]});c.write(stage/'tree-0.json',tree)
  m={'epoch':45,'phase':phase,'source_checkpoint':c.BASE,'source_parent':parent,'expected_source_root':'c'*40,'expected_final_root':'a'*40,'owner_sha256':'f'*64,'operational_binding_sha256':'e'*64,'mutation_ID_prefix':prefix,'blobs':[{'id':prefix+'-blob-0','file':'blob-0.json','bytes':len(blob),'sha256':c.sha(blob),'GitSHA':c.git(payload)}],'trees':[{'id':prefix+'-tree-0','file':'tree-0.json','bytes':len(tree),'sha256':c.sha(tree)}],'commit_message':'invented fixture','forbidden_Git_objects':sorted(c.FORBIDDEN_OBJECTS)}
  if source_receipt:m['actual_SOURCE_receipt']=source_receipt
  m['mutation_ID_order']=[r['id']for r in m['blobs']+m['trees']]+[prefix+'-commit',prefix+'-ref'];c.write(stage/'metadata.json',c.encoded(m));approval={'checks_passed':True,'publication_phase_allowed':True,'source_and_denylist_review_passed':True,'dual_unknown_denylist_reviewed':True,'stage_metadata_sha256':c.sha(c.body(stage/'metadata.json')),'expected_final_root_sha':m['expected_final_root'],'phase':phase,'original_blob5_execution':'UNKNOWN_PERMANENTLY','forbidden_Git_object_sha1':c.FORBIDDEN,'forbidden_Git_objects':sorted(c.FORBIDDEN_OBJECTS),'operational_binding_sha256':'e'*64};ap=w/(phase+'-approval.json');c.write(ap,c.encoded(approval));return m,SimpleNamespace(phase=phase,approval=ap,expected_approval_sha=c.sha(c.body(ap)),mode='guard',id=None,kind=None,payload=None)
 def run_phase(self,w,m,a,commit):
  g.main(a)
  for i,id in enumerate(m['mutation_ID_order']):
   kind=('create_blob','create_tree','create_commit','update_ref')[i];a.id=id;a.kind='mcp__codex_apps__github_'+kind
   a.mode='reserve';g.main(a);a.mode='intent';g.main(a)
   # Regression: response receives completed prefix plus exactly its own open intent.
   self.assertEqual(len(g.journal_rows())%2,1)
   result={'sha':m['blobs'][0]['GitSHA']}if i==0 else {'sha':'a'*40}if i==1 else {'sha':commit}if i==2 else {'success':True}
   raw={'structuredContent':result,'content':[]};c.write(w/'publication/requests'/(id+'.raw-tool-return.json'),c.encoded(raw));value={'ok':True,'result':result}
   if i==3:value['fresh_ref']={'ref':'refs/heads/'+c.BRANCH,'object':{'sha':commit}}
   a.payload=base64.b64encode(c.encoded(value)).decode();a.mode='response';g.main(a)
  a.mode='guard';g.main(a)
 def test_source_then_final(self):
  with tempfile.TemporaryDirectory(prefix='e45-two-phase-inert-')as d:
   w=Path(d)
   with patch.object(c,'W',w),patch.object(c,'held_owner',return_value={'pid':42}),patch.object(c,'OWNER_SHA','f'*64),patch.object(c,'OWNER_GENERATION',10),patch.object(c,'OPERATIONAL_SHA','e'*64):
    sm,sa=self.stage(w,'source',c.BASE);self.run_phase(w,sm,sa,'b'*40)
    sr={'epoch':45,'phase':'source','commit':'b'*40,'parent':c.BASE,'verified_actual_full_tree':True,'stage_metadata_sha256':c.sha(c.body(w/'stage-source/metadata.json'))};rp=w/'source-receipt.json';c.write(rp,c.encoded(sr));fm,fa=self.stage(w,'final','b'*40,c.pin(rp));self.run_phase(w,fm,fa,'d'*40)
    rows=g.journal_rows();self.assertEqual(len(rows),16);self.assertEqual([r['publication_phase']for r in rows],['source']*8+['final']*8);self.assertEqual(rows[-1]['payload']['result'],{'success':True});self.assertEqual(rows[-1]['payload']['fresh_ref']['object']['sha'],'d'*40)
    fa.id=fm['mutation_ID_order'][-1];fa.kind='mcp__codex_apps__github_update_ref';fa.mode='reserve'
    with self.assertRaises(ValueError):g.main(fa)
    # Existing final rows cannot be mistaken for a source-only prefix.
    sa.mode='guard'
    with self.assertRaises(ValueError):g.main(sa)
 def test_own_intent_and_uncertain_prefix(self):
  from future_response_protocol import response_intent
  good=[{'phase':'intent','id':'previous'},{'phase':'response','id':'previous','payload':{'ok':True}},{'phase':'intent','id':'own','kind':'blob'}];self.assertEqual(response_intent(good,'own','blob')['id'],'own')
  for bad in (good[:-1],good+[{'phase':'intent','id':'other'}],good[:1]+good[-1:]):
   with self.assertRaises(ValueError):response_intent(bad,'own','blob')
if __name__=='__main__':unittest.main()
