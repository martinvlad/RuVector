"""Frozen E30 algorithm and allocation; standard-library-only source constants."""
KIND = 'REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
CODEC = 'epoch30-bart-crossattn-r4-f32le-v1'
SEED = 30030
MODULES = (
    'model.decoder.layers.10.encoder_attn.q_proj',
    'model.decoder.layers.10.encoder_attn.v_proj',
    'model.decoder.layers.11.encoder_attn.q_proj',
    'model.decoder.layers.11.encoder_attn.v_proj',
)
HEAD_NAMES = (
    'classification_head.dense.weight', 'classification_head.dense.bias',
    'classification_head.out_proj.weight', 'classification_head.out_proj.bias',
)
HEAD_SHAPES = ((1024, 1024), (1024,), (3, 1024), (3,))
EXPECTED_TENSORS = tuple((name + suffix, shape) for name in MODULES
    for suffix, shape in (('.lora_A', (4, 1024)), ('.lora_B', (1024, 4)))) + tuple(zip(HEAD_NAMES, HEAD_SHAPES))
TRAIN_DOCUMENT_IDS = (237, 120, 187, 422, 464, 207, 294, 250)
DEV_DOCUMENT_IDS = (594, 343, 394, 103, 403, 481, 154, 306)
HYPOTHESIS_IDS = ('nda-17', 'nda-7', 'nda-3')
TRAIN_CASE_IDS = tuple(f'original-contractnli:train:epoch30:train:{document}:{hypothesis}'
    for document in TRAIN_DOCUMENT_IDS for hypothesis in HYPOTHESIS_IDS)
DEV_CASE_IDS = tuple(f'original-contractnli:train:epoch30:dev:{document}:{hypothesis}'
    for document in DEV_DOCUMENT_IDS for hypothesis in HYPOTHESIS_IDS)
BASE_MODEL = {
    'repository': 'facebook/bart-large-mnli',
    'revision': 'd7645e127eaf1aefc7862fd59a17a5aa8558b8ce',
    'weights_file': 'pytorch_model.bin', 'weights_bytes': 1629486723,
    'weights_sha256': 'ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17',
    'pretrained_parameter_count': 407344131,
}
TRAINABLE_COUNT, FROZEN_COUNT, PARAMETER_BYTES = 1085443, 406291456, 4341772
ALGORITHM = {
    'name': 'original2020-BART-final2-crossattention-qv-r4-plus-existing-head-one-epoch',
    'seed': SEED, 'module_order': list(MODULES),
    'lora': {'rank': 4, 'alpha': 8, 'scale': 2.0, 'dropout': 0,
        'A_initialization': 'uniform[-1/32,1/32] dedicated CPU generator seed30030, module order fixed',
        'B_initialization': 'exact zero', 'global_seed_reset_immediately_before_injection': True},
    'existing_pretrained_head_parameters': list(HEAD_NAMES),
    'trainable_parameters': TRAINABLE_COUNT, 'frozen_pretrained_parameters': FROZEN_COUNT,
    'optimizer': {'name': 'AdamW', 'learning_rate': 0.0001, 'weight_decay': 0.01,
        'betas': [0.9, 0.999], 'epsilon': 1e-8, 'foreach': False, 'fused': False,
        'amsgrad': False, 'maximize': False, 'capturable': False, 'differentiable': False},
    'objective': 'unweighted native-C/N/E three-way cross entropy; equal example weights',
    'gradient_clip_global_norm': 1.0, 'model_mode': 'eval with gradients enabled only during TRAIN',
    'gradient_integrity_gate': 'Each of four LoRA B tensors has a finite nonzero gradient in at least one of24 fixed updates; all intended tensors changed and effective BA deltas nonzero; every other pretrained parameter bit-unchanged.',
    'dropout': 'all disabled by recursive eval mode', 'precision': 'CPU float32',
    'attention': 'sdpa', 'use_cache': False, 'max_true_pair_tokens': 512,
    'batch_size': 1, 'epochs': 1, 'training_steps': 24,
    'train_case_order': list(TRAIN_CASE_IDS),
    'DEV_order': 'fresh original native24 before reading/applying learned tensor values, then adapted native/lexical/positional72',
    'temperature': 1.0, 'raw_logit_order': ['contradiction', 'not_mentioned', 'entailment'],
    'canonical_probability_permutation': [2, 0, 1],
    'threeway_tie_rule': 'first maximum in native C,N,E order',
    'binary_rule': 'Yes=P(E),No=P(C)+P(N);Yes only ifP(E)>0.5, exact-half No',
    'no_early_stopping_checkpoint_selection_calibration_or_retry': True,
    'attribution': {'base_model_license': 'MIT; retain pinned fairseq model licence/copyright',
        'base_license_source': 'experiments/sota-2026-10-22/candidate/epoch27/reader/LICENSE.fairseq',
        'legal_training_data_license': 'CC-BY-4.0',
        'legal_training_data_citation': 'Koreeda and Manning (2021), ContractNLI',
        'legal_training_source_revision': 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
        'legal_training_source_sha256': 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5',
        'change_notice': 'Rank4 final-decoder cross-attention LoRA and existing classifier adapted on exactly24 fixed TRAIN choices; no DEV/CONF choice fit.'},
}
