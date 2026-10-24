---
library_name: transformers
license: apache-2.0
base_model: answerdotai/ModernBERT-large
tags:
- generated_from_trainer
model-index:
- name: ModernBERT-large-ft-all-nli
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# ModernBERT-large-ft-all-nli

This model is a fine-tuned version of [answerdotai/ModernBERT-large](https://huggingface.co/answerdotai/ModernBERT-large) on an unknown dataset.
It achieves the following results on the evaluation set:
- Loss: 0.2684
- Accuracy Score: 0.9127

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 8e-05
- train_batch_size: 128
- eval_batch_size: 128
- seed: 42
- optimizer: Use adamw_torch with betas=(0.9,0.98) and epsilon=1e-06 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: linear
- num_epochs: 2

### Training results

| Training Loss | Epoch | Step  | Validation Loss | Accuracy Score |
|:-------------:|:-----:|:-----:|:---------------:|:--------------:|
| 0.3108        | 1.0   | 7360  | 0.2522          | 0.9061         |
| 0.1534        | 2.0   | 14720 | 0.2684          | 0.9127         |


### Framework versions

- Transformers 4.48.0.dev0
- Pytorch 2.5.1+cu121
- Datasets 3.2.0
- Tokenizers 0.21.0
