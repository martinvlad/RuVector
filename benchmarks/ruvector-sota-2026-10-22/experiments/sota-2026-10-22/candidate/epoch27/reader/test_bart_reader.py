"""Synthetic stdlib checks only; never acquire assets or initialize an ML runtime."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load_source(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = load_source("e27_synthetic_reader", "bart_reader.py")
acquisition = load_source("e27_synthetic_acquisition", "acquire_bart_assets.py")


class ReaderNumerics(unittest.TestCase):
    def test_native_permutation_keeps_neutral_mass(self):
        probabilities = reader.canonical_probabilities([math.log(2), math.log(3), math.log(5)])
        for actual, expected in zip(probabilities, [0.5, 0.2, 0.3]):
            self.assertAlmostEqual(actual, expected, places=15)
        self.assertAlmostEqual(sum(probabilities), 1.0, places=15)

    def test_stable_extremes_and_shift_invariance(self):
        self.assertEqual(reader.canonical_probabilities([-1000, 0, 1000]), [1.0, 0.0, 0.0])
        expected = reader.canonical_probabilities([2.0, 4.0, 1.0])
        shifted = reader.canonical_probabilities([1002.0, 1004.0, 1001.0])
        self.assertEqual(expected, shifted)

    def test_nonfinite_and_wrong_arity_rejected(self):
        for logits in ([0, 1], [0, 1, 2, 3], [0, math.nan, 1], [0, math.inf, 1], [-math.inf, 0, 1]):
            with self.subTest(logits=logits), self.assertRaises(ValueError):
                reader.canonical_probabilities(logits)

    def test_native_tie_order_and_binary_half_tie(self):
        self.assertEqual(reader.decisions([0, 0, 0])["typed_prediction"], "Contradiction")
        row = reader.decisions([0, 0, math.log(2)])
        self.assertEqual(row["binary_yes_probability"], 0.5)
        self.assertEqual(row["binary_no_probability"], 0.5)
        self.assertEqual(row["binary_prediction"], "No")
        self.assertEqual(row["typed_prediction"], "Entailment")

    def test_import_is_lazy(self):
        self.assertFalse(set(sys.modules) & {"torch", "transformers", "tokenizers", "safetensors", "numpy"})


class PreparationGuards(unittest.TestCase):
    def setUp(self):
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden in synthetic tests"))
        self.network_mock = self.network.start()
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-only-", dir=HERE)
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.network_mock.assert_not_called()
        self.temp.cleanup()
        self.network.stop()

    def test_replay_receipt_persists_and_blocks_reentry(self):
        destination = self.directory / "never-downloaded-model"
        receipt = acquisition.reserve_attempt(destination, {"synthetic_test_only": True})
        acquisition.update_receipt(receipt, {"status": "FAILED_NO_RETRY", "synthetic_test_only": True})
        self.assertFalse(destination.exists())
        with self.assertRaisesRegex(ValueError, "retry/resume"):
            acquisition.reserve_attempt(destination, {"synthetic_test_only": True})

    def test_existing_destination_and_symlinks_rejected(self):
        destination = self.directory / "existing"
        destination.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            acquisition.reserve_attempt(destination, {})
        link = self.directory / "linked"
        link.symlink_to(destination, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            acquisition.checked_absolute_path(link / "unused")

    def test_duplicate_plan_and_changed_weight_pin_rejected(self):
        plan = acquisition.read_object(HERE / "asset-acquisition-plan.json")
        acquisition.verify_plan(plan)
        duplicate = copy.deepcopy(plan)
        duplicate["files"].append(copy.deepcopy(duplicate["files"][0]))
        with self.assertRaisesRegex(ValueError, "closure"):
            acquisition.verify_plan(duplicate)
        changed = copy.deepcopy(plan)
        next(row for row in changed["files"] if row["path"] == "pytorch_model.bin")["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pin changed"):
            acquisition.verify_plan(changed)

    def test_permit_false_and_stale_physical_lease_rejected(self):
        manifest_path = self.directory / "synthetic-manifest.json"
        manifest = {"source_git_commit": "1" * 40}
        manifest_path.write_text(json.dumps(manifest))
        plan_path = HERE / "asset-acquisition-plan.json"
        destination = self.directory / "synthetic-destination"
        permit = json.loads((HERE / "prepare-permit.example.json").read_text())
        permit.update({
            "preparation_go": True, "source_git_commit": manifest["source_git_commit"],
            "source_manifest_sha256": acquisition.sha256_file(manifest_path),
            "acquisition_plan_sha256": acquisition.sha256_file(plan_path),
            "destination": str(destination),
            "lease": {"pid": acquisition.LEASE_PID, "start_ticks": acquisition.LEASE_START_TICKS,
                      "checkpoint": manifest["source_git_commit"]},
        })
        permit_path = self.directory / "SYNTHETIC_TEST_NOT_A_ROOT_PERMIT.json"
        permit_path.write_text(json.dumps(permit))
        with patch.object(acquisition, "process_start_ticks", return_value=acquisition.LEASE_START_TICKS):
            acquisition.verify_permit(permit_path, manifest_path, manifest, plan_path, destination)
        with patch.object(acquisition, "process_start_ticks", return_value=acquisition.LEASE_START_TICKS + 1):
            with self.assertRaisesRegex(ValueError, "reused"):
                acquisition.verify_permit(permit_path, manifest_path, manifest, plan_path, destination)
        permit["preparation_go"] = False
        permit_path.write_text(json.dumps(permit))
        with self.assertRaisesRegex(ValueError, "preparation_go"):
            acquisition.verify_permit(permit_path, manifest_path, manifest, plan_path, destination)

    def metadata_lock_fixture(self):
        model_directory = self.directory / "synthetic-model-metadata-only"
        model_directory.mkdir()
        for name in reader.REQUIRED_ASSETS:
            (model_directory / name).write_text("Synthetic fixture; no actual model bytes.\n")
        raw_lock = b'{"synthetic_metadata_only": true}\n'
        actual_lock = model_directory / "asset-lock.json"
        actual_lock.write_bytes(raw_lock)
        public_directory = self.directory / "public-metadata-copy"
        public_directory.mkdir()
        public_copy = public_directory / "MODEL_ASSETS.json"
        public_copy.write_bytes(raw_lock)
        return model_directory, actual_lock, public_copy

    def test_public_lock_copy_equals_direct_lock_and_tamper_fails(self):
        model_directory, actual_lock, public_copy = self.metadata_lock_fixture()
        direct = reader.read_canonical_asset_lock(model_directory, actual_lock)
        public = reader.read_canonical_asset_lock(model_directory, public_copy)
        self.assertEqual(direct, public)
        self.assertEqual(public[1], {"synthetic_metadata_only": True})
        # Same byte count, different content: neither size alone nor JSON shape suffices.
        public_copy.write_bytes(public_copy.read_bytes().replace(b"true", b"null"))
        with self.assertRaisesRegex(ValueError, "bytes/SHA256"):
            reader.read_canonical_asset_lock(model_directory, public_copy)

    def test_public_lock_copy_rejects_extras_and_symlink_components(self):
        model_directory, actual_lock, public_copy = self.metadata_lock_fixture()
        extra = model_directory / "MODEL_ASSETS.json"
        extra.write_bytes(actual_lock.read_bytes())
        with self.assertRaisesRegex(ValueError, "additional files"):
            reader.read_canonical_asset_lock(model_directory, public_copy)
        extra.unlink()
        linked_directory = self.directory / "linked-public-directory"
        linked_directory.symlink_to(public_copy.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            reader.read_canonical_asset_lock(model_directory, linked_directory / public_copy.name)
        linked_lock = self.directory / "linked-public-lock.json"
        linked_lock.symlink_to(public_copy)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            reader.read_canonical_asset_lock(model_directory, linked_lock)
        linked_model = self.directory / "linked-model-directory"
        linked_model.symlink_to(model_directory, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            reader.read_canonical_asset_lock(linked_model, actual_lock)


if __name__ == "__main__":
    unittest.main()
