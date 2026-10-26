"""Disjoint fake-encoding contract; no actual tokenizer/model/native/guard calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('e42_retained_packing_source',Path(__file__).with_name('context_windows.py'))
W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)


def digest(value):
    body=value.encode()if isinstance(value,str)else json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


class RetainedPacking(unittest.TestCase):
    def prepare(self):
        rows=W.sentence_catalog('Audit alloy. Audit reserve. Audit consent. Audit duration. Audit remedy.')
        claim='Invented audit assertion';journal=[];lookups={};calls=[0]
        def fake_count(premise,hypothesis):
            calls[0]+=1;count=3+200*premise.count('.')
            features={'input_ids':list(range(count)),'attention_mask':[1]*count}
            receipt={'premise_sha256':digest(premise),'claim_sha256':digest(hypothesis),
                'features':features,'joint_tokens':count,'features_sha256':digest(features)}
            journal.append(receipt);lookups[(receipt['premise_sha256'],receipt['claim_sha256'])]=receipt
            return count
        packed=W.build_windows(rows,list(range(5)),claim,fake_count)
        return rows,claim,journal,lookups,calls,packed

    def test_postclosure_replay_uses_only_retained_counts_and_features(self):
        rows,claim,journal,lookups,calls,expected=self.prepare();initial=calls[0]
        def retained_count(premise,hypothesis):
            receipt=lookups[(digest(premise),digest(hypothesis))]
            self.assertEqual(receipt['joint_tokens'],len(receipt['features']['input_ids']))
            self.assertEqual(receipt['features_sha256'],digest(receipt['features']))
            return receipt['joint_tokens']
        observed=W.build_windows(rows,list(range(5)),claim,retained_count)
        self.assertEqual(observed,expected);self.assertEqual(calls[0],initial)
        self.assertEqual(len(journal),expected['packing_pair_tokenizer_calls'])
        for window in observed['windows']:
            receipt=lookups[(window['premise_sha256'],digest(claim))]
            self.assertEqual(receipt['joint_tokens'],window['joint_tokens'])

    def test_missing_retained_lookup_fails_without_encoding_fallback(self):
        rows,claim,journal,lookups,calls,_=self.prepare();initial=calls[0]
        del lookups[(digest(''),digest(claim))]
        with self.assertRaises(KeyError):
            W.build_windows(rows,list(range(5)),claim,
                lambda premise,hypothesis:lookups[(digest(premise),digest(hypothesis))]['joint_tokens'])
        self.assertEqual(calls[0],initial)


if __name__=='__main__':unittest.main()
