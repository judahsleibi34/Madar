"""Native nft grammar/observation in a NEW network namespace, never host rules.

Opt in only through unshare --net; no production interfaces, Docker or mounts.
Not a KVM execution, receiver or protected-operation acceptance substitute.
"""
import json
import os
from pathlib import Path
import subprocess
import unittest
from deployment.lib import isolated_release_environment as env


@unittest.skipUnless(os.getenv('MADAR_NATIVE_ISOLATED_FIREWALL')=='1','Requires root in a new disposable network namespace')
class NativeIsolatedFirewallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.geteuid()!=0 or os.readlink('/proc/self/ns/net')==os.readlink('/proc/1/ns/net')
                or subprocess.check_output(['/usr/sbin/ip','-json','link','show']).decode().count('"ifname"')!=1):
            raise RuntimeError('fresh_disposable_network_namespace_required')
        subprocess.run(['/usr/sbin/ip','link','add','control0','type','dummy'],check=True)
        subprocess.run(['/usr/sbin/ip','addr','add','10.0.2.15/24','dev','control0'],check=True)
        subprocess.run(['/usr/sbin/ip','link','set','control0','up'],check=True)
        subprocess.run(['/usr/sbin/ip','route','add','default','via','10.0.2.2','dev','control0'],check=True)

    def tearDown(self):
        subprocess.run(['/usr/sbin/nft','delete','table','inet',env.TABLE],check=True)

    def install(self,execution):
        commands=[{'add':{'table':{'family':'inet','name':env.TABLE}}}]
        for name,rules in env.required_rules('control0',execution=execution).items():
            commands.append({'add':{'chain':{'family':'inet','table':env.TABLE,'name':name,
                'type':'filter','hook':name,'prio':200,'policy':'accept'}}})
            for expr in rules:
                commands.append({'add':{'rule':{'family':'inet','table':env.TABLE,'chain':name,'expr':expr}}})
        result=subprocess.run(['/usr/sbin/nft','--json','--file','-'],input=json.dumps({'nftables':commands}).encode(),capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode()[:1000])

    def test_native_preparation_firewall_is_observed_but_cannot_authorize_execution(self):
        self.install(False)
        self.assertEqual(env.observe_effect_fence(),'control0')
        with self.assertRaisesRegex(RuntimeError,'effect_fencing_invalid'):env.observe_effect_fence(execution=True)

    def test_native_execution_firewall_binds_ssh_reply_only_and_blocks_all_initiated_egress(self):
        self.install(True)
        self.assertEqual(env.observe_effect_fence(execution=True),'control0')
        with self.assertRaisesRegex(RuntimeError,'unreviewed_firewall_rule'):env.observe_effect_fence()
        # Even a single additional permissive rule is rejected by the observer.
        subprocess.run(['/usr/sbin/nft','add','rule','inet',env.TABLE,'output','accept'],check=True)
        with self.assertRaisesRegex(RuntimeError,'effect_fencing_invalid'):env.observe_effect_fence(execution=True)


if __name__=='__main__':unittest.main()
