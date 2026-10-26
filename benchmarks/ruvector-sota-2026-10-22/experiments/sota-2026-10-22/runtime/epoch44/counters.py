"""Actual operation accounting; logical completions are not backend batches."""
FIXED_NAMES = [
    "corpus_batches_attempted", "corpus_batches_completed", "native_helper_starts_attempted",
    "native_helper_starts_completed", "native_binary_loads_attempted", "native_binary_loads_completed",
    "native_index_initializations_attempted", "native_index_initializations_completed",
    "native_insertions_attempted", "native_insertions_completed", "native_queries_attempted",
    "native_queries_completed", "native_len_calls_attempted", "native_len_calls_completed",
    "native_version_calls_attempted", "native_version_calls_completed", "native_hit_source_validations",
    "Node_network_operations_attempted", "BGE_initializations_attempted", "BGE_initializations_completed",
    "ORT_sessions_attempted", "ORT_sessions_completed", "BGE_forward_calls_attempted",
    "BGE_forward_calls_completed", "BGE_texts_attempted", "BGE_texts_completed",
    "reader_server_starts_attempted", "reader_server_starts_completed", "reader_server_stops_attempted",
    "reader_server_stops_completed", "local_HTTP_requests_attempted", "local_HTTP_requests_completed",
    "health_requests_attempted", "health_requests_completed", "metadata_requests_attempted",
    "metadata_requests_completed", "label_tokenize_requests_attempted", "label_tokenize_requests_completed",
    "prompt_tokenize_requests_attempted", "prompt_tokenize_requests_completed",
    "completion_requests_attempted", "completion_requests_completed", "first_answer_token_draws_observed",
    "forecasts_completed", "feature_cases_admitted", "feature_documents_admitted", "semantic_gold_decodes",
    "training_calls", "calibration_calls", "confirmation_calls", "paid_API_calls", "GPU_calls",
]


def initial(): return {name: 0 for name in FIXED_NAMES}


def expected_fixed(doc_counts):
    if len(doc_counts) != 4 or any(type(n) is not int or not 1 <= n <= 1024 for n in doc_counts.values()):
        raise ValueError("EXACT_FOUR_SOURCE_COUNTS")
    units = sum(doc_counts.values()); batches = sum((n + 7) // 8 for n in doc_counts.values()) + 12
    e = {"corpus_batches_attempted":1, "corpus_batches_completed":1,
         "native_helper_starts_attempted":1, "native_helper_starts_completed":1,
         "native_binary_loads_attempted":1, "native_binary_loads_completed":1,
         "native_index_initializations_attempted":4, "native_index_initializations_completed":4,
         "native_insertions_attempted":units, "native_insertions_completed":units,
         "native_queries_attempted":12, "native_queries_completed":12,
         "native_len_calls_attempted":8, "native_len_calls_completed":8,
         "native_version_calls_attempted":1, "native_version_calls_completed":1,
         "native_hit_source_validations":3*units, "Node_network_operations_attempted":0,
         "BGE_initializations_attempted":1, "BGE_initializations_completed":1,
         "ORT_sessions_attempted":1, "ORT_sessions_completed":1,
         "BGE_forward_calls_attempted":batches, "BGE_forward_calls_completed":batches,
         "BGE_texts_attempted":units+12, "BGE_texts_completed":units+12,
         "feature_cases_admitted":12, "feature_documents_admitted":4,
         "reader_server_starts_attempted":1, "reader_server_starts_completed":1,
         "reader_server_stops_attempted":1, "reader_server_stops_completed":1,
         "label_tokenize_requests_attempted":3, "label_tokenize_requests_completed":3,
         "metadata_requests_attempted":1, "metadata_requests_completed":1,
         "completion_requests_attempted":36, "completion_requests_completed":36,
         "first_answer_token_draws_observed":36, "forecasts_completed":36}
    for name in ("semantic_gold_decodes", "training_calls", "calibration_calls", "confirmation_calls",
                 "paid_API_calls", "GPU_calls"): e[name] = 0
    return e
