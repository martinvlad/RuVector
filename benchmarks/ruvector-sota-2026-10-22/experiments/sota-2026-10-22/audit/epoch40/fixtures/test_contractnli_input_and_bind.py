"""Unrelated input receipt and publication-only source contracts."""
import copy,json,tempfile,unittest
from pathlib import Path
import contractnli_io as I
import contractnli_input_audit as A
import contractnli_scorer as S
class InputAndBind(unittest.TestCase):
 def test_saved_whole_claim_prefix_and_offset_audit(self):
  premise='Fee is 3.';claim='A fee applies.';record={'claim':claim,'evidence':[{'unit_id':0,'sentence':premise,'start':0,'end':len(premise)}]};full={'input_ids':[0,10,11,12,2,20,21,2],'attention_mask':[1]*8};consumed={'input_ids':[0,10,11,2,20,21,2],'attention_mask':[1]*7};fs=[None,0,0,0,None,1,1,None];cs=[None,0,0,None,1,1,None];fo=[[0,0],[0,3],[4,6],[7,9],[0,0],[0,1],[2,14],[0,0]];co=[[0,0],[0,3],[4,6],[0,0],[0,1],[2,14],[0,0]];want={'full_premise_sha256':A.digest(premise),'claim_sha256':A.digest(claim),'ordered_unit_ids':[0],'full_joint_tokens':8,'joint_tokens':7,'full_premise_tokens':3,'consumed_premise_tokens':2,'full_claim_tokens':2,'consumed_claim_tokens':2,'claim_complete':True,'premise_truncated':True,'full_input_features_sha256':A.digest(full),'consumed_input_features_sha256':A.digest(consumed),'consumed_premise_tokens_sha256':A.digest([10,11]),'consumed_claim_tokens_sha256':A.digest([20,21]),'full_numeric_literal_count':1,'retained_numeric_literal_count':0,'omitted_numeric_literal_count':1,'numeric_literal_coverage':0.0};r={'readout_id':'toy::b354_source_order','model_tag':'b354','raw_native_logits':[1.,0.,-1.],'input_audit':want};saved=dict(r,premise=premise,claim=claim,full_features=full,features=consumed,sequence_ids=cs,full_sequence_ids=fs,offset_mapping=co,full_offsets=fo);self.assertEqual(A.check_saved_input(record,'b354_source_order',r,saved),want);saved['features']['input_ids'][-2]=99
  with self.assertRaises(ValueError):A.check_saved_input(record,'b354_source_order',r,saved)
 def test_bind_preserves_every_field_and_failure_custody(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);v={'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','checks_passed':False,'dev_passed':False,'evaluation_executed':False,'source_plan_sha256':'a'*64,'label_custody':{'semantic_label_decodes':None},'extra_preserved':['fixture']};vr=I.put(root/'replay.json',v);rr=I.put(root/'result.json',dict(v,publication_checkpoint={'qualification_replay':vr}));r=S.bind(vr,rr,root);self.assertTrue(r['publication_binding_checks_passed']);self.assertFalse(r['evaluated_integrity_checks_passed']);self.assertFalse(r['evaluation_executed']);bad=dict(v);bad['label_custody']={'semantic_label_decodes':0};br=I.put(root/'bad.json',dict(bad,publication_checkpoint={'qualification_replay':vr}))
   with self.assertRaises(ValueError):S.bind(vr,br,root)
 def test_bind_type_sensitive_nested_json_facts(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);v={'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','checks_passed':False,'dev_passed':False,'evaluation_executed':False,'source_plan_sha256':'a'*64,'nested':{'rows':[{'flag':False,'count':1}]}};vr=I.put(root/'replay.json',v)
   for i,change in enumerate([{'rows':[{'flag':0,'count':1}]},{'rows':[{'flag':False,'count':True}]},{'rows':{'flag':False,'count':1}},{'rows':[{'flag':False}]}]):
    mutated=dict(v,nested=change,publication_checkpoint={'qualification_replay':vr});rr=I.put(root/f'mutated{i}.json',mutated)
    with self.assertRaises(ValueError):S.bind(vr,rr,root)
if __name__=='__main__':unittest.main()
