"""Disjoint stdlib-only regression for the exact dispatch filesystem scope."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch


class WorkspaceScope(unittest.TestCase):
    def test_distinct_filesystems_do_not_substitute_tmp_free_for_workspace(self):
        source=Path(__file__).parents[2]/'epoch40/preparation/dispatch_once.py'
        spec=importlib.util.spec_from_file_location('e40_dispatch_scope_pure',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        GiB=1073741824
        memory={
            '/proc/meminfo':f'MemTotal: {16*GiB//1024} kB\nMemAvailable: {12*GiB//1024} kB\n',
            '/sys/fs/cgroup/memory.max':str(16*GiB),
            '/sys/fs/cgroup/memory.current':str(4*GiB),
            '/sys/fs/cgroup/memory.stat':'\n'.join(f'{key} 0' for key in
                ('anon','kernel','file','shmem','active_file','inactive_file','file_dirty','file_writeback'))}
        queried=[];workspace_free=32*1024*1024
        def fake_disk_usage(path):
            queried.append(str(path))
            return types.SimpleNamespace(free=workspace_free if str(path)=='/workspace' else 8*GiB)
        def fake_read_text(path,*args,**kwargs):return memory[str(path)]
        with patch.object(Path,'read_text',fake_read_text),patch.object(module.shutil,'disk_usage',fake_disk_usage):
            with self.assertRaisesRegex(RuntimeError,'workspace free space'):
                module.host_admission({'host_admission_policy':dict(module.RESOURCE_POLICY)})
            self.assertEqual(queried,['/workspace'])
            workspace_free=128*1024*1024;queried.clear()
            result=module.host_admission({'host_admission_policy':dict(module.RESOURCE_POLICY)})
        self.assertEqual(queried,['/workspace'])
        self.assertEqual(result['workspace_filesystem_path'],'/workspace')
        self.assertEqual(result['workspace_free_bytes'],128*1024*1024)
        self.assertTrue(result['passed'])


if __name__=='__main__':unittest.main()
