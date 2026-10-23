"""Pure/injected engineering only. Zero neural/native sessions or benchmark data."""
import collections
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent

def module(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE/file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

M = module('epoch18_test_reader', 'torch_reader.py')
C = module('epoch18_test_context', 'context.py')
R = module('epoch18_test_runtime', 'runtime.py')
A = module('epoch18_test_acquisition', 'acquire_assets.py')


class CharacterTokenizer:
    def __init__(self, multiplier=1, hypothesis_extra=0):
        self.multiplier, self.hypothesis_extra = multiplier, hypothesis_extra
    def encode(self, text, pair=None, add_special_tokens=True):
        content = len(text)*self.multiplier + ((len(pair)+self.hypothesis_extra) if pair is not None else 0)
        n = content + ((3 if pair is not None else 2) if add_special_tokens else 0)
        return SimpleNamespace(ids=list(range(n)), offsets=[(i,i+1) for i in range(len(text))],
                               attention_mask=[1]*n, type_ids=[0]*(n-1)+[1])


def document(parts):
    state, units, start = ''.join(parts), [], 0
    for index, part in enumerate(parts):
        units.append({'id':index,'start':start,'end':start+len(part),
                      'paragraph_id':index,'token_fallback':False})
        start += len(part)
    return state, units


class MappingTests(unittest.TestCase):
    def test_every_label_permutation_uses_source_mapping(self):
        raw = {'entailment':2.5,'contradiction':-.7,'neutral':.3}
        expected = [math.exp(raw[x]-2.5) for x in ('entailment','contradiction','neutral')]
        expected = [x/sum(expected) for x in expected]
        for order in itertools.permutations(raw):
            config = {'id2label':{str(i):name.upper() for i,name in enumerate(order)}}
            typed = M.threeway_probabilities([raw[name] for name in order], M.label_indices(config))
            self.assertEqual(list(typed), M.TYPED_ORDER)
            for got, want in zip(typed.values(), expected):
                self.assertAlmostEqual(got,want,places=14)
            self.assertEqual(M.typed_prediction(typed),'Entailment')
    def test_invalid_label_identity_and_nonfinite_logits_fail(self):
        for config in ({'id2label':{'0':'E','1':'N','2':'C'}},
                       {'id2label':{'0':'entailment','1':'entailment','2':'neutral'}},
                       {'id2label':{'0':'entailment','1':'neutral','3':'contradiction'}}):
            with self.assertRaises(ValueError): M.label_indices(config)
        mapping = {'entailment':2,'neutral':1,'contradiction':0}
        for logits in ([1,2], [0,float('nan'),1], [float('inf'),0,1]):
            with self.assertRaises(ValueError): M.threeway_probabilities(logits,mapping)
    def test_typed_tie_fixed_order_and_binary_exact_half_tie_no(self):
        typed = dict(zip(M.TYPED_ORDER,[.5,.5,0.]))
        self.assertEqual(M.typed_prediction(typed),'Entailment')
        answer = R.answer_with_typed({'Yes':.5,'No':.5}, {'raw_threeway_probabilities':typed}, 'test','rev','fixture')
        self.assertEqual(answer['choice'],'No')
        self.assertEqual(answer['typed_prediction'],'Entailment')
    def test_large_logits_stable_without_rounding_or_repair(self):
        typed=M.threeway_probabilities([10000,9999,-10000],{'entailment':2,'neutral':1,'contradiction':0})
        self.assertTrue(all(math.isfinite(x) for x in typed.values()))
        self.assertAlmostEqual(sum(typed.values()),1.,places=15)
        self.assertEqual(typed['Entailment'],0.)


class ContextTests(unittest.TestCase):
    def test_old_only_budget_conflict_rejected_before_clipping(self):
        state,units=document(['A complete source clause.'])
        with self.assertRaises(ValueError):
            C.pack(state,units,[0],'claim',CharacterTokenizer(),CharacterTokenizer(hypothesis_extra=510))
    def test_priority_budget_is_max_both_complete_units(self):
        state,units=document(['"Recipient" means '+('x'*65)])
        result=C.select_prelude(state,units,CharacterTokenizer(),CharacterTokenizer(2))
        self.assertEqual(result['selected_unit_ids'],[])
        self.assertFalse(result['candidate_attempts'][0]['accepted'])
    def test_same_exact_source_numeric_retention_and_dual_trace(self):
        state,units=document(['"Recipient" means Acme.\n\n','Use $5 each day.\n\n','Keep 20 days.'])
        new,old=CharacterTokenizer(),CharacterTokenizer(2)
        priority=C.select_prelude(state,units,new,old)
        premise,cov=C.pack(state,units,[2,1,0],'full H',new,old,prelude=priority,pair_cap=150)
        expected='\n\n'.join(state[a:b] for a,b in cov['selected_source_spans'])
        self.assertEqual(premise,expected)
        self.assertEqual(cov['joint_pair_tokens'],max(cov['new_reader_joint_pair_tokens'],cov['previous_reader_joint_pair_tokens']))
        self.assertEqual(cov['numeric_mentions_retained']+cov['numeric_mentions_omitted'],2)
        self.assertTrue(all(x['candidate_pair_tokens']==max(x['candidate_new_reader_pair_tokens'],x['candidate_previous_reader_pair_tokens']) for x in cov['packing_attempts']))
        self.assertEqual(cov['definition_priority'],priority)
    def test_partition_conserves_unicode_source_and_fallback_offsets(self):
        state='α “秘密” remains protected.\n\nSecond; third.  '
        t=CharacterTokenizer()
        units=C.partition(state,t,CharacterTokenizer(2),t,target=16,nli_cap=40,bge_cap=80)
        self.assertEqual(''.join(state[x['start']:x['end']] for x in units),state)
    def test_previous_reader_budget_changes_admission_without_rewrite(self):
        state,units=document(['One long original clause.\n\n','Two extra original clauses.'])
        premise,cov=C.pack(state,units,[1,0],'H',CharacterTokenizer(),CharacterTokenizer(2),pair_cap=65)
        self.assertEqual(premise,state[units[1]['start']:units[1]['end']])
        self.assertEqual(cov['selected_chunk_ids_source_order'],[1])
        self.assertFalse(cov['selected_evidence_truncated'])


class InjectedReader:
    def __init__(self,tokenizer,counters,new):
        self.tokenizer,self.counters,self.new,self.calls=tokenizer,counters,new,[]
    def decode(self,premise,hypothesis):
        self.calls.append((premise,hypothesis))
        for suffix in ('attempted','completed'):
            self.counters['nli_forward_pairs_'+suffix]+=1
            if self.new:self.counters['new_reader_forward_pairs_'+suffix]+=1
        typed=dict(zip(M.TYPED_ORDER,[.6,.1,.3]))
        digest=hashlib.sha256(json.dumps({'premise':premise,'hypothesis':hypothesis},ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        return {'Yes':.6,'No':.4},{'raw_threeway_probabilities':typed,'input_text_sha256':digest,'injected_engineering_only':True}


class InjectedNative:
    def __init__(self):self.calls=[]
    def predict(self,state,questions):
        self.calls.append((state,questions))
        return {'answers':{k:R.HELPERS.answer_for({'Yes':.6,'No':.4}) for k in questions},'usage':{'injected_engineering_only':True}}


class RuntimeTests(unittest.TestCase):
    def engine(self):
        e=R.CandidateEngine.__new__(R.CandidateEngine)
        e.config={'source_partition':{'target':32,'nli_cap':64,'bge_cap':256,'max_units':192},
                  'ranking_depth':40,'joint_pair_token_cap':512,'query_prefix':'prefix ',
                  'legacy_arm_names':'Injected only'}
        e.counters=collections.defaultdict(int)
        e.nli=InjectedReader(CharacterTokenizer(),e.counters,True)
        e.previous_nli=InjectedReader(CharacterTokenizer(2),e.counters,False)
        e.bge=SimpleNamespace(raw_tokenizer=CharacterTokenizer())
        e.base=InjectedNative();e.last_usage=None
        e.retrieve=lambda chunks,h:(list(reversed(range(min(40,len(chunks))))),{'injected_engineering_only':True})
        return e
    def test_actual_old_control_same_text_and_exact_four_forwards(self):
        e=self.engine()
        q={'p':{'type':'choice','criteria':{'Yes':'Records stay protected.','No':'Other.'}}}
        result=e.predict('This agreement is between Acme and Beta.\n\nKeep records for 20 days.',q)
        primary=result['diagnostics']['p']['arms']['ruvector_top2']
        self.assertEqual(len(e.nli.calls),3);self.assertEqual(len(e.previous_nli.calls),1)
        self.assertEqual(e.previous_nli.calls[0],(primary['premise'],primary['hypothesis']))
        self.assertEqual(e.base.calls[0],(primary['premise'],q))
        for prefix,n in [('nli',4),('new_reader',3),('previous_reader',1)]:
            for suffix in ('attempted','completed'):
                self.assertEqual(e.counters[prefix+'_forward_pairs_'+suffix],n)
        self.assertEqual(primary['new_decoding']['input_text_sha256'],primary['previous_decoding']['input_text_sha256'])
        self.assertEqual(set(result['ablation_responses']),{'same_nli_lexical_top2','same_nli_positional_first2','previous_reader_native_same_premise'})
        self.assertEqual(result['answers']['p']['typed_prediction'],'Entailment')
    def test_all_question_validation_precedes_any_call(self):
        e=self.engine()
        with self.assertRaises(ValueError):e.predict('Source text.',{'p':{'type':'bogus'}})
        self.assertFalse(e.nli.calls);self.assertFalse(e.previous_nli.calls);self.assertFalse(e.base.calls)
        self.assertEqual(e.counters['context_partitions_attempted'],0)
    def test_either_reader_whole_hypothesis_guard_precedes_any_call(self):
        e=self.engine();e.previous_nli.tokenizer=CharacterTokenizer(hypothesis_extra=510)
        with self.assertRaises(ValueError):e.predict('Source text.',{'p':{'type':'choice','criteria':{'Yes':'Full H.','No':'Other.'}}})
        self.assertFalse(e.nli.calls);self.assertFalse(e.previous_nli.calls);self.assertFalse(e.base.calls)


class AcquisitionTests(unittest.TestCase):
    def test_exact_spec_and_mutation_rejection(self):
        value=A.load_spec()
        self.assertEqual(len(value['assets']),6)
        value['assets'][0]['remote_path']='../escape'
        with self.assertRaises(ValueError):A.validate_spec(value)
    def test_identity_mismatch_fails(self):
        import io
        with self.assertRaises(ValueError):A.identity(io.BytesIO(b'bad'),{'bytes':3,'sha256':'0'*64})




class ConstructorBindingTests(unittest.TestCase):
    def test_shared_actual17_asset_namespace_and_new18_role_config(self):
        seen = {}
        old_receipt = {'repo':'cross-encoder/nli-deberta-v3-large','revision':'PREVIOUS_FIXTURE'}
        new_receipt = {'repo':M.REPO,'revision':M.REVISION}
        def old_construct(engine):
            engine.counters={};engine.receipt={};engine.native_pid=0
            engine.nli=SimpleNamespace(receipt=old_receipt)
            engine.base=SimpleNamespace(close=lambda:None)
        def new_construct(folder,counters):
            seen['folder']=Path(folder)
            return SimpleNamespace(receipt=new_receipt)
        with mock.patch.object(R.OLD.CandidateEngine,'__init__',old_construct), \
             mock.patch.object(R.OLD,'verify_file')as assets, \
             mock.patch.object(R.READER,'SingletonNli',side_effect=new_construct), \
             mock.patch.object(R.OLD.FROZEN4,'resource_snapshot',return_value={'engineering_fixture':True}):
            engine=R.CandidateEngine()
        self.assertEqual(assets.call_count,6)
        self.assertEqual(seen['folder'],HERE.parent/'epoch17/assets/official-deberta-v2-xlarge-mnli')
        self.assertEqual(engine.receipt['nli'],old_receipt)
        self.assertEqual(engine.receipt['previous_reader'],old_receipt)
        self.assertEqual(engine.receipt['new_reader'],new_receipt)
        self.assertEqual(engine.config['epoch'],18)
        self.assertTrue(engine.config['data_contract_path'].endswith('epoch18/data-contract.pre-label.json'))
        self.assertEqual(engine.config['prelabel_operational_max_decision_seconds'],30)
        engine.close()

    def test_wrong_config_hash_blocks_before_any_constructor(self):
        with mock.patch.object(R,'CONFIG_SHA256','0'*64), \
             mock.patch.object(R.OLD.CandidateEngine,'__init__')as old:
            with self.assertRaises(ValueError):R.CandidateEngine()
            old.assert_not_called()


if __name__=='__main__':unittest.main()
