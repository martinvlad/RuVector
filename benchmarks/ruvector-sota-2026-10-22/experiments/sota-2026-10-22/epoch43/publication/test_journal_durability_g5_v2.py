"""One fake-W metadata durability check; no guardian/API/real journal is touched."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import os,tempfile,unittest
from unittest.mock import patch
import publication_common as c
import mutation_guard_source_g5 as g
class Durability(unittest.TestCase):
 def test_nested_journal_and_request_directory_are_durable(self):
  with tempfile.TemporaryDirectory()as d:
   w=Path(d);parent=w/'lease-generation5';parent.mkdir();seen=[];real=os.fsync
   def sync(fd):seen.append((Path('/proc/self/fd')/str(fd)).resolve());return real(fd)
   with patch.object(c,'W',w),patch.object(g.os,'fsync',side_effect=sync):
    g.append({'invented':'intent'});requests=g.request_directory()
   self.assertEqual(seen[0],parent/'source-final-journal.jsonl');self.assertEqual(seen[1],parent);self.assertEqual(seen[2],parent);self.assertEqual(requests,parent/'source-final-requests')
   self.assertNotIn(w,seen)
if __name__=='__main__':unittest.main()
