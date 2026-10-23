"""Pure temporary fixtures only; no actual project staging or Git calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('epoch19_public_staging',HERE/'prepare_publication.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class Transport(unittest.TestCase):
    def test_large_utf8_is_separate_blob_and_exact_sha_tree_reference(self):
        path=M.PREFIX+'epoch19/generic-fixture.json'
        raw=json.dumps({'generic':'é'*150000},ensure_ascii=False).encode('utf8')
        entries,big,groups=M.transport_groups({path:raw})
        self.assertEqual(len(big),1);self.assertEqual(len(groups),1)
        name,payload,rel,original=big[0]
        self.assertEqual(payload['encoding'],'utf-8')
        self.assertEqual(payload['content'].encode('utf8'),raw)
        self.assertEqual((rel,original),(path,raw))
        self.assertEqual(entries[0]['sha'],M.gitsha(raw))
        self.assertNotIn('content',entries[0])
        self.assertLess(len(M.raw_json({'tree_elements':groups[0]})),200000)

    def test_multiple_small_unicode_files_respect_actual_byte_cap(self):
        rows={M.PREFIX+f'epoch19/generic-{n}.txt':('Ω'*10000).encode('utf8')for n in range(50)}
        entries,big,groups=M.transport_groups(rows)
        self.assertFalse(big);self.assertEqual(len(entries),50);self.assertGreater(len(groups),1)
        for group in groups:self.assertLess(len(M.raw_json({'tree_elements':group})),190000)
        self.assertEqual([e for g in groups for e in g],entries)

    def test_single_huge_path_never_bypasses_tree_cap(self):
        path=M.PREFIX+'epoch19/'+'x'*200000+'.txt'
        with self.assertRaises(ValueError):M.transport_groups({path:b'GENERIC'})


class PublicInputs(unittest.TestCase):
    def test_symlink_directory_and_dangling_leaf_refused(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);real=root/'real';real.mkdir();(real/'x.txt').write_text('GENERIC')
            (root/'alias').symlink_to(real,target_is_directory=True)
            (root/'dangling.txt').symlink_to(root/'absent')
            for p in (root/'alias/x.txt',root/'dangling.txt'):
                with self.assertRaises(ValueError):M.regular(p)

    def test_private_assets_raw_email_and_pages_fail_closed(self):
        for path,raw in [('x/assets/config.json',b'{}'),('x/private.json',b'{}'),
                         ('x/cache/file.json',b'{}'),('x/raw.html',bytes([60])+b'html>PUBLIC_FIXTURE'+bytes([60])+b'/html>'),
                         ('x/raw.txt',b'Received: GENERIC_FIXTURE'),
                         ('x/control.json',b'{"x":"\x00"}')]:
            with self.subTest(path=path),self.assertRaises(ValueError):M.public_text(path,raw)

    def test_source_controls_must_withhold_native_admission(self):
        with tempfile.TemporaryDirectory()as temp:
            directory=Path(temp)
            old=[{'path':f'historical/{n}.txt','bytes':0,'sha256':'0'*64}for n in range(2718)]
            cp={'project_files':old};cpbytes=json.dumps(cp).encode()
            (directory/'CHECKPOINT_MANIFEST.json').write_bytes(cpbytes)
            active={'run_id':'GENERIC','experiments_active':True,'native_allowed':0}
            continuation={'checkpoint_manifest_sha256':M.sha(cpbytes),'active_run':dict(active)}
            def save():
                (directory/'CONTINUATION.json').write_text(json.dumps(continuation))
                (directory/'ACTIVE_RUN.json').write_text(json.dumps(active))
            save();M.checked_controls(directory,cp,{},'source')
            for target,field,value in ((active,'native_allowed',2),(continuation['active_run'],'native_allowed',2),
                                       (active,'experiments_active',False)):
                original=target[field];target[field]=value;save()
                with self.assertRaises(ValueError):M.checked_controls(directory,cp,{},'source')
                target[field]=original

    def test_final_both_control_flags_and_conditional_allowance_are_closed(self):
        with tempfile.TemporaryDirectory()as temp:
            directory=Path(temp);rel=M.PREFIX+'epoch19/EPOCH_MANIFEST.json';raw=b'{}'
            old=[{'path':f'historical/{n}.txt','bytes':0,'sha256':'0'*64}for n in range(2718)]
            oldcp={'project_files':old};cp={'project_files':old+[{'path':rel,'bytes':len(raw),'sha256':M.sha(raw)}]}
            cpbytes=json.dumps(cp).encode();(directory/'CHECKPOINT_MANIFEST.json').write_bytes(cpbytes)
            active={'run_id':'GENERIC','experiments_active':False,'native_allowed':0,
                    'native_allowed_after_exact_remote_readback':0}
            continuation={'checkpoint_manifest_sha256':M.sha(cpbytes),'active_run':dict(active)}
            def save():
                (directory/'CONTINUATION.json').write_text(json.dumps(continuation))
                (directory/'ACTIVE_RUN.json').write_text(json.dumps(active))
            save();M.checked_controls(directory,oldcp,{rel:raw},'final')
            for target,field,value in ((active,'native_allowed_after_exact_remote_readback',2),
                (active,'native_allowed',False),(continuation['active_run'],'native_allowed',2),
                (continuation['active_run'],'experiments_active',True)):
                original=target[field];target[field]=value;save()
                with self.assertRaises(ValueError):M.checked_controls(directory,oldcp,{rel:raw},'final')
                target[field]=original

    def test_previously_published18_source_cannot_change_or_disappear(self):
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'expected.json';rel=M.PREFIX+'epoch19/generic.json';raw=b'{}'
            value={'scope':M.SCOPE,'source_checkpoint':M.SOURCE_COMMIT,
                   'files':[dict(M.leaf(rel,raw),path=M.SCOPE+rel)]}
            path.write_text(json.dumps(value))
            M.previous_leaves(path,{}, {rel:raw})
            for now in ({rel:b'{"changed":true}'},{}):
                with self.assertRaises(ValueError):M.previous_leaves(path,{},now)


if __name__=='__main__':unittest.main()
