"""Fixed equal-weight probability mixture; no fitting, confidence override or NEI rule."""
import math

LABELS=('NotMentioned','Entailment','Contradiction')


def two_window_mixture(log_probabilities):
    if type(log_probabilities)is not list or len(log_probabilities)!=2:raise ValueError('EXACTLY_TWO_REAL_WINDOW_OUTPUTS_REQUIRED')
    for row in log_probabilities:
        if type(row)is not list or len(row)!=3 or any(type(x)not in(int,float)or not math.isfinite(x)or x>1e-12 for x in row):
            raise ValueError('FINITE_THREEWAY_LOG_PROBABILITIES_REQUIRED')
        if abs(sum(math.exp(x)for x in row)-1)>1e-12:raise ValueError('UNNORMALIZED_WINDOW_OUTPUT')
    logs=[]
    for a,b in zip(*log_probabilities):
        maximum=max(a,b);logs.append(maximum+math.log(math.exp(a-maximum)+math.exp(b-maximum))-math.log(2))
    probabilities=[math.exp(value)for value in logs]
    if abs(sum(probabilities)-1)>1e-12:raise AssertionError('MIXTURE_NORMALIZATION')
    winner=max(range(3),key=lambda i:logs[i])
    return {'probabilities_N_E_C':probabilities,'log_probabilities_N_E_C':logs,
        'canonical_argmax_index':winner,'primary_label':LABELS[winner],
        'aggregation':'EQUAL_WEIGHT_ARITHMETIC_PROBABILITY_MIXTURE_TWO_REAL_WINDOWS',
        'real_window_outputs_required':2,'retrieval_miss_absence_inference':False}
