"""Engineering-only active BPE pair/offset conservation; no benchmark inference."""
import importlib.util
import hashlib
from pathlib import Path
import unittest
from tokenizers import Tokenizer
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('epoch13_context_engineering',HERE.parent/'epoch6/context.py')
context=importlib.util.module_from_spec(spec);spec.loader.exec_module(context)

class ContextEngineering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nli=Tokenizer.from_file(str(HERE/'assets/official-roberta-base/tokenizer.json'))
        cls.nli.no_padding();cls.nli.no_truncation()
        cls.bge=Tokenizer.from_file(str(HERE.parents[3]/'models/bge-small-en-v1.5/tokenizer.json'))
        cls.bge.no_padding();cls.bge.no_truncation()

    def test_reviewed_algorithm_identity(self):
        self.assertEqual(hashlib.sha256((HERE.parent/'epoch6/context.py').read_bytes()).hexdigest(),'28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2')

    def test_actual_roberta_wholepair_serialization(self):
        a,b='Evidence with café and 日本語.', 'The entire whole claim remains.'
        left=self.nli.encode(a,add_special_tokens=False).ids
        right=self.nli.encode(b,add_special_tokens=False).ids
        pair=self.nli.encode(a,b)
        self.assertEqual(pair.ids,[0]+left+[2,2]+right+[2])
        self.assertEqual(set(pair.type_ids),{0})
        self.assertEqual(set(pair.attention_mask),{1})

    def test_unicode_whitespace_and_oversize_complete_source_conservation(self):
        sources=[
            '  Préambule 日本語 😀.\n\n  Section\t2;   retained text.\n ',
            ('é日本語😀 αβγ\t ' * 350)+'unbrokenTAIL',
            ('word'*1000)+'\n\n'+('   spaced word; '*150),
        ]
        for source in sources:
            with self.subTest(bytes=len(source.encode())):
                units=context.partition(source,self.nli,self.bge)
                self.assertEqual(units[0]['start'],0)
                self.assertEqual(units[-1]['end'],len(source))
                self.assertTrue(all(a['end']==b['start'] for a,b in zip(units,units[1:])))
                self.assertEqual(''.join(source[u['start']:u['end']] for u in units),source)
                for u in units:
                    part=source[u['start']:u['end']]
                    self.assertLessEqual(len(self.nli.encode(part,add_special_tokens=False).ids),160)
                    self.assertLessEqual(len(self.bge.encode(part).ids),256)
                ranking=list(range(min(40,len(units))))
                premise,trace=context.pack(source,units,ranking,'Whole numerical claim is 12.5 percent.',self.nli)
                self.assertLessEqual(len(self.nli.encode(premise,'Whole numerical claim is 12.5 percent.').ids),512)
                self.assertFalse(trace['selected_evidence_truncated'])
                self.assertFalse(trace['claim_truncated'])

if __name__=='__main__':unittest.main()
