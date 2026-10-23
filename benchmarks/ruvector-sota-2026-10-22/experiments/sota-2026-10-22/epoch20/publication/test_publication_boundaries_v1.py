"""Generic path, review and derived-control admission tests; no real data/runtime."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('epoch20_publication_boundaries',Path(__file__).with_name('prepare_publication.py'))
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class Boundaries(unittest.TestCase):
    def test_noncanonical_existing_file_and_directory_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'child').mkdir();(root/'public.txt').write_text('GENERIC')
            with self.assertRaisesRegex(ValueError,'Noncanonical'):M.regular(root/'child/../public.txt')
            with self.assertRaisesRegex(ValueError,'Noncanonical'):M.regular_dir(root/'child/..')

    def test_review_is_required_and_exact_for_every_file(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'review.json';current={'generic/public.json':b'{}'}
            with self.assertRaisesRegex(ValueError,'reviewed public allowlist required'):M.checked_review(None,current)
            row={'path':'generic/public.json','bytes':2,'sha256':M.sha(b'{}')}
            for rows in ([],[row,row],[dict(row,sha256='0'*64)],[dict(row,bytes=3)],
                         [row,{'path':'generic/extra.txt','bytes':0,'sha256':M.sha(b'')}]):
                p.write_text(json.dumps({'files':rows}))
                with self.assertRaises(ValueError):M.checked_review(p,current)
            p.write_text(json.dumps({'files':[row]}));M.checked_review(p,current)

    def test_output_may_not_be_inside_kit_or_lexically_escape(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);project=root/'project';kit=root/'kit';controls=root/'controls'
            for d in (project,kit,controls):d.mkdir()
            for out in (kit/'stage',root/'controls/../stage'):
                a=argparse.Namespace(project=project,kit=kit,controls_dir=controls,out=out,
                    source_filemap=root/'absent.json',mode='source',prior_expected=None,reviewed_files=None)
                with self.assertRaises(ValueError):M.prepare(a)
                self.assertFalse(out.exists())

    def test_final_continuation_conditional_allowance_and_owner_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);rel=M.PREFIX+'epoch20/EPOCH_MANIFEST.json';raw=b'{}'
            before={'project_files':[{'path':f'historical/{n}.txt','bytes':0,'sha256':'0'*64}for n in range(2813)]}
            after={'project_files':before['project_files']+[{'path':rel,'bytes':2,'sha256':M.sha(raw)}]}
            cb=json.dumps(after).encode();(d/'CHECKPOINT_MANIFEST.json').write_bytes(cb)
            active={'run_id':'GENERIC','native_allowed':0,'experiments_active':False}
            cont={'checkpoint_manifest_sha256':M.sha(cb),'active_run':dict(active)}
            def save():
                (d/'ACTIVE_RUN.json').write_text(json.dumps(active));(d/'CONTINUATION.json').write_text(json.dumps(cont))
            save();M.checked_controls(d,before,{rel:raw},'final')
            for value in [1,False,'0']:
                cont['active_run']['native_allowed_after_exact_remote_readback']=value;save()
                with self.assertRaisesRegex(ValueError,'continuation conditional'):M.checked_controls(d,before,{rel:raw},'final')
            cont['active_run'].pop('native_allowed_after_exact_remote_readback')
            active['run_id']='';cont['active_run']['run_id']='';save()
            with self.assertRaisesRegex(ValueError,'owner identity'):M.checked_controls(d,before,{rel:raw},'final')

if __name__=='__main__':unittest.main(verbosity=2)
