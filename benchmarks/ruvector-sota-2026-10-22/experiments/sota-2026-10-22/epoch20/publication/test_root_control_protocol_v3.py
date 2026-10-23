"""Generic new protocol binding/closure faults; no real study rendering."""
import json
import unittest
import test_root_builders_v2 as prior

CONTROL = prior.module('build_controls_v3.py')
prior.CONTROL = CONTROL


class ActiveProtocolBinding(prior.GenericControlClosure):
    def setUp(self):
        super().setUp()
        self.active_protocol = self.p + 'audit/epoch20/protocol_pooler_v1.json'
        prior.put(self.project / self.active_protocol, {'generic': 'NEW_ACTIVE_PROTOCOL'})
        spec_path = self.project / (self.p + 'epoch20/PLAN_SPEC.json')
        spec = json.loads(spec_path.read_bytes())
        spec['references'] = {'audit_protocol': self.active_protocol}
        prior.put(spec_path, spec)

    def test_source_control_binds_exact_new_protocol_instead_of_preserved_old_file(self):
        args = self.args('dynamic-protocol')
        self.render(args)
        cont = json.loads((args.out / 'CONTINUATION.json').read_bytes())
        self.assertEqual(cont['epoch20_frozen_study']['audit_protocol'],
                         CONTROL.ref(self.project, self.active_protocol))
        self.assertNotEqual(cont['epoch20_frozen_study']['audit_protocol']['path'],
                            self.p + 'audit/epoch20/protocol.json')

    def test_missing_or_symlink_active_protocol_refused(self):
        active = self.project / self.active_protocol
        active.unlink()
        with self.assertRaises((AssertionError, FileNotFoundError)):
            self.render(self.args('missing-active'))
        active.symlink_to(self.project / (self.p + 'audit/epoch20/protocol.json'))
        with self.assertRaises(AssertionError):
            self.render(self.args('symlink-active'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
