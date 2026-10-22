"""Meaningful negative controls for split leakage and false SOTA/calibration claims."""
import copy
from pathlib import Path
import tempfile
import unittest
from verify_epoch_v2 import canonical_input_hash, check_split_isolation, official_sota_gate, paired_diagnostics, proper_scores, sha256, verify_pins


class GateTests(unittest.TestCase):
    def test_float32_tolerance_matches_upstream_strict_rule(self):
        self.assertGreater(proper_scores({"a": .50000004, "b": .50000004}, "a", ["a", "b"])["nll"], 0)
        with self.assertRaises(ValueError):
            proper_scores({"a": .51, "b": .50}, "a", ["a", "b"])

    def test_zero_probabilities_produce_finite_explicitly_clipped_nll(self):
        self.assertGreater(proper_scores({"a": 0, "b": 1}, "a", ["a", "b"])["nll"], 30)

    def test_distribution_rejects_missing_labels_nonfinite_and_bad_total(self):
        for p in ({"a": 1}, {"a": float("nan"), "b": 0}, {"a": .4, "b": .4}, {"a": True, "b": False}):
            with self.assertRaises(ValueError):
                proper_scores(p, "a", ["a", "b"])

    def test_input_duplicates_across_roles_rejected(self):
        x = {"state": "example", "questions": {}}
        records = [{"id": "a", "split": "train", "source_group": "a", "input": x, "input_sha256": canonical_input_hash(x)}, {"id": "b", "split": "confirmation", "source_group": "b", "input": x, "input_sha256": canonical_input_hash(x)}]
        with self.assertRaises(ValueError):
            check_split_isolation(records)

    def test_group_duplicates_with_changed_text_rejected(self):
        records = []
        for i, role in enumerate(["train", "confirmation"]):
            x = {"state": str(i), "questions": {}}
            records.append({"id": str(i), "split": role, "source_group": "shared", "input": x, "input_sha256": canonical_input_hash(x)})
        with self.assertRaises(ValueError):
            check_split_isolation(records)

    def test_unknown_confirmation_exposure_does_not_count_as_fresh(self):
        x = {"state": "new", "questions": {}}
        record = {"id": "new", "split": "confirmation", "source_group": "new", "input": x, "input_sha256": canonical_input_hash(x)}
        with self.assertRaises(ValueError):
            check_split_isolation([record])
        record["previously_loop_used"] = False
        self.assertEqual(check_split_isolation([record])["rows"], 1)

    def test_pin_tampering_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); p = root / "source.py"; p.write_text("original")
            pin = {"path": "source.py", "sha256": sha256(p)}
            self.assertEqual(len(verify_pins([pin], root)), 1)
            link = root / "alias.py"; link.symlink_to(p)
            with self.assertRaises(ValueError):
                verify_pins([{**pin, "path": "alias.py"}], root)
            p.write_text("changed")
            with self.assertRaises(ValueError):
                verify_pins([pin], root)

    def test_empirical_calibration_gain_does_not_invent_official_axis(self):
        rows = [{"id": "x", "gold": "a", "labels": ["a", "b"], "baseline": {"correct": False, "probabilities": {"a": .01, "b": .99}}, "candidate": {"correct": False, "probabilities": {"a": .3, "b": .7}}}]
        result = paired_diagnostics(rows)
        self.assertTrue(result["development_gate_passed"])
        self.assertIsNone(result["official_Calibration"])
        self.assertEqual(result["candidate"]["correct"], 0)

    def test_calibration_gain_with_accuracy_loss_rejected(self):
        rows = [{"id": "x", "gold": "a", "labels": ["a", "b"], "baseline": {"correct": True, "probabilities": {"a": .51, "b": .49}}, "candidate": {"correct": False, "probabilities": {"a": .9, "b": .1}}}]
        self.assertFalse(paired_diagnostics(rows)["development_gate_passed"])

    def test_public_proxy_and_queue_receipt_never_pass_sota(self):
        for x in ({"Capability": 100, "rank": 1, "scope": "public_development"}, {"ok": True, "reference": "7FEA2738", "queuePosition": 1}):
            self.assertFalse(official_sota_gate(x))

    def test_sota_gate_requires_sealed_source_eligibility(self):
        x = {"publisher_primary_source_measured": True, "independently_verified_receipt": True, "exact_candidate_identity_matches": True, "current_score_version_matches": True, "eligible_under_official_caps": True, "rank": 1, "scope": "publisher_full_sealed_evaluation", "total_decisions": 1500, "sealed_decisions": 1200, "primary_source_url": "https://benchmarkheaven.com/jev-models", "source_receipt_sha256": "a" * 64, "Capability": 86, "cost_usd_per_1000": .05, "adjusted_p50_s": 1}
        self.assertTrue(official_sota_gate(x))
        for field, value in [("sealed_decisions", 0), ("scope", "synthetic"), ("cost_usd_per_1000", .1), ("adjusted_p50_s", 2), ("exact_candidate_identity_matches", False), ("rank", 2), ("rank", True), ("Capability", 101), ("source_receipt_sha256", "z" * 64)]:
            y = copy.deepcopy(x); y[field] = value
            self.assertFalse(official_sota_gate(y))


if __name__ == "__main__":
    unittest.main()
