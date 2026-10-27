"""Stdlib-only invented encoding tests; no real tokenizer/model/native imports."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from collections import Counter
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import inherited_packing as packing
import inherited_reader as reader
import worker
import io_guard
import search_policy


def wordpiece_fake(premise,claim):
    # Deliberately invented, whitespace-based token counts, engineering fixture only.
    n=len(claim.split());m=len(premise.split());return {'input_ids':[101]+[200]*n+[102]+[201]*m+[102],
        'attention_mask':[1]*(n+m+3),'token_type_ids':[0]*(n+2)+[1]*(m+1)}


def simple_bank(text,parts=None):
    parts=parts or [text];off=0;units=[]
    for i,s in enumerate(parts):units.append(dict(unit_id=i,start=off,end=off+len(s),sentence=s));off+=len(s)
    doc={'document_id':'invented:inert','evidence':units,'source_document_sha256':packing.digest(text)}
    return {'documents':[doc],'cases':[{'id':'invented:'+str(i),'document_id':'invented:inert','hypothesis_id':slot,'claim':'invented query'} for i,slot in enumerate(worker.SLOTS)]}


class SourceContractTests(unittest.TestCase):
    def test_supervisor_exact_guardian20_fence(self):
        tree=ast.parse((HERE/'supervisor.py').read_text())
        check=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='fence')
        source=ast.get_source_segment((HERE/'supervisor.py').read_text(),check)
        for required in ["owner['epoch']==55", "owner['generation']==20", "owner['pid']==177383",
                         "owner['startticks']==42200361", "'LIVE_SCOPED_GUARDIAN20'"]:
            self.assertIn(required,source)
        self.assertNotIn('41273162',source);self.assertNotIn('GUARDIAN19',source)
    def test_denied_open_all_original_suffixes_still_fail_closed(self):
        counts=Counter();guard=io_guard.DeniedOpenAudit(counts,maximum_events=3)
        for suffix in io_guard.SUFFIXES:
            with self.assertRaisesRegex(RuntimeError,'ENGINEERING_MODEL_WEIGHTS_AND_CORPUS_ARCHIVES_FORBIDDEN'):
                guard('open',('/invented/inert-only'+suffix,'r',0))
        self.assertEqual(counts['forbidden_model_or_archive_file_access_attempts'],5)
        self.assertEqual(len(guard.events),3);self.assertEqual(guard.overflow,2)
        self.assertTrue(all(e['denied_before_OS_open'] for e in guard.events))
        self.assertNotIn('/invented/inert-only',json.dumps(guard.receipt()))
    def test_absent_zip_policy_removes_only_frozen_entry_retains_deny(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=str(Path(folder)/('python%d%d.zip'%sys.version_info[:2]))
            with mock.patch.object(sys,'base_prefix',folder),mock.patch.object(sys,'path',[str(HERE),archive,'unchanged-tail']):
                row={'sys_path_index':1,**search_policy.canonical_fingerprint(archive)}
                policy={'kind':'REMOVE_EXACT_PROVEN_ABSENT_INTERPRETER_ZIP_SEARCH_ENTRY',
                        'archive_access_authorized':False,'suffix_denies_unchanged':True,'entries':[row]}
                result=search_policy.apply_exact_absent_interpreter_zip_policy(policy)
                self.assertEqual(sys.path,[str(HERE),'unchanged-tail'])
                self.assertTrue(result['all_suffix_matching_opens_still_denied'])
                guard=io_guard.DeniedOpenAudit(Counter())
                with self.assertRaises(RuntimeError):guard('open',(archive,'rb',0))
    def test_existing_zip_policy_rejected_without_path_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder)/('python%d%d.zip'%sys.version_info[:2]);archive.write_bytes(b'inert archive marker')
            with mock.patch.object(sys,'base_prefix',folder),mock.patch.object(sys,'path',[str(archive)]):
                row={'sys_path_index':0,**search_policy.canonical_fingerprint(str(archive))}
                policy={'kind':'REMOVE_EXACT_PROVEN_ABSENT_INTERPRETER_ZIP_SEARCH_ENTRY',
                        'archive_access_authorized':False,'suffix_denies_unchanged':True,'entries':[row]}
                with self.assertRaisesRegex(ValueError,'EXACT_ABSENT_INTERPRETER_ZIP_CANONICAL_IDENTITY'):
                    search_policy.apply_exact_absent_interpreter_zip_policy(policy)
                self.assertEqual(sys.path,[str(archive)])
    def test_absent_zip_canonical_escape_rejected(self):
        with tempfile.TemporaryDirectory() as folder,tempfile.TemporaryDirectory() as outside:
            link=Path(folder)/'escape';link.symlink_to(outside,target_is_directory=True)
            archive=str(link/('python%d%d.zip'%sys.version_info[:2]))
            with mock.patch.object(sys,'base_prefix',folder),mock.patch.object(sys,'path',[archive]):
                row={'sys_path_index':0,**search_policy.canonical_fingerprint(archive)}
                self.assertTrue(row['inside_interpreter_base_prefix'])
                self.assertFalse(row['canonical_inside_interpreter_base_prefix'])
                policy={'kind':'REMOVE_EXACT_PROVEN_ABSENT_INTERPRETER_ZIP_SEARCH_ENTRY',
                        'archive_access_authorized':False,'suffix_denies_unchanged':True,'entries':[row]}
                with self.assertRaisesRegex(ValueError,'EXACT_ABSENT_INTERPRETER_ZIP_CANONICAL_IDENTITY'):
                    search_policy.apply_exact_absent_interpreter_zip_policy(policy)
    def test_changed_absent_zip_hash_rejected_without_path_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=str(Path(folder)/('python%d%d.zip'%sys.version_info[:2]))
            with mock.patch.object(sys,'base_prefix',folder),mock.patch.object(sys,'path',[archive]):
                row={'sys_path_index':0,**search_policy.canonical_fingerprint(archive)};row['path_sha256']='0'*64
                policy={'kind':'REMOVE_EXACT_PROVEN_ABSENT_INTERPRETER_ZIP_SEARCH_ENTRY',
                        'archive_access_authorized':False,'suffix_denies_unchanged':True,'entries':[row]}
                with self.assertRaisesRegex(ValueError,'EXACT_ABSENT_INTERPRETER_ZIP_CANONICAL_IDENTITY'):
                    search_policy.apply_exact_absent_interpreter_zip_policy(policy)
                self.assertEqual(sys.path,[archive])
    def test_headroom_precedes_version_policy_and_science(self):
        s=(HERE/'worker.py').read_text()
        point=s.index("baseline=memory_snapshot();")
        self.assertLess(point,s.index("raw['metadata_search_policy']=apply_exact_absent_interpreter_zip_policy"))
        self.assertLess(point,s.index("for package,version in plan['runtime_versions'].items():"))
        self.assertLess(point,s.index("progress('TOKENIZER_INITIALIZE_BEFORE')"))
    def test_import_does_not_load_runtime(self):
        for name in ['transformers','torch','tokenizers','onnxruntime','numpy']:
            self.assertNotIn(name,sys.modules)
    def test_delegate_exact_original_methods(self):
        self.assertIs(worker.TokenizerOnlyCapture.tokenize,reader.Reader.tokenize)
        self.assertIs(worker.TokenizerOnlyCapture.hypothesis_pair_capacity,reader.Reader.hypothesis_pair_capacity)
    def test_no_reader_constructor_or_score_call(self):
        tree=ast.parse((HERE/'worker.py').read_text())
        calls=[x for x in ast.walk(tree) if isinstance(x,ast.Call)]
        self.assertFalse(any(isinstance(x.func,ast.Name) and x.func.id=='Reader' for x in calls))
        self.assertFalse(any(isinstance(x.func,ast.Attribute) and x.func.attr=='score' for x in calls))
    def test_fixture_role_validation(self):
        f=json.loads((HERE/'authored_fixtures.json').read_text());bank,docs=worker.validate_fixture(f)
        self.assertEqual(len(bank['cases']),12);self.assertEqual(len(docs),4)
        self.assertEqual(bank['role'],'engineering')
        self.assertTrue(all(c['id'].startswith('authored:e55:') for c in bank['cases']))
    def test_no_confirmation_role(self):
        f=json.loads((HERE/'authored_fixtures.json').read_text());f['roles']['fresh_confirmation']=['invented']
        with self.assertRaisesRegex(ValueError,'NO_BENCHMARK_DATA_ROLES'):worker.validate_fixture(f)
    def test_corrupt_source_rejected(self):
        f=json.loads((HERE/'authored_fixtures.json').read_text());f['documents'][0]['source_document_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'AUTHORED_SOURCE_TEXT_HASH'):worker.validate_fixture(f)
    def test_benchmark_identity_rejected(self):
        f=json.loads((HERE/'authored_fixtures.json').read_text());f['documents'][0]['document_id']=17
        with self.assertRaisesRegex(ValueError,'AUTHORSHIP_DOCUMENT_IDENTITY'):worker.validate_fixture(f)
    def test_original_fitting_group_preserved(self):
        text='Invented source $125.50 retained for 30 days without omission.';bank=simple_bank(text);audit={}
        result=packing.build_fragment_catalog(bank,wordpiece_fake,lambda:1,audit)
        self.assertEqual(result['documents'][0]['evidence'],bank['documents'][0]['evidence'])
        self.assertFalse(audit['documents'][0]['coalesced_groups'][0]['over_capacity'])
    def test_invented_oversized_branch(self):
        text=('invented word '*700)+'closing note';bank=simple_bank(text);audit={}
        result=packing.build_fragment_catalog(bank,wordpiece_fake,lambda:1,audit)
        units=result['documents'][0]['evidence'];self.assertGreater(len(units),1)
        self.assertEqual(''.join(u['sentence'] for u in units),text)
        self.assertTrue(audit['documents'][0]['coalesced_groups'][0]['over_capacity'])
    def test_numeric_boundary_coalesces(self):
        parts=['Amount $1,','250.50 retained.'];bank=simple_bank(''.join(parts),parts);audit={}
        result=packing.build_fragment_catalog(bank,wordpiece_fake,lambda:1,audit)
        self.assertEqual(audit['documents'][0]['coalesced_boundary_offsets'],[len(parts[0])])
        self.assertEqual(len(result['documents'][0]['evidence']),1)
    def test_combining_boundary_coalesces(self):
        parts=['Cafe','\u0301 recorded.'];bank=simple_bank(''.join(parts),parts);audit={}
        packing.build_fragment_catalog(bank,wordpiece_fake,lambda:1,audit)
        self.assertEqual(audit['documents'][0]['coalesced_boundary_offsets'],[4])
    def test_zwj_boundary_coalesces(self):
        parts=['Symbol \U0001f469','\u200d\U0001f4bb recorded.'];bank=simple_bank(''.join(parts),parts);audit={}
        packing.build_fragment_catalog(bank,wordpiece_fake,lambda:1,audit)
        self.assertEqual(audit['documents'][0]['coalesced_boundary_offsets'],[len(parts[0])])
    def test_blank_boundary_coalesces(self):
        parts=['Source. ','   ','Tail.'];bank=simple_bank(''.join(parts),parts);audit={}
        result=packing.build_fragment_catalog(bank,wordpiece_fake,lambda:1,audit)
        self.assertIn(len(parts[0]),audit['documents'][0]['coalesced_boundary_offsets'])
        self.assertEqual(''.join(x['sentence'] for x in result['documents'][0]['evidence']),''.join(parts))
    def test_invented_unfragmentable_rejected(self):
        bank=simple_bank('unsplittable')
        def impossible(p,c):return {'input_ids':[1]*600}
        with self.assertRaisesRegex(ValueError,'GREEDY_SOURCE_FRAGMENT_PARTITION_FAILED_NO_FALLBACK'):
            packing.build_fragment_catalog(bank,impossible,lambda:1,{})
    def test_no_unsafe_pair_rewrite(self):
        fake=wordpiece_fake('invented source','invented query');self.assertIs(reader.validate_encoding(fake,True),fake)
        fake['token_type_ids']=[0]*len(fake['input_ids'])
        with self.assertRaisesRegex(ValueError,'TOKENIZER_WHOLE_PAIR_CAPTURE'):reader.validate_encoding(fake,True)
    def test_whole_source_partition_preserves(self):
        text='One record. Two records. ';parts=['One record. ','Two records. '];b=simple_bank(text,parts)
        windows=packing.pack_whole_source(b['documents'][0]['evidence'],'query',wordpiece_fake,lambda c:3)
        self.assertEqual(len(windows),1);self.assertEqual(windows[0]['evidence']['source_coverage_fraction'],1.0)
    def test_false_branch_coverage_rejected(self):
        f=json.loads((HERE/'authored_fixtures.json').read_text());bank,_=worker.validate_fixture(f)
        audit={};result=packing.build_fragment_catalog(bank,wordpiece_fake,lambda:1,audit)
        # These full fixtures have >512 invented words, but corrupt the actual coalescence audit.
        audit['documents'][0]['coalesced_boundary_offsets']=[123]
        with self.assertRaisesRegex(ValueError,'EXACT_EXPECTED_COALESCED_BOUNDARIES'):
            worker.branch_and_integrity_gates(bank,result,audit)
    def test_native_diff_scope(self):
        s=(HERE/'native_helper.cjs').read_text();self.assertIn("bundle.phase==='engineering'",s)
        self.assertIn('bundle.epoch===55',s);self.assertNotIn('bundle.epoch===53',s)
        self.assertIn('NATIVE_SOURCE_VECTOR_BITS',s)
    def test_supervisor_external_termination_enters_cleanup(self):
        s=(HERE/'supervisor.py').read_text()
        self.assertIn('signal.signal(signal.SIGTERM,stop_for_external_signal)',s)
        self.assertIn('signal.signal(signal.SIGINT,stop_for_external_signal)',s)
        self.assertIn('signal.signal(signal.SIGTERM,signal.SIG_IGN)',s)
        self.assertIn('EXTERNAL_SUPERVISOR_SIGNAL',s)
    def test_supervisor_signal_deferred_through_child_identity_capture(self):
        tree=ast.parse((HERE/'supervisor.py').read_text())
        handler=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='stop_for_external_signal')
        self.assertFalse(any(isinstance(n,ast.Raise) for n in ast.walk(handler)))
        s=(HERE/'supervisor.py').read_text()
        self.assertIn('stop_requested[0]=True',s)
        self.assertIn("require(not stop_requested[0],'EXTERNAL_SUPERVISOR_SIGNAL')",s)
        self.assertIn("if stop_requested[0]:reason=reason or 'EXTERNAL_SUPERVISOR_SIGNAL'",s)
    def test_supervisor_hard_absolute_clock(self):
        s=(HERE/'supervisor.py').read_text();self.assertIn('LIMIT=START+600',s)
        self.assertIn("str(START+570)",s);self.assertIn('elapsed>=580',s);self.assertIn('elapsed>=585',s)
        self.assertIn("W/'ENGINEERING_OUTER_ATTEMPT.actual.v1.json'",s)
        self.assertIn('os.O_EXCL',s)

if __name__=='__main__':unittest.main(verbosity=2)
