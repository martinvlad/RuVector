"""Source-certified permutation of a retained real raw neural T1 readout.

No fabricated confidence, fitted parameter, label access or extra model call.
The guarantee is conditional on a correct source certificate and SAME readout.
"""
import importlib.util
import math
from pathlib import Path

LABELS=('Entailment','Contradiction','NotMentioned')
POLICY='SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION'
_spec=importlib.util.spec_from_file_location('e37_quantitative_source_logic',Path(__file__).with_name('quantitative.py'))
Q=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(Q)


def raw_checked(reader):
    p=reader['probabilities_E_C_N'];label=reader['native_typed_argmax']
    if (type(p)is not list or len(p)!=3 or label not in LABELS
            or any(type(v)not in(int,float)or not math.isfinite(v)or not 0<=v<=1 for v in p)
            or abs(math.fsum(p)-1)>1e-12 or p[LABELS.index(label)]!=max(p)):
        raise ValueError('Complete finite raw T1 and PROVIDED original raw-logit winner required')
    return p,label


def raw_decision(reader):
    p,label=raw_checked(reader)
    return {'schema_version':1,'epoch':37,'policy':'RAW_T1_CONTROL_NO_CERTIFICATE',
            'raw_probabilities_E_C_N':list(p),'raw_typed_argmax':label,
            'final_probabilities_E_C_N':list(p),'final_typed_argmax':label,
            'permutation':[0,1,2],'certificate':None,'certificate_applied':False,
            'fallback_reason':'raw_control_certificate_not_applied','semantic_decision_override':False,
            'probabilities_changed':False,'extra_NLI_calls':0,'fitting':False,'calibrated_posterior_claim':False,
            'argmax_policy':'Original provided C,N,E raw-logit first maximum'}


def spans_checked(document,premise,spans):
    if type(spans)is not list or not spans:raise ValueError('Nonempty exact source spans required')
    end=0
    for row in spans:
        if (type(row)is not list or len(row)!=2 or any(type(v)is not int for v in row)
                or not 0<=row[0]<row[1]<=len(document)or row[0]<end):
            raise ValueError('Disjoint ascending valid original source spans required')
        end=row[1]
    if premise!='\n\n'.join(document[a:b]for a,b in spans):
        raise ValueError('Measured premise is not exact selected original source')


def decide(document,premise,hypothesis,selected_source_spans,reader):
    p,label=raw_checked(reader);spans_checked(document,premise,selected_source_spans)
    analysis=Q.analyze(document,hypothesis)
    reason=analysis.get('reason');certificate=None
    if analysis['status']=='CERTIFICATE_CANDIDATE':
        missing=[span for span in analysis['required_source_spans']
                 if not any(a<=span[0]and span[1]<=b for a,b in selected_source_spans)]
        if missing:reason='required_source_constraint_not_retrieved'
        else:
            certificate={'schema_version':1,'epoch':37,'grammar':Q.POLICY,
                         'document_sha256':Q.sha(document),'hypothesis_sha256':Q.sha(hypothesis),
                         'premise_sha256':Q.sha(premise),'selected_source_spans':selected_source_spans,
                         'all_required_source_quotes_covered':True,'full_source_analysis':analysis,
                         'conclusion':analysis['proof']['conclusion']}
    target=label if certificate is None else certificate['conclusion'];permutation=[0,1,2]
    if certificate is not None:
        w=LABELS.index(label);c=LABELS.index(target);permutation[w],permutation[c]=permutation[c],permutation[w]
    final=[p[i]for i in permutation]
    if final[LABELS.index(target)]!=max(final):raise ValueError('Certified class not maximal after exact permutation')
    return {'schema_version':1,'epoch':37,'policy':POLICY,
            'raw_probabilities_E_C_N':list(p),'raw_typed_argmax':label,
            'final_probabilities_E_C_N':final,'final_typed_argmax':target,
            'permutation':permutation,'certificate':certificate,'certificate_applied':certificate is not None,
            'fallback_reason':reason,'semantic_decision_override':target!=label,
            'probabilities_changed':final!=p,'extra_NLI_calls':0,'fitting':False,
            'calibrated_posterior_claim':False,'source_analysis':{'status':analysis['status'],'sha256':analysis['analysis_sha256']},
            'argmax_policy':'Valid certificate class first among equal final maxima; otherwise original provided C,N,E raw-logit first maximum'}
