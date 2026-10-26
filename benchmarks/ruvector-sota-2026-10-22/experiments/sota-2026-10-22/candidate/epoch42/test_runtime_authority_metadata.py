"""Source/metadata-only digest regression; no asset payload or guard invocation."""
import ast
import hashlib
import json
from pathlib import Path
import unittest

HERE=Path(__file__).parent
AUTHORITY_SHA='ea8e993641fa330e47b00e374c5f7bf6f5f2952198ead0de1bc6b1cc21cf2eb4'
AUTHORITY_GIT='473912fa2cc7eb40b86ac4e0326c04679d901a0c'


class RuntimeAuthority(unittest.TestCase):
    def authority(self):
        raw=(HERE/'research/ORIGINAL_RUNTIME_LOCK_AUTHORITY.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),AUTHORITY_SHA)
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),AUTHORITY_GIT)
        return {row['path']:row['sha256']for row in json.loads(raw)['assets']}

    def test_all10_guard_literals_equal_actual_git_cp_lock_authority(self):
        tree=ast.parse((HERE/'runtime/model_assets_guard.py').read_text())
        declared=next(ast.literal_eval(node.value)for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name)and target.id=='NATIVE_BGE_SHA256'for target in node.targets))
        expected=self.authority();self.assertEqual(len(expected),10);self.assertEqual(declared,expected)
        root=HERE.parents[3]
        lock=json.loads((root/'experiments/sota-2026-10-22/epoch42/preparation/runtime-assets.lock.json').read_text())
        self.assertEqual({row['path']:row['sha256']for row in lock['assets']},expected)

    def test_old_namespace_mutations_are_rejected_by_exact_authority(self):
        expected=self.authority();path='retrieval/node_modules/@ruvector/core/index.js'
        for corrupted in ['eeba197be4185adb3492b8bc53cd61870f57d6bc18a9a5f1cd2ebec4b1908bee',
                          'eeba197be4285adb3492b8bc53cd61870f57d6bc18a9a5f1cd2ebec4b1908bee']:
            proposed={**expected,path:corrupted};self.assertNotEqual(proposed,expected)


if __name__=='__main__':unittest.main()
