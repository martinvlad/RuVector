"""Generic directory-boundary tests for source-only publication metadata."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCOPE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('generic19_stager',Path(__file__).resolve().parent/'prepare_publication.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class OptionalQualificationDirectories(unittest.TestCase):
    def test_required_epoch_root_allows_absent_nonroot_directories(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);file=root/(M.PREFIX+'epoch19/generic.txt')
            file.parent.mkdir(parents=True);file.write_bytes(b'GENERIC_SOURCE_ONLY')
            self.assertEqual(M.walk_current(root),{M.PREFIX+'epoch19/generic.txt':b'GENERIC_SOURCE_ONLY'})

    def test_dangling_optional_directory_rejected_and_epochroot_required(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);e=root/(M.PREFIX+'epoch19');e.mkdir(parents=True)
            target=root/(M.PREFIX+'candidate/epoch19');target.parent.mkdir()
            target.symlink_to(root/'absent',target_is_directory=True)
            with self.assertRaises(ValueError):M.walk_current(root)
        with tempfile.TemporaryDirectory()as tmp:
            with self.assertRaises(ValueError):M.walk_current(Path(tmp))


if __name__=='__main__':unittest.main(verbosity=2)
