"""Three pure path/ref guards only; never invokes actual control generation."""
from pathlib import Path
import hashlib,importlib.util,tempfile,unittest
TARGET=Path(__file__).resolve().parents[1]/'preparation/build_controls.py'
spec=importlib.util.spec_from_file_location('control_source_only',TARGET)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class ControlPaths(unittest.TestCase):
 def test_regular_ref_and_relative_escape_rejection(self):
  with tempfile.TemporaryDirectory()as tmp:
   base=Path(tmp);root=base/'root';root.mkdir();(root/'x.json').write_bytes(b'{}\n');(base/'outside.json').write_bytes(b'{}')
   self.assertEqual(M.ref(root,'x.json'),{'path':'x.json','bytes':3,'sha256':hashlib.sha256(b'{}\n').hexdigest()})
   for name in ('../outside.json','/outside.json','x/../x.json','./x.json','x\\file.json'):
    with self.assertRaises((AssertionError,ValueError)):M.ref(root,name)
 def test_dangling_and_symlink_ancestors_rejected(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);real=root/'real';real.mkdir();(real/'x.json').write_bytes(b'{}')
   (root/'alias').symlink_to(real,target_is_directory=True);(root/'dangling').symlink_to(root/'missing')
   for path in (root/'alias/x.json',root/'dangling'):
    with self.assertRaises((AssertionError,ValueError,FileNotFoundError)):M.regular(path)
 def test_directory_is_not_regular_file_and_file_is_not_directory(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);(root/'x.txt').write_text('GENERIC')
   self.assertEqual(M.regular(root,True),root)
   with self.assertRaises(AssertionError):M.regular(root)
   with self.assertRaises(AssertionError):M.regular(root/'x.txt',True)
if __name__=='__main__':unittest.main()
