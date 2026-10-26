"""Private-provider publication refusal; synthetic Docker observations only."""
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_provider_adapter as adapter
import test_schema150_provider_adapter as fixtures


class PrivateProviderPortTests(unittest.TestCase):
    def component(self, **kwargs):
        return fixtures.ConcreteAdapterTests.component(self, **kwargs)

    def test_exposed_image_ports_without_publication_are_permitted(self):
        row = {'Config': {'ExposedPorts': {'9999/tcp': {}}},
               'HostConfig': {'PublishAllPorts': False, 'PortBindings': None},
               'NetworkSettings': {'Ports': {'9999/tcp': None}}}
        adapter.Schema150ProviderAdapter._private_ports(row)
        row['HostConfig']['PortBindings'] = {}
        row['NetworkSettings']['Ports'] = {}
        adapter.Schema150ProviderAdapter._private_ports(row)

    def test_automatic_explicit_and_effective_publication_refuse(self):
        base = {'HostConfig': {'PortBindings': {}, 'PublishAllPorts': False},
                'NetworkSettings': {'Ports': {'9999/tcp': None}}}
        mutations = [({'PublishAllPorts': True}, {}),
                     ({'PortBindings': {'9999/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '59999'}]}}, {}),
                     ({}, {'9999/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '59999'}]}),
                     ({}, {'9999/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '59999'}]}),
                     ({}, {'9999/tcp': [{'HostIp': '::', 'HostPort': '59999'}]})]
        for host, effective in mutations:
            observed = copy.deepcopy(base)
            observed['HostConfig'].update(host)
            observed['NetworkSettings']['Ports'].update(effective)
            with self.subTest(host=host, effective=effective), self.assertRaisesRegex(RuntimeError, 'private_port_exposed'):
                adapter.Schema150ProviderAdapter._private_ports(observed)

    def test_automatic_publication_refuses_before_starting_that_provider(self):
        actor, scope, preimage, _ = self.component(stage='fenced')
        actor.require_authority = Mock()
        actor._roles = Mock(return_value={'fixture': 'original'})
        actor._expected_roles = Mock(return_value={'fixture': 'original'})
        auth = next(row for row in actor._rows.return_value if row['Name'] == '/supabase-auth')
        auth['HostConfig'].update(PublishAllPorts=True, PortBindings={})
        auth['Config']['ExposedPorts'] = {'9999/tcp': {}}
        with self.assertRaisesRegex(RuntimeError, 'private_port_exposed'):
            actor.resume_providers_private(scope, preimage)
        actor.runtime.command.assert_not_called()

    def test_private_attestation_detects_effective_ports_even_when_spec_is_unchanged(self):
        actor, _, _, _ = self.component(stage='private')
        auth = next(row for row in actor._rows.return_value if row['Name'] == '/supabase-auth')
        # NetworkSettings is ephemeral and deliberately outside measured_spec.
        auth['NetworkSettings']['Ports'] = {'9999/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '59999'}]}
        for phase in ('private', 'private-boundary'):
            with self.subTest(phase=phase), self.assertRaisesRegex(RuntimeError, 'private_port_exposed'):
                actor._attest(phase)
        actor.runtime.command.assert_not_called()

    def test_lost_resume_ack_cannot_reconcile_with_public_provider_ports(self):
        actor, scope, preimage, journal = self.component(stage='fenced')
        journal.append('effect_intent', {'step': 'restore_roles_private'})
        journal.append('effect_complete', {'step': 'restore_roles_private'})
        journal.append('effect_intent', {'step': 'resume_providers_private'})
        actor._rows.return_value = fixtures.phase_rows(actor.inventory, actor._rows.return_value, 'private')
        auth = next(row for row in actor._rows.return_value if row['Name'] == '/supabase-auth')
        auth['NetworkSettings']['Ports'] = {'9999/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '59999'}]}
        with self.assertRaisesRegex(RuntimeError, 'private_port_exposed'):
            actor.verify_effect('resume_providers_private', scope, preimage)
        actor.runtime.command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
