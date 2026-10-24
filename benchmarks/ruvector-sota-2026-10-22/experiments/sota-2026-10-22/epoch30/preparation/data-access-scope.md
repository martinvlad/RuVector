# Preparation and worker data access

Source preparation constructs and hashes both fixed input-only banks so that their exact bytes can be published before any fitting or model inference. This preparation reads selected source text and hypothesis descriptors, with no annotation choices or evidence-list access.

The published MODEL barrier governs the executable research phases: the TRAIN worker must not read, hash or parse the DEV input bank; the DEV worker must verify the independently read-back MODEL seal before opening its input bank or using learned parameters. Hashing and input-only projection during source preparation do not activate the DEV phase.

Only the fixed 24 TRAIN choices may be joined inside the admitted TRAIN worker. The independent DEV scorer may join the fixed 24 DEV choices only after all 96 predictions and the closed execution receipt have been sealed. A binding pass does not join labels again. Calibration and confirmation roles remain empty. Retrieval absence or truncated context does not establish global insufficient evidence.
