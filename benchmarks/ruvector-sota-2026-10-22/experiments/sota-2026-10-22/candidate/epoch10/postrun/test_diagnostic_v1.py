"""Small synthetic arithmetic and fail-closed controls for postrun tooling."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch10_diagnostic', HERE/'build_diagnostic_v1.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)

class DiagnosticTests(unittest.TestCase):
    def test_auxiliary_probability_metrics_and_ties(self):
        values = D.probability_metrics([.8,.8,.2,.2],[1,0,1,0])
        self.assertEqual(values['auc_pairwise_tie_half'],.5)
        self.assertAlmostEqual(values['brier'],.34)
        self.assertEqual(D.decision({'Yes':.5,'No':.5}),'No')
        model={'mean':[0,0],'scale':[1,1],'weights':[0,2]}
        self.assertAlmostEqual(D.aux_probability(model,[1,0]),.5)
        self.assertAlmostEqual(D.aux_probability(model,[1,1]),1/(1+np.exp(-2)))

    def test_unclosed_study_stops_before_any_output_or_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);study=root/(D.PREFIX+'epoch10');study.mkdir(parents=True)
            (study/'study-completion.json').write_text(json.dumps({'finished_at':None,'allowed_further_attempts_in_closed_study':0}))
            with self.assertRaisesRegex(ValueError,'Terminal closed'):D.build(root,root,root/'forbidden-confirmation-labels.json')

    def test_cached_ann_arithmetic_and_digest_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'bundles').mkdir()
            bundle={'vectors':[[1,0],[0,1],[-1,0]],'query_vectors':[[1,0]]};literal=json.dumps(bundle).encode()
            digest=hashlib.sha256(literal).hexdigest();path=folder/'bundles'/f'{digest}.json';path.write_bytes(literal)
            retrieval={'bundle_evidence':{'relativefilename':path.name,'sha256':digest,'bytes':len(literal)},'native':{'queries':[{'ids':[1,0,2]}]}}
            records=[{'id':'synthetic','response':{'diagnostics':{'decision':{'retrieval':retrieval}}}}]
            out=D.ann_diagnostic(records,folder)
            self.assertEqual(out['queries_with_rank_position_difference'],1)
            self.assertEqual(out['mean_topk_set_overlap_fraction'],1)
            self.assertEqual(out['max_top1_cosine_distance_regret'],1)
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError,'bundle missing or changed'):D.ann_diagnostic(records,folder)

    def test_auditor_projection_requires_output_hash_and_exact_consumed_identities(self):
        records = [{'id':str(i),'source_group':'group-'+str(i//3),'provenance':{'hypothesis_id':'h-'+str(i%3)},
                    'evaluation':{'original_threeway_label':'Entailment'},'input_sha256':'sha-'+str(i),'input':{'state':'synthetic'}} for i in range(24)]
        projection={'only_consumed_DEV_hypotheses':True,'confirmation_records_or_labels_included':False,
                    'saved_DEV_records_sha256':'records','queries':24,'document_groups':8,
                    'records':[{'id':r['id'],'source_group':r['source_group'],'hypothesis_id':r['provenance']['hypothesis_id'],
                                'gold_threeway':'Entailment','annotation_spans':[[0,3]]} for r in records]}
        normalized=D.normalize_dev_projection(projection,records,'records')
        self.assertEqual(normalized['role'],'development');self.assertEqual(len(normalized['records']),24)
        with self.assertRaisesRegex(ValueError,'binding invalid'):D.normalize_dev_projection(projection,records,'changed')
        projection['confirmation_records_or_labels_included']=True
        with self.assertRaisesRegex(ValueError,'binding invalid'):D.normalize_dev_projection(projection,records,'records')

    def test_numeric_retention_and_dev_only_annotation_guard(self):
        state='Contract is24 months.';a=state.index('24');b=a+2
        coverage={'selected_source_spans':[[a,b]],'numeric_mentions':[{'span':[a,b],'text':'24','retained':True}],'document_character_coverage':2/len(state)}
        row={'id':'synthetic','source_group':'one','input':{'state':state},'input_sha256':'synthetic','evaluation':{'original_threeway_label':'Entailment'},
             'response':{'diagnostics':{'decision':{'arms':{s:{'coverage':coverage} for s in D.SELECTORS}}}}}
        annotations={'role':'development','queries':1,'records':[{'id':'synthetic','input_sha256':'synthetic','source_group':'one',
            'source_document_sha256':hashlib.sha256(state.encode()).hexdigest(),'original_threeway_label':'Entailment','evidence_spans':[[a,b]]}]}
        out=D.retention([row],annotations)
        self.assertEqual(out['aggregate']['ruvector_top2']['full_annotation_retained'],1)
        annotations['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'consumed DEV'):D.retention([row],annotations)

if __name__=='__main__':unittest.main()
