"""Generic public cache path/RECORD fixtures; no neural/runtime restoration."""
from pathlib import Path
import base64
import csv
import hashlib
import importlib.util
import io
import stat
import tempfile
import unittest
import warnings
import zipfile

SOURCE = Path(__file__).resolve().parents[2]
HELPER = SOURCE / 'epoch18/preparation/restore_public_runtime_cache.py'
spec = importlib.util.spec_from_file_location('reviewed18_public_cache', HELPER)
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)


def wheel(files=None, mutate=None, symlink=None):
    files = dict(files or {'generic/core.py': b'PUBLIC_GENERIC = 1\n'})
    record = 'generic-1.0.dist-info/RECORD'
    rows = []
    for name, value in files.items():
        encoded = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).decode().rstrip('=')
        rows.append([name, 'sha256=' + encoded, str(len(value))])
    rows.append([record, '', ''])
    if mutate:
        mutate(rows)
    text = io.StringIO(newline='')
    csv.writer(text).writerows(rows)
    body = io.BytesIO()
    with zipfile.ZipFile(body, 'w') as archive:
        for name, value in files.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = ((stat.S_IFLNK if name == symlink else stat.S_IFREG) | 0o644) << 16
            archive.writestr(info, value)
        archive.writestr(record, text.getvalue())
    body.seek(0)
    return body


class PublicCacheFixtures(unittest.TestCase):
    def test_safe_relative_paths(self):
        self.assertEqual(H.relative('package/public.bin'), Path('package/public.bin'))
        for value in ('', '/outside', '../outside', 'x/../outside', 'x//y', 'x/./y', 'x\\y', 'x/'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                H.relative(value)

    def test_exact_public_hardlink_and_existing_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root/'source'; target = root/'new'/'target'
            raw = b'generic public cache bytes'; source.write_bytes(raw)
            row = {'path': 'new/target', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            self.assertEqual(H.link_asset(source, target, row), 'HARDLINKED_EXACT_PUBLIC_BYTES')
            self.assertEqual(source.stat().st_ino, target.stat().st_ino)
            self.assertEqual(H.link_asset(source, target, row), 'VERIFIED_EXISTING')

    def test_wrong_identity_or_destination_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root/'source'; target = root/'target'
            source.write_bytes(b'public'); target.write_bytes(b'preserve')
            row = {'path':'target', 'bytes':6, 'sha256':hashlib.sha256(b'public').hexdigest()}
            with self.assertRaises(ValueError): H.link_asset(source, target, row)
            self.assertEqual(target.read_bytes(), b'preserve')
            with self.assertRaises(ValueError): H.link_asset(source, root/'absent', {**row,'sha256':'0'*64})
            self.assertFalse((root/'absent').exists())

    def test_symlink_and_symlink_parent_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=root/'folder'; folder.mkdir(); (folder/'public').write_bytes(b'public')
            (root/'alias').symlink_to(folder, target_is_directory=True)
            with self.assertRaises(ValueError): H.no_symlink(root/'alias'/'public')
            (root/'direct').symlink_to(folder/'public')
            with self.assertRaises(ValueError): H.no_symlink(root/'direct')

    def test_wheel_target_schemes(self):
        venv=Path('/generic/venv'); site=venv/'lib/python3.12/site-packages'
        self.assertEqual(H.wheel_target('generic/core.py',venv,site),site/'generic/core.py')
        for scheme, base in [('purelib',site),('platlib',site),('scripts',venv/'bin'),('data',venv),('headers',venv/'include')]:
            self.assertEqual(H.wheel_target('generic.data/'+scheme+'/public',venv,site),base/'public')
        for name in ('generic.data/unknown/public','generic.data/data','generic.data/data/../private'):
            with self.subTest(name=name), self.assertRaises(ValueError): H.wheel_target(name,venv,site)

    def test_exact_record_member_hashes(self):
        with zipfile.ZipFile(wheel()) as archive:
            checked=list(H.wheel_members(archive))
        self.assertEqual(len(checked),2)
        self.assertEqual(checked[0][1],hashlib.sha256(b'PUBLIC_GENERIC = 1\n').hexdigest())

    def test_bad_record_hash_and_missing_member_record(self):
        for mutate in (lambda rows: rows[0].__setitem__(1,'sha256='+('A'*43)),lambda rows: rows.pop(0)):
            with zipfile.ZipFile(wheel(mutate=mutate)) as archive, self.assertRaises(ValueError):
                list(H.wheel_members(archive))

    def test_duplicate_record_rows(self):
        with zipfile.ZipFile(wheel(mutate=lambda rows:rows.append(rows[0]))) as archive, self.assertRaises(ValueError):
            list(H.wheel_members(archive))

    def test_duplicate_zip_members(self):
        body=wheel()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(body,'a') as archive: archive.writestr('generic/core.py',b'duplicate')
        body.seek(0)
        with zipfile.ZipFile(body) as archive, self.assertRaises(ValueError): list(H.wheel_members(archive))

    def test_traversal_zip_member_and_symlink_refused(self):
        for body in (wheel({'../outside.py':b'public'}),wheel(symlink='generic/core.py')):
            with zipfile.ZipFile(body) as archive, self.assertRaises(ValueError): list(H.wheel_members(archive))

    def test_missing_record(self):
        body=io.BytesIO()
        with zipfile.ZipFile(body,'w') as archive:archive.writestr('generic/core.py',b'public')
        body.seek(0)
        with zipfile.ZipFile(body) as archive, self.assertRaises(ValueError):list(H.wheel_members(archive))


if __name__ == '__main__': unittest.main()
