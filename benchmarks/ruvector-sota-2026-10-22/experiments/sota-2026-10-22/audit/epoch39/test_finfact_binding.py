import copy,tempfile,unittest
from pathlib import Path
import finfact_io as I
import finfact_scorer as S
class Bind(unittest.TestCase):
 def test_exact_preservation_and_separate_binding(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);v={'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','checks_passed':True,'dev_passed':False,'source_plan_sha256':'1'*64,'retained_unexpected_diagnostic':{'no_field_dropped':42}};er=I.put(root/'evaluation.json',v);result={**copy.deepcopy(v),'publication_checkpoint':{'qualification_replay':er}};rr=I.put(root/'results.json',result);b=S.bind(er,rr,root);self.assertTrue(b['publication_binding_checks_passed']);self.assertFalse(b['dev_passed']);result.pop('retained_unexpected_diagnostic');bad=I.put(root/'bad.json',result)
   with self.assertRaisesRegex(ValueError,'PRESERVE_EVERY'):S.bind(er,bad,root)
if __name__=='__main__':unittest.main()
