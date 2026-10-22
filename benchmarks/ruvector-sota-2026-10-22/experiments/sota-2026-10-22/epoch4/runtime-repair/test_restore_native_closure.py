"""Meaningful restoration controls; no package import or native/model calls."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

import restore_native_closure as repair


class ClosureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = repair.load_spec()
        cls.fixture = tempfile.TemporaryDirectory(prefix="negative-controls-", dir=repair.HERE)
        cls.folder = Path(cls.fixture.name)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def test_all_eight_official_files_verified(self):
        files = {}
        for package in self.spec["packages"]:
            raw = repair.read_offline(repair.HERE, repair.cache_name(package["package"]))
            files.update(repair.unpack(package, raw))
        self.assertEqual(len(files), 8)
        self.assertIn("retrieval/node_modules/ruvector-core-linux-x64-gnu/index.js", files)
        self.assertEqual(len(files["retrieval/node_modules/ruvector-core-linux-x64-gnu/index.js"]), 330)

    def test_tarball_corruption_rejected(self):
        package = self.spec["packages"][1]
        raw = repair.read_offline(repair.HERE, repair.cache_name(package["package"]))
        with self.assertRaisesRegex(ValueError, "archive length/SHA256"):
            repair.unpack(package, raw[:-1] + bytes([raw[-1] ^ 1]))

    def test_wrong_npm_integrity_rejected(self):
        package = copy.deepcopy(self.spec["packages"][0])
        raw = repair.read_offline(repair.HERE, repair.cache_name(package["package"]))
        package["npm_integrity"] = "sha512-" + base64.b64encode(bytes(64)).decode()
        with self.assertRaisesRegex(ValueError, "SHA512"):
            repair.verify_tarball(package, raw)

    def test_missing_platform_main_rejected(self):
        package = self.spec["packages"][1]
        raw = repair.read_offline(repair.HERE, repair.cache_name(package["package"]))
        files = repair.unpack(package, raw)
        del files["retrieval/node_modules/ruvector-core-linux-x64-gnu/index.js"]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            repair.verify_closure(package, files)

    def test_unpacked_file_tamper_rejected(self):
        package = self.spec["packages"][0]
        raw = repair.read_offline(repair.HERE, repair.cache_name(package["package"]))
        files = repair.unpack(package, raw)
        files["retrieval/node_modules/@ruvector/core/index.js"] += b"x"
        with self.assertRaisesRegex(ValueError, "file identity"):
            repair.verify_closure(package, files)

    def test_spec_tamper_rejected_before_restoration(self):
        path = self.folder / "altered-spec.json"
        path.write_bytes(repair.SPEC_PATH.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "specification changed"):
            repair.restore(self.folder / "not-created", archive_dir=repair.HERE, spec_path=path)
        self.assertFalse((self.folder / "not-created").exists())

    def test_existing_destination_is_preserved(self):
        destination = self.folder / "existing"
        destination.mkdir()
        (destination / "user.txt").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "never overwrite"):
            repair.restore(destination, archive_dir=repair.HERE)
        self.assertEqual((destination / "user.txt").read_text(), "preserve")

    def test_destination_symlink_rejected(self):
        link = self.folder / "destination-link"
        link.symlink_to(self.folder / "target")
        with self.assertRaises(ValueError):
            repair.restore(link, archive_dir=repair.HERE)

    def test_symlink_parent_rejected(self):
        link = self.folder / "parent-link"
        link.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(OSError):
            repair.restore(link / "not-created", archive_dir=repair.HERE)

    def test_offline_archive_symlink_rejected(self):
        folder = self.folder / "archive-links"
        folder.mkdir()
        name = repair.cache_name(self.spec["packages"][0]["package"])
        (folder / name).symlink_to(repair.HERE / name)
        with self.assertRaises(OSError):
            repair.restore(self.folder / "no-source-write", archive_dir=folder)
        self.assertFalse((self.folder / "no-source-write").exists())

    def test_offline_fifo_rejected_without_blocking(self):
        folder = self.folder / "archive-fifo"
        folder.mkdir()
        name = repair.cache_name(self.spec["packages"][0]["package"])
        os.mkfifo(folder / name)
        with self.assertRaisesRegex(ValueError, "regular file"):
            repair.restore(self.folder / "no-fifo-write", archive_dir=folder)
        self.assertFalse((self.folder / "no-fifo-write").exists())

    def test_specification_symlink_rejected(self):
        path = self.folder / "specification-link.json"
        path.symlink_to(repair.SPEC_PATH)
        with self.assertRaisesRegex(ValueError, "symlink"):
            repair.load_spec(path)

    def test_archive_traversal_rejected(self):
        for path in ("../outside", "/absolute", "package/../../outside", "package\\outside"):
            with self.assertRaises(ValueError):
                repair.safe_parts(path)

    def test_link_member_rejected_even_with_consistent_test_archive_digest(self):
        package = copy.deepcopy(self.spec["packages"][0])
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo("package/index.js")
            member.type = tarfile.SYMTYPE
            member.linkname = "../../outside"
            archive.addfile(member)
        raw = stream.getvalue()
        # Unit-test the archive structure guard after integrity validation.
        package.update(tarball_bytes=len(raw), tarball_sha256=repair.sha(raw),
                       npm_integrity="sha512-" + base64.b64encode(hashlib.sha512(raw).digest()).decode())
        with self.assertRaisesRegex(ValueError, "non-regular"):
            repair.unpack(package, raw)

    def test_no_implicit_network_or_multiple_sources(self):
        for kwargs in ({}, {"archive_dir": repair.HERE, "acquire": True}):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                repair.restore(self.folder / "no-implicit-network", **kwargs)


if __name__ == "__main__": unittest.main()
