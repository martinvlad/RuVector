---
library_name: transformers
base_model:
- answerdotai/ModernBERT-base
license: apache-2.0
language:
- en
pipeline_tag: zero-shot-classification
datasets:
- nyu-mll/glue
- facebook/anli
tags:
- instruct
- natural-language-inference
- nli
- mnli
---

# Model Card for Model ID

ModernBERT multi-task fine-tuned on tasksource NLI tasks, including MNLI, ANLI, SICK, WANLI, doc-nli, LingNLI, FOLIO, FOL-NLI, LogicNLI, Label-NLI and all datasets in the below table).
This is the equivalent of an "instruct" version.
The model was trained for 200k steps on an Nvidia A30 GPU.

It is very good at reasoning tasks (better than llama 3.1 8B Instruct on ANLI and FOLIO), long context reasoning, sentiment analysis and zero-shot classification with new labels. 

The following table shows model test accuracy. These are the scores for the same single transformer with different classification heads on top. Further gains can be obtained by fine-tuning on a single-task, e.g. SST, but it this checkpoint is great for zero-shot classification and natural language inference (contradiction/entailment/neutral classification).


| test_name                             |   test_accuracy |
|:--------------------------------------|----------------:|
| glue/mnli                             |            0.87 |
| glue/qnli                             |            0.93 |
| glue/rte                              |            0.85 |
| glue/mrpc                             |            0.87 |
| glue/qqp                              |            0.9  |
| glue/cola                             |            0.86 |
| glue/sst2                             |            0.96 |
| super_glue/boolq                      |            0.64 |
| super_glue/cb                         |            0.89 |
| super_glue/multirc                    |            0.82 |
| super_glue/wic                        |            0.67 |
| super_glue/axg                        |            0.89 |
| anli/a1                               |            0.66 |
| anli/a2                               |            0.49 |
| anli/a3                               |            0.44 |
| sick/label                            |            0.93 |
| sick/entailment_AB                    |            0.91 |
| snli                                  |            0.83 |
| scitail/snli_format                   |            0.94 |
| hans                                  |            1    |
| WANLI                                 |            0.74 |
| recast/recast_ner                     |            0.87 |
| recast/recast_sentiment               |            0.99 |
| recast/recast_verbnet                 |            0.88 |
| recast/recast_megaveridicality        |            0.88 |
| recast/recast_verbcorner              |            0.94 |
| recast/recast_kg_relations            |            0.91 |
| recast/recast_factuality              |            0.94 |
| recast/recast_puns                    |            0.96 |
| probability_words_nli/reasoning_1hop  |            0.99 |
| probability_words_nli/usnli           |            0.72 |
| probability_words_nli/reasoning_2hop  |            0.98 |
| nan-nli                               |            0.85 |
| nli_fever                             |            0.78 |
| breaking_nli                          |            0.99 |
| conj_nli                              |            0.74 |
| fracas                                |            0.86 |
| dialogue_nli                          |            0.93 |
| mpe                                   |            0.74 |
| dnc                                   |            0.92 |
| recast_white/fnplus                   |            0.82 |
| recast_white/sprl                     |            0.9  |
| recast_white/dpr                      |            0.68 |
| robust_nli/IS_CS                      |            0.79 |
| robust_nli/LI_LI                      |            0.99 |
| robust_nli/ST_WO                      |            0.85 |
| robust_nli/PI_SP                      |            0.74 |
| robust_nli/PI_CD                      |            0.8  |
| robust_nli/ST_SE                      |            0.81 |
| robust_nli/ST_NE                      |            0.86 |
| robust_nli/ST_LM                      |            0.87 |
| robust_nli_is_sd                      |            1    |
| robust_nli_li_ts                      |            0.89 |
| add_one_rte                           |            0.94 |
| paws/labeled_final                    |            0.95 |
| pragmeval/pdtb                        |            0.64 |
| lex_glue/scotus                       |            0.55 |
| lex_glue/ledgar                       |            0.8  |
| dynasent/dynabench.dynasent.r1.all/r1 |            0.81 |
| dynasent/dynabench.dynasent.r2.all/r2 |            0.75 |
| cycic_classification                  |            0.9  |
| lingnli                               |            0.84 |
| monotonicity-entailment               |            0.97 |
| scinli                                |            0.8  |
| naturallogic                          |            0.96 |
| dynahate                              |            0.78 |
| syntactic-augmentation-nli            |            0.92 |
| autotnli                              |            0.94 |
| defeasible-nli/atomic                 |            0.81 |
| defeasible-nli/snli                   |            0.78 |
| help-nli                              |            0.96 |
| nli-veridicality-transitivity         |            0.98 |
| lonli                                 |            0.97 |
| dadc-limit-nli                        |            0.69 |
| folio                                 |            0.66 |
| tomi-nli                              |            0.48 |
| puzzte                                |            0.6  |
| temporal-nli                          |            0.92 |
| counterfactually-augmented-snli       |            0.79 |
| cnli                                  |            0.87 |
| boolq-natural-perturbations           |            0.66 |
| equate                                |            0.63 |
| logiqa-2.0-nli                        |            0.52 |
| mindgames                             |            0.96 |
| ConTRoL-nli                           |            0.67 |
| logical-fallacy                       |            0.37 |
| cladder                               |            0.87 |
| conceptrules_v2                       |            1    |
| zero-shot-label-nli                   |            0.82 |
| scone                                 |            0.98 |
| monli                                 |            1    |
| SpaceNLI                              |            1    |
| propsegment/nli                       |            0.88 |
| FLD.v2/default                        |            0.91 |
| FLD.v2/star                           |            0.76 |
| SDOH-NLI                              |            0.98 |
| scifact_entailment                    |            0.84 |
| AdjectiveScaleProbe-nli               |            0.99 |
| resnli                                |            1    |
| semantic_fragments_nli                |            0.99 |
| dataset_train_nli                     |            0.94 |
| nlgraph                               |            0.94 |
| ruletaker                             |            0.99 |
| PARARULE-Plus                         |            1    |
| logical-entailment                    |            0.86 |
| nope                                  |            0.44 |
| LogicNLI                              |            0.86 |
| contract-nli/contractnli_a/seg        |            0.87 |
| contract-nli/contractnli_b/full       |            0.79 |
| nli4ct_semeval2024                    |            0.67 |
| biosift-nli                           |            0.92 |
| SIGA-nli                              |            0.53 |
| FOL-nli                               |            0.8  |
| doc-nli                               |            0.77 |
| mctest-nli                            |            0.87 |
| natural-language-satisfiability       |            0.9  |
| idioms-nli                            |            0.81 |
| lifecycle-entailment                  |            0.78 |
| MSciNLI                               |            0.85 |
| hover-3way/nli                        |            0.88 |
| seahorse_summarization_evaluation     |            0.73 |
| missing-item-prediction/contrastive   |            0.79 |
| Pol_NLI                               |            0.89 |
| synthetic-retrieval-NLI/count         |            0.64 |
| synthetic-retrieval-NLI/position      |            0.89 |
| synthetic-retrieval-NLI/binary        |            0.91 |
| babi_nli                              |            0.97 |
| gen_debiased_nli                      |            0.91 |


# Usage

## [ZS] Zero-shot classification pipeline
```python
from transformers import pipeline
classifier = pipeline("zero-shot-classification",model="tasksource/ModernBERT-base-nli")

text = "one day I will see the world"
candidate_labels = ['travel', 'cooking', 'dancing']
classifier(text, candidate_labels)
```
NLI training data of this model includes [label-nli](https://huggingface.co/datasets/tasksource/zero-shot-label-nli), a NLI dataset specially constructed to improve this kind of zero-shot classification.

## [NLI] Natural language inference pipeline

```python
from transformers import pipeline
pipe = pipeline("text-classification",model="tasksource/ModernBERT-base-nli")
pipe([dict(text='there is a cat',
  text_pair='there is a black cat')]) #list of (premise,hypothesis)
```

## Backbone for further fune-tuning

This checkpoint has stronger reasoning and fine-grained abilities than the base version and can be used for further fine-tuning.

# Citation

```
@inproceedings{sileo-2024-tasksource,
    title = "tasksource: A Large Collection of {NLP} tasks with a Structured Dataset Preprocessing Framework",
    author = "Sileo, Damien",
    booktitle = "Proceedings of the 2024 Joint International Conference on Computational Linguistics, Language Resources and Evaluation (LREC-COLING 2024)",
    month = may,
    year = "2024",
    address = "Torino, Italia",
    publisher = "ELRA and ICCL",
    url = "https://aclanthology.org/2024.lrec-main.1361",
    pages = "15655--15684",
}
```