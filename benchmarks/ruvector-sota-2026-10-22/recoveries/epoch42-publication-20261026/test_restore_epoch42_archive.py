"""Invented tiny archives/tempdirs only; never open the real E42 archive."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('e42_archive_fixture_source',HERE/'restore_epoch42_archive.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)


def fixture(*,bad_hash=False,bad_name=None,bad_mode=None,duplicate=False):
    files={'public-project/a.txt':b'alpha','public-project/sub/b.txt':b'beta',
        'unpublished-desired-controls/never.json':b'{"fixture_only":true}'}
    if bad_name is not None:files[bad_name]=files.pop('unpublished-desired-controls/never.json')
    rows=[{'path':name,'bytes':len(body),'sha256':A.digest(body)}for name,body in files.items()]
    if bad_hash:rows[2 if bad_hash=='nonselected'else 0]['sha256']='0'*64
    manifest=json.dumps({'schema_version':1,'epoch':42,'files':rows},sort_keys=True).encode()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED)as target:
        for index,(name,body)in enumerate([*files.items(),('RECOVERY_MANIFEST.json',manifest)]):
            info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3
            info.external_attr=((bad_mode if index==0 and bad_mode is not None else stat.S_IFREG|0o644)<<16)
            target.writestr(info,body)
        if duplicate:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore');target.writestr('public-project/a.txt',b'alpha')
    projection={'project_files':[{'path':name.removeprefix('public-project/'),'archive_member':name,
        'bytes':len(body),'sha256':A.digest(body),'present_in_SOURCE_Git':True}for name,body in files.items()if name.startswith('public-project/')]}
    policy={'members':5 if duplicate else 4,'manifest_rows':3,'manifest':'RECOVERY_MANIFEST.json',
        'manifest_bytes':len(manifest),'manifest_sha256':A.digest(manifest),
        'total_bytes':sum(map(len,files.values()))+len(manifest)+(5 if duplicate else 0),
        'selected':2,'selected_bytes':9,'prefix':'public-project/'}
    return buf.getvalue(),projection,policy


class ArchiveChecks(unittest.TestCase):
    def validated(self):return A._validated_payloads(*fixture())

    def test_valid_members_and_only_selected_written_to_both_roots(self):
        payloads,proof=self.validated();self.assertEqual(set(payloads),{'a.txt','sub/b.txt'})
        self.assertEqual(proof['manifest_bodies_verified'],3)
        with tempfile.TemporaryDirectory(prefix='invented-archive-',dir=HERE)as folder:
            scope=Path(folder);kit,dest=scope/'kit',scope/'project'
            result=A._materialize(payloads,kit,dest,scope)
            self.assertEqual((result['kit_written'],result['dest_written']),(2,2))
            for root in(kit,dest):
                self.assertEqual((root/'a.txt').read_bytes(),b'alpha')
                self.assertFalse((root/'unpublished-desired-controls').exists())
            verify=A._materialize(payloads,kit,dest,scope,True)
            self.assertEqual((verify['kit_written'],verify['dest_written']),(0,0))
            self.assertTrue(verify['both_destinations_complete'])

    def test_every_unsafe_name_including_dot_refused(self):
        for name in ['.','../escape','/absolute','x\\evil','x//evil','x/./evil','x/../evil','C:drive']:
            with self.subTest(name=name),self.assertRaises(ValueError):A._validated_payloads(*fixture(bad_name=name))

    def test_duplicate_and_symlink_special_directory_setuid_refused(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):A._validated_payloads(*fixture(duplicate=True))
        for mode in [stat.S_IFLNK|0o777,stat.S_IFIFO|0o600,stat.S_IFDIR|0o755,stat.S_IFREG|0o4644]:
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'SPECIAL'):
                A._validated_payloads(*fixture(bad_mode=mode))

    def test_encryption_bit_refused_before_body_read(self):
        data,projection,policy=fixture();raw=bytearray(data);at=raw.index(b'PK\x01\x02')
        flags=struct.unpack_from('<H',raw,at+8)[0];struct.pack_into('<H',raw,at+8,flags|1)
        with self.assertRaisesRegex(ValueError,'ENCRYPTED'):A._validated_payloads(bytes(raw),projection,policy)

    def test_nonselected_hash_and_selected_hash_failure_no_targets(self):
        for bad in [True,'nonselected']:
            data,projection,policy=fixture(bad_hash=bad)
            with self.assertRaisesRegex(ValueError,'BODY_HASH'):A._validated_payloads(data,projection,policy)
        data,projection,policy=fixture();projection['project_files'][0]['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'PROJECTION_MANIFEST'):A._validated_payloads(data,projection,policy)

    def test_member_and_manifest_bound_mismatches(self):
        data,projection,policy=fixture();policy={**policy,'total_bytes':policy['total_bytes']-1}
        with self.assertRaisesRegex(ValueError,'BOUND_OR_IDENTITY'):A._validated_payloads(data,projection,policy)
        data,projection,policy=fixture();policy={**policy,'manifest_sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'MANIFEST_SHA'):A._validated_payloads(data,projection,policy)

    def test_second_destination_collision_prevents_first_root_creation(self):
        payloads,_=self.validated()
        with tempfile.TemporaryDirectory(prefix='invented-collision-',dir=HERE)as folder:
            scope=Path(folder);kit,dest=scope/'kit',scope/'project';(dest/'sub').mkdir(parents=True)
            (dest/'sub/b.txt').write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'NO_OVERWRITE'):A._materialize(payloads,kit,dest,scope)
            self.assertFalse(kit.exists());self.assertFalse((dest/'a.txt').exists())

    def test_parent_file_symlink_and_input_ancestry_prevent_any_write(self):
        payloads,_=self.validated()
        with tempfile.TemporaryDirectory(prefix='invented-path-',dir=HERE)as folder:
            scope=Path(folder);kit,dest=scope/'kit',scope/'project'
            (scope/'parent-file').write_bytes(b'fixture')
            with self.assertRaises((ValueError,NotADirectoryError)):
                A._materialize(payloads,kit,scope/'parent-file'/'project',scope)
            self.assertFalse(kit.exists())
            (scope/'other').mkdir();kit.symlink_to(scope/'other',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'SYMLINK'):A._materialize(payloads,kit,dest,scope)
            kit.unlink()
            with self.assertRaisesRegex(ValueError,'SOURCE_INPUT'):
                A._materialize(payloads,kit,dest,scope,inputs=(kit/'a.txt'/'below',))
            self.assertFalse(kit.exists());self.assertFalse(dest.exists())

    def test_verify_only_missing_and_immutable_scope_overlap_refused(self):
        payloads,_=self.validated()
        with tempfile.TemporaryDirectory(prefix='invented-verify-',dir=HERE)as folder:
            scope=Path(folder)
            with self.assertRaisesRegex(ValueError,'VERIFY_ONLY'):A._materialize(payloads,scope/'kit',scope/'project',scope,True)
            self.assertEqual(list(scope.iterdir()),[])
        with tempfile.TemporaryDirectory(prefix='invented-immutable-',dir=HERE)as folder:
            old=Path(folder)/'fixture-frozen-root'
            with patch.object(A,'IMMUTABLE_ROOTS',(old,)):
                for scope in [old,old/'fresh-child',old.parent]:
                    with self.assertRaisesRegex(ValueError,'IMMUTABLE'):A._check_roots(scope/'kit',scope/'project',scope)

    def test_typed_binary_git_hash_and_exact_whole_input_identity(self):
        raw=b'PK\x03\x04\x00\xff\xfe\x80';expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.assertEqual(A.git_blob(raw),expected)
        with tempfile.TemporaryDirectory(prefix='invented-identity-',dir=HERE)as folder:
            path=Path(folder)/'small.zip';path.write_bytes(raw)
            self.assertEqual(A.checked_read(path,len(raw),A.digest(raw),expected),raw)
            with self.assertRaisesRegex(ValueError,'GIT_BLOB'):A.checked_read(path,len(raw),A.digest(raw),'0'*40)


if __name__=='__main__':unittest.main()
