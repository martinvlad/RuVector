---
license: apache-2.0
language: en
tags:
- deberta-v3-large
- text-classification
- nli
- natural-language-inference
- multitask
- multi-task
- pipeline
- extreme-multi-task
- extreme-mtl
- tasksource
- zero-shot
- rlhf
pipeline_tag: zero-shot-classification
datasets:
- glue
- super_glue
- anli
- metaeval/babi_nli
- sick
- snli
- scitail
- hans
- alisawuffles/WANLI
- metaeval/recast
- sileod/probability_words_nli
- joey234/nan-nli
- pietrolesci/nli_fever
- pietrolesci/breaking_nli
- pietrolesci/conj_nli
- pietrolesci/fracas
- pietrolesci/dialogue_nli
- pietrolesci/mpe
- pietrolesci/dnc
- pietrolesci/gpt3_nli
- pietrolesci/recast_white
- pietrolesci/joci
- martn-nguyen/contrast_nli
- pietrolesci/robust_nli
- pietrolesci/robust_nli_is_sd
- pietrolesci/robust_nli_li_ts
- pietrolesci/gen_debiased_nli
- pietrolesci/add_one_rte
- metaeval/imppres
- pietrolesci/glue_diagnostics
- hlgd
- paws
- quora
- medical_questions_pairs
- conll2003
- Anthropic/hh-rlhf
- Anthropic/model-written-evals
- truthful_qa
- nightingal3/fig-qa
- tasksource/bigbench
- bigbench
- blimp
- cos_e
- cosmos_qa
- dream
- openbookqa
- qasc
- quartz
- quail
- head_qa
- sciq
- social_i_qa
- wiki_hop
- wiqa
- piqa
- hellaswag
- pkavumba/balanced-copa
- 12ml/e-CARE
- art
- tasksource/mmlu
- winogrande
- codah
- ai2_arc
- definite_pronoun_resolution
- swag
- math_qa
- metaeval/utilitarianism
- mteb/amazon_counterfactual
- SetFit/insincere-questions
- SetFit/toxic_conversations
- turingbench/TuringBench
- trec
- tals/vitaminc
- hope_edi
- strombergnlp/rumoureval_2019
- ethos
- tweet_eval
- discovery
- pragmeval
- silicone
- lex_glue
- papluca/language-identification
- imdb
- rotten_tomatoes
- ag_news
- yelp_review_full
- financial_phrasebank
- poem_sentiment
- dbpedia_14
- amazon_polarity
- app_reviews
- hate_speech18
- sms_spam
- humicroedit
- snips_built_in_intents
- banking77
- hate_speech_offensive
- yahoo_answers_topics
- pacovaldez/stackoverflow-questions
- zapsdcn/hyperpartisan_news
- zapsdcn/sciie
- zapsdcn/citation_intent
- go_emotions
- scicite
- liar
- relbert/lexical_relation_classification
- metaeval/linguisticprobing
- metaeval/crowdflower
- metaeval/ethics
- emo
- google_wellformed_query
- tweets_hate_speech_detection
- has_part
- wnut_17
- ncbi_disease
- acronym_identification
- jnlpba
- species_800
- SpeedOfMagic/ontonotes_english
- blog_authorship_corpus
- launch/open_question_type
- health_fact
- commonsense_qa
- mc_taco
- ade_corpus_v2
- prajjwal1/discosense
- circa
- YaHi/EffectiveFeedbackStudentWriting
- Ericwang/promptSentiment
- Ericwang/promptNLI
- Ericwang/promptSpoke
- Ericwang/promptProficiency
- Ericwang/promptGrammar
- Ericwang/promptCoherence
- PiC/phrase_similarity
- copenlu/scientific-exaggeration-detection
- quarel
- mwong/fever-evidence-related
- numer_sense
- dynabench/dynasent
- raquiba/Sarcasm_News_Headline
- sem_eval_2010_task_8
- demo-org/auditor_review
- medmcqa
- aqua_rat
- RuyuanWan/Dynasent_Disagreement
- RuyuanWan/Politeness_Disagreement
- RuyuanWan/SBIC_Disagreement
- RuyuanWan/SChem_Disagreement
- RuyuanWan/Dilemmas_Disagreement
- lucasmccabe/logiqa
- wiki_qa
- metaeval/cycic_classification
- metaeval/cycic_multiplechoice
- metaeval/sts-companion
- metaeval/commonsense_qa_2.0
- metaeval/lingnli
- metaeval/monotonicity-entailment
- metaeval/arct
- metaeval/scinli
- metaeval/naturallogic
- onestop_qa
- demelin/moral_stories
- corypaik/prost
- aps/dynahate
- metaeval/syntactic-augmentation-nli
- metaeval/autotnli
- lasha-nlp/CONDAQA
- openai/webgpt_comparisons
- Dahoas/synthetic-instruct-gptj-pairwise
- metaeval/scruples
- metaeval/wouldyourather
- sileod/attempto-nli
- metaeval/defeasible-nli
- metaeval/help-nli
- metaeval/nli-veridicality-transitivity
- metaeval/natural-language-satisfiability
- metaeval/lonli
- metaeval/dadc-limit-nli
- ColumbiaNLP/FLUTE
- metaeval/strategy-qa
- openai/summarize_from_feedback
- metaeval/folio
- metaeval/tomi-nli
- metaeval/avicenna
- stanfordnlp/SHP
- GBaker/MedQA-USMLE-4-options-hf
- sileod/wikimedqa
- declare-lab/cicero
- amydeng2000/CREAK
- metaeval/mutual
- inverse-scaling/NeQA
- inverse-scaling/quote-repetition
- inverse-scaling/redefine-math
- metaeval/puzzte
- metaeval/implicatures
- race
- metaeval/spartqa-yn
- metaeval/spartqa-mchoice
- metaeval/temporal-nli
metrics:
- accuracy
library_name: transformers
---

# Model Card for DeBERTa-v3-large-tasksource-nli

DeBERTa-v3-large fine-tuned with multi-task learning on 600 tasks of the [tasksource collection](https://github.com/sileod/tasksource/)
You can further fine-tune this model to use it for any classification or multiple-choice task.
This checkpoint has strong zero-shot validation performance on many tasks (e.g. 77% on WNLI).
The untuned model CLS embedding also has strong linear probing performance (90% on MNLI), due to the multitask training.

This is the shared model with the MNLI classifier on top. Its encoder was trained on many datasets including bigbench, Anthropic rlhf, anli... alongside many NLI and classification tasks with a SequenceClassification heads while using only one shared encoder.
Each task had a specific CLS embedding, which is dropped 10% of the time to facilitate model use without it. All multiple-choice model used the same classification layers. For classification tasks, models shared weights if their labels matched.
The number of examples per task was capped to 64k. The model was trained for 80k steps with a batch size of 384, and a peak learning rate of 2e-5.


tasksource training code: https://colab.research.google.com/drive/1iB4Oxl9_B5W3ZDzXoWJN-olUbqLBxgQS?usp=sharing

### Software
https://github.com/sileod/tasksource/ \
https://github.com/sileod/tasknet/ \
Training took 6 days on Nvidia A100 40GB GPU.



# Citation

More details on this [article:](https://arxiv.org/abs/2301.05948) 
```bib
@article{sileo2023tasksource,
  title={tasksource: Structured Dataset Preprocessing Annotations for Frictionless Extreme Multi-Task Learning and Evaluation},
  author={Sileo, Damien},
  url= {https://arxiv.org/abs/2301.05948},
  journal={arXiv preprint arXiv:2301.05948},
  year={2023}
}
```

# Loading a specific classifier
Classifiers for all tasks available. See https://huggingface.co/sileod/deberta-v3-large-tasksource-adapters

<img src="https://www.dropbox.com/s/eyfw8i1ekzxj3fa/task_embeddings.png?dl=1"  width="1000" height="">


# Model Card Contact

damien.sileo@inria.fr


</details>