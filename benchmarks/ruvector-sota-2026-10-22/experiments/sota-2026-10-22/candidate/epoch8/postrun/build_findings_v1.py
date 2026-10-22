"""Summarize only the saved TRAIN/DEV diagnostic; no inference or fitting."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

EXPECTED_DIAGNOSTIC_SHA256 = 'a525fabe7da933531c81a2f60c01a4e605e0ddd0e50048e9c87847153b3da93b'


def identity(path):
    data = path.read_bytes()
    return {'filename': path.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def build(path):
    if identity(path)['sha256'] != EXPECTED_DIAGNOSTIC_SHA256:
        raise ValueError('This version describes only the exact pinned saved-output diagnostic')
    data = json.loads(path.read_text())
    if not data['full_DEV_diagnostic_available']:
        raise ValueError('This findings version requires the full saved fitted-head DEV24')
    cases = data['DEV_cases']
    coverage = {row['id']: row for row in data['source_annotation_numeric_coverage']['cases']}
    coverage_correctness = {}
    for arm in data['DEV_summary']:
        counts = collections.Counter()
        for case in cases:
            value = coverage[case['id']]['selectors'][arm]
            category = ('no_annotated_evidence' if not value['annotation_available'] else
                        'all_annotated_characters' if value['all_annotation_characters_retained'] else
                        'partial_annotated_characters' if value['any_annotation_overlap'] else 'no_annotated_overlap')
            counts[(category, case['selectors'][arm]['trained_head']['binary']['correct'])] += 1
        coverage_correctness[arm] = [{'coverage': category, 'binary_correct': correct, 'n': count}
                                     for (category, correct), count in sorted(counts.items())]
    by_hypothesis = {}
    for hypothesis in sorted({case['hypothesis_id'] for case in cases}):
        subset = [case for case in cases if case['hypothesis_id'] == hypothesis]
        by_hypothesis[hypothesis] = {'n': len(subset),
            'gold_threeway_counts': dict(collections.Counter(case['gold_threeway'] for case in subset)),
            'trained_binary_correct': {arm: sum(case['selectors'][arm]['trained_head']['binary']['correct'] for case in subset)
                                       for arm in data['DEV_summary']}}
    fit = {key: value for key, value in data['fit_diagnostics'].items() if key != 'history'}
    return {'schema_version': 1,
            'scope': 'Saved-output-only TRAIN/DEV diagnostic. No confirmation records or labels opened, new inference, refit, selection or candidate change.',
            'diagnostic_input': identity(path),
            'DEV_document_groups': 8, 'TRAIN_document_groups': 24,
            'gold_DEV_threeway_counts': dict(collections.Counter(case['gold_threeway'] for case in cases)),
            'gold_TRAIN_threeway_counts': dict(collections.Counter(case['gold_threeway'] for case in data['train_cases'])),
            'DEV_summary': data['DEV_summary'], 'TRAIN_in_sample_summary': data['train_in_sample_summary'],
            'fit_diagnostics_without_history': fit,
            'annotation_coverage_vs_correctness': coverage_correctness,
            'by_hypothesis_descriptive_only': by_hypothesis,
            'findings': [
                'The fitted native arm is 15/24 binary and 16/24 original-threeway on DEV; same-logit raw threeway is 12/24 and 13/24. TRAIN fitted native 50/72 is in-sample, not held-out performance.',
                'Same-model matched retrieval controls are lexical 12/24 and positional 13/24 on DEV. The native-vs-lexical discordances are 7 native-only correct and 4 lexical-only correct, within 8 correlated document groups.',
                'Native binary Brier falls from .7426115332 to .4600432614 and NLL from 1.2053257890 to .6475783825 relative to the predeclared full-threeway raw same-logit reference. High-confidence wrong predictions at confidence >= .8 fall from 8 to 0; none of these offline comparisons selects a candidate or changes a gate.',
                'The historical discarded-neutral reference predicts Yes 21/24, the fitted native arm 14/24, and gold Yes 13/24. This is a same-logit reference comparison on this split, not evidence of causal gain against a different historical epoch.',
                'Native-selected context overlaps annotation evidence on 14/15 annotated queries and retains all annotated characters on 10/15. Three of those 10 fully retained cases remain binary errors. Both 2 DEV Contradiction labels are predicted Entailment by the native threeway head; this is a small descriptive error slice, not a tuned threshold.',
                'Numeric retention is 185/813 query-level occurrences for native, 148/813 lexical and 204/813 positional. These repeat each document 3 times and establish exact source exposure only, not factual sufficiency or numeric reasoning.'
            ],
            'one_next_direction': {
                'status': 'Unimplemented, unmeasured future hypothesis; no automatic execution or change to this closed study',
                'hypothesis': 'Train a clause-level legal contradiction/sufficiency head using TRAIN-only evidence annotations and explicit actor/action/modality/condition bindings, retaining separate Entailment/Contradiction/NotMentioned targets. Apply one frozen readout and unchanged input budget to every retrieval arm.',
                'motivation': 'Fully retained evidence still has decision errors and contradiction recall is 0/2 on this DEV; greater retrieval exposure alone cannot guarantee scope/polarity understanding.',
                'separation': 'Freeze source rule, objective and document-group split before new held-out labels. Do not tune thresholds, refit, promote an offline reference, or reuse consumed DEV/confirmation as fresh evidence.'},
            'limitations': ['8 DEV document groups, 3 correlated hypotheses each; no independent-query confidence claim.',
                            'Training full-document labels supervise selected excerpts; annotation coverage is not sufficiency.',
                            'Public-data pretraining contamination unknown. No official leaderboard score/rank or cross-epoch causal model-gain claim.',
                            'Only saved TRAIN and DEV rows were analyzed. Confirmation aggregate status exists in the terminal input manifest, but no confirmation cases/labels were opened by this analysis.'],
            'new_model_calls': 0, 'new_native_calls': 0, 'new_optimizer_fits': 0, 'frozen_source_changes': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnostic', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.diagnostic)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(identity(args.output)))


if __name__ == '__main__':
    main()
