"""Small author-only archive/transport fixtures; no scientific/runtime tests."""
import base64
import gzip
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

PATH = Path(__file__).with_name('prepare_publication_archive_v1.py')
SPEC = importlib.util.spec_from_file_location('archive_publication_author_fixture', PATH)
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


def fixture(data=b'{"fixture":"public saved trace"}\n'):
    spec = {'path': W.RAW_PATH, 'bytes': len(data), 'sha256': W.digest(data),
            'git_blob_sha1': W.git_blob(data)}
    compressed = gzip.compress(data, compresslevel=9, mtime=0)
    envelope = {'schema_version': 1, 'epoch': 22, 'format': 'gzip+base64',
                'artifact': spec, 'gzip': {'bytes': len(compressed),
                    'sha256': W.digest(compressed), 'mtime': 0},
                'payload_base64': base64.b64encode(compressed).decode('ascii')}
    return data, spec, envelope


def replace_compressed(envelope, compressed):
    envelope['gzip'].update(bytes=len(compressed), sha256=W.digest(compressed))
    envelope['payload_base64'] = base64.b64encode(compressed).decode('ascii')


class ArchivePublicationGuards(unittest.TestCase):
    def test_lossless_fixture_roundtrip(self):
        data, spec, envelope = fixture()
        self.assertEqual(W.decode_envelope(envelope, spec), data)

    def test_other_artifact_path_refused(self):
        _, spec, envelope = fixture()
        envelope['artifact'] = dict(spec, path='other.json')
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_wrong_restored_digest_refused(self):
        _, spec, envelope = fixture()
        spec = dict(spec, sha256='0' * 64)
        envelope['artifact'] = spec
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_wrong_compressed_digest_refused(self):
        _, spec, envelope = fixture()
        envelope['gzip']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_non_base64_and_wrong_encoding_refused(self):
        _, spec, envelope = fixture()
        envelope['payload_base64'] += '\n'
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)
        envelope['format'] = 'plain'
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_concatenated_gzip_members_refused(self):
        _, spec, envelope = fixture()
        payload = base64.b64decode(envelope['payload_base64'])
        replace_compressed(envelope, payload + gzip.compress(b'extra', mtime=0))
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_expansion_beyond_claimed_size_refused(self):
        _, spec, envelope = fixture()
        spec = dict(spec, bytes=3)
        envelope['artifact'] = spec
        replace_compressed(envelope, gzip.compress(b'x' * 100000, mtime=0))
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_nonzero_gzip_header_time_refused(self):
        data, spec, envelope = fixture()
        replace_compressed(envelope, gzip.compress(data, mtime=1))
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_boolean_schema_version_refused(self):
        _, spec, envelope = fixture()
        envelope['schema_version'] = True
        with self.assertRaises(ValueError):
            W.decode_envelope(envelope, spec)

    def test_archive_never_replaces_baseline_or_prior_source(self):
        W.reject_previously_published_raw({}, {}, 'scope/')
        with self.assertRaises(ValueError):
            W.reject_previously_published_raw({W.RAW_PATH: {}}, {}, 'scope/')
        with self.assertRaises(ValueError):
            W.reject_previously_published_raw({}, {'scope/' + W.RAW_PATH: {}}, 'scope/')

    def test_projection_removes_exactly_raw_preserves_prior_and_controls(self):
        scope = 'scope/'
        raw = {'path': scope + W.RAW_PATH, 'mode': '100644', 'type': 'blob',
               'sha': W.RAW_SPEC['git_blob_sha1'], 'size': W.RAW_SPEC['bytes']}
        old = dict(raw, path=scope + 'old.json', sha='a' * 40, size=1)
        control = dict(raw, path=scope + 'ACTIVE_RUN.json', sha='b' * 40, size=2)
        before = {old['path']: old, control['path']: dict(control, sha='c' * 40)}
        result = W.project_expected_to_git([raw, old, control], before, scope,
                                           {'ACTIVE_RUN.json'})
        self.assertEqual(result, {old['path']: old, control['path']: control})
        mutated = dict(old, sha='d' * 40)
        with self.assertRaises(ValueError):
            W.project_expected_to_git([raw, mutated, control], before, scope,
                                      {'ACTIVE_RUN.json'})

    def test_changed_or_previously_published_raw_tuple_refused(self):
        scope = 'scope/'
        row = {'path': scope + W.RAW_PATH, 'mode': '100644', 'type': 'blob',
               'sha': W.RAW_SPEC['git_blob_sha1'], 'size': W.RAW_SPEC['bytes']}
        with self.assertRaises(ValueError):
            W.project_expected_to_git([dict(row, size=1)], {}, scope, set())
        with self.assertRaises(ValueError):
            W.project_expected_to_git([row], {row['path']: row}, scope, set())

    def test_transport_reuses_reviewed_v1_and_respects_limits(self):
        helper = W.load_v1()
        big, groups = W.build_transport(helper, {'public-fixture.json': b'{"ok":true}'})
        self.assertEqual(big, [])
        self.assertEqual(len(groups), 1)
        self.assertLess(len(helper.raw_json({'tree_elements': groups[0]})), 190000)

    def test_blob_and_tree_limit_fail_closed(self):
        helper = W.load_v1()

        class Fake:
            raw_json = staticmethod(helper.raw_json)
            transport_groups = staticmethod(lambda changed: (
                [], [('blob.json', {'content': 'x' * W.MAX_BLOB_JSON_BYTES}, 'x', b'x')], []))
        with self.assertRaises(ValueError):
            W.build_transport(Fake, {})
        Fake.transport_groups = staticmethod(lambda changed: (
            [], [], [[{'content': 'x' * W.MAX_TREE_JSON_BYTES}]]))
        with self.assertRaises(ValueError):
            W.build_transport(Fake, {})

    def test_control_refs_and_CP_keep_restored_raw_and_archive(self):
        data, spec, envelope = fixture()
        project, controls = Path('/fixture/project'), Path('/fixture/controls')
        files = {W.RAW_PATH: data, W.ARCHIVE_PATH: W.json.dumps(envelope).encode(),
                 W.EXTRACTOR_PATH: b'extractor fixture', W.HELPER_PATH: b'wrapper fixture'}
        refs = {rel: {'path': rel, 'bytes': len(body), 'sha256': W.digest(body)}
                for rel, body in files.items()}
        transport = {'format': 'gzip+base64', 'archive': refs[W.ARCHIVE_PATH],
                     'extractor': refs[W.EXTRACTOR_PATH], 'restored_artifact': refs[W.RAW_PATH],
                     'publication_helper': refs[W.HELPER_PATH],
                     'required_before_bootstrap': True, 'standalone_Git_leaf_omitted': W.RAW_PATH}
        continuation = {'artifact_transport': transport, 'prior_published_base_commit': W.PARENT}
        cp = {'project_files': list(refs.values())}

        class Fake:
            @staticmethod
            def content(path):
                if path == W.Path(W.__file__):
                    return files[W.HELPER_PATH]
                return files[path.relative_to(project).as_posix()]

            @staticmethod
            def parse(path):
                if path == controls / 'CONTINUATION.json':
                    return continuation
                if path == controls / 'ACTIVE_RUN.json':
                    return {'checkpoint_parent': W.PARENT}
                if path == controls / 'CHECKPOINT_MANIFEST.json':
                    return cp
                return envelope

            public_text = staticmethod(lambda rel, body: body.decode('utf-8'))

        with patch.object(W, 'RAW_SPEC', spec):
            got, count = W.checked_reconstruction(Fake, project, controls)
            self.assertEqual(got, transport)
            self.assertEqual(count, 4)
            cp['project_files'] = [r for r in cp['project_files'] if r['path'] != W.RAW_PATH]
            with self.assertRaises(ValueError):
                W.checked_reconstruction(Fake, project, controls)
            cp['project_files'] = list(refs.values())
            transport['standalone_Git_leaf_omitted'] = 'other.json'
            with self.assertRaises(ValueError):
                W.checked_reconstruction(Fake, project, controls)


if __name__ == '__main__':
    unittest.main()
