# E31 fixed archived legal adaptation diagnostic

This single DEV batch measures one fixed E30 learned state on the eight prospectively fixed E31 documents. It compares original BART on the 24 native contexts with the archived state on the same 24 native contexts plus 24 lexical and 24 positional contexts. Quality is unknown. The backbone and training recipe are unchanged, and this epoch performs no training.

The new `algorithm.py` and `model.py` are source-pinned wrappers around the unchanged E30 algorithm/model/parameter codec. The archived artifact retains its E30 epoch, kind, seed30030, source plan and TRAIN input identity. The current archive seal records new execution binding separately. Current TRAIN, calibration and CONF roles are empty.

The worker admits actual current SOURCE readback, archive seal, exact archived provenance, runtime/source pins, CPU guard and owned worker identity before reading the DEV bank. All 24 original native forwards finish before learned tensor decode/load. It then loads exactly one archived state and performs 72 adapted forwards. It retains C/N/E outputs at temperature1 and paired input hashes. It performs no fitting, generation, HTTP, full104 comparison or confirmation.

`EXPECTED_COUNTERS.json`, `INFERENCE_CONTRACT.json`, `RAW_SCHEMA.json` and `runtime/RUNTIME_CONTRACT.json` describe the exact wire contracts. `runtime/preflight.py` uses synthetic metadata/authored strings and small stdlib processes only. The historical fixed-hash artifact admission fixtures are explicitly mocked; they never read real archived tensors, weights or data.

This is a DEV diagnostic, with no benchmark acceptance, champion promotion, new backbone claim or generalization claim. Foundation-text overlap and historical lineage limitations remain in force.
