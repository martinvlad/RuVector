"""Tiny generic assets test precise exclusion; no actual model bytes/runtime."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('publication_asset_v2',HERE/'prepare_publication_v2.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
oldspec=importlib.util.spec_from_file_location('publication_retained_v1',HERE/'prepare_publication.py')
OLD=importlib.util.module_from_spec(oldspec);oldspec.loader.exec_module(OLD)

class ExactExternalAssets(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='e20-generic-assets-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=self.root/'project';self.project.mkdir()
        self.contents={name:('GENERIC_EXTERNAL_BYTES_'+name).encode()for name in M.EXTERNAL_FILES}
        self.fake={name:(len(b),M.sha(b))for name,b in self.contents.items()}
        original=M.EXTERNAL_FILES;M.EXTERNAL_FILES=self.fake;self.addCleanup(setattr,M,'EXTERNAL_FILES',original)
        self.assets={}
        for name,b in self.contents.items():
            rel=M.EXTERNAL_ROOT+'/'+name;path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b);self.assets[rel]=path
        self.lock={'repository':M.EXTERNAL_REPOSITORY,'revision':M.EXTERNAL_REVISION,
                   'assets':[{'path':rel,'bytes':self.fake[path.name][0],'sha256':self.fake[path.name][1]}for rel,path in self.assets.items()]}
        self.save_lock()
        self.public=self.project/(M.PREFIX+'epoch20/generic-public.json');self.public.parent.mkdir(parents=True);self.public.write_text('{}')
        self.code=self.project/(M.PREFIX+'candidate/epoch20/generic-source.py');self.code.write_text('GENERIC = True\n')
    def save_lock(self):
        p=self.project/M.EXTERNAL_LOCK;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(self.lock))
    def test_old_integration_failure_retained_in_tiny_fixture(self):
        with self.assertRaisesRegex(ValueError,'Private/raw/model/cache path refused'):OLD.walk_current(self.project)
    def test_only_exact_seven_excluded_without_read_bytes_on_any_asset(self):
        real=Path.read_bytes
        def guarded(path):
            if path in self.assets.values():raise AssertionError('external asset loaded into publication RAM')
            return real(path)
        with patch.object(Path,'read_bytes',guarded):current=M.walk_current(self.project)
        self.assertEqual(set(current),{M.EXTERNAL_LOCK,self.public.relative_to(self.project).as_posix(),self.code.relative_to(self.project).as_posix()})
        self.assertFalse(set(current)&set(self.assets))
    def test_same_size_changed_asset_fails_hash(self):
        p=next(iter(self.assets.values()));p.write_bytes(b'X'*p.stat().st_size)
        with self.assertRaisesRegex(ValueError,'SHA256 changed'):M.walk_current(self.project)
    def test_missing_asset_fails(self):
        next(iter(self.assets.values())).unlink()
        with self.assertRaisesRegex(ValueError,'Missing declared'):M.walk_current(self.project)
    def test_unknown_asset_fails_before_content_read(self):
        p=self.project/M.EXTERNAL_ROOT/'unknown.bin';p.write_bytes(b'GENERIC')
        real=Path.read_bytes
        def guarded(path):
            if path==p:raise AssertionError('unknown asset content was read')
            return real(path)
        with patch.object(Path,'read_bytes',guarded),self.assertRaisesRegex(ValueError,'Unknown external model asset'):M.walk_current(self.project)
    def test_unknown_empty_directory_refused(self):
        (self.project/M.EXTERNAL_PARENT/'unreviewed').mkdir()
        with self.assertRaisesRegex(ValueError,'Unknown external asset directory'):M.walk_current(self.project)
    def test_symlink_known_asset_refused(self):
        p=next(iter(self.assets.values()));b=p.read_bytes();p.unlink();other=self.root/'generic-target';other.write_bytes(b);p.symlink_to(other)
        with self.assertRaises(ValueError):M.walk_current(self.project)
    def test_lock_expansion_or_identity_edit_cannot_expand_exclusions(self):
        original=copy.deepcopy(self.lock)
        for mutation in ['path','sha','duplicate','revision']:
            self.lock=copy.deepcopy(original)
            if mutation=='path':self.lock['assets'][0]['path']=M.EXTERNAL_ROOT+'/unreviewed.bin'
            elif mutation=='sha':self.lock['assets'][0]['sha256']='0'*64
            elif mutation=='duplicate':self.lock['assets'].append(copy.deepcopy(self.lock['assets'][0]))
            else:self.lock['revision']='0'*40
            self.save_lock()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):M.walk_current(self.project)
    def test_lock_required_when_assets_exist(self):
        (self.project/M.EXTERNAL_LOCK).unlink()
        with self.assertRaises(FileNotFoundError):M.walk_current(self.project)

if __name__=='__main__':unittest.main(verbosity=2)
