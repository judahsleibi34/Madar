import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_release_bootstrap import release_cli


class SupabaseClientNetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        overlay = self.root/'web/precutover/docker-compose.supabase-client.yml'
        overlay.parent.mkdir(parents=True)
        overlay.write_text('services: {}\n')
        compatibility = release_cli.Compatibility(114,116,116,'forward-compatible',114,114)
        self.ops = release_cli.DockerGitOperations(self.root,self.root,self.root/'unused.env',compatibility)
        self.ops.release_root=self.root

    def tearDown(self):
        self.temp.cleanup()

    def test_option_absent_keeps_existing_topology(self):
        with patch.dict(os.environ,{'MADAR_SUPABASE_CLIENT_NETWORK':''}), patch.object(self.ops,'run') as run:
            self.assertEqual(self.ops._supabase_client_files(),[])
            self.ops._validate_supabase_client_network()
            run.assert_not_called()

    def test_requires_exact_url_and_internal_bridge(self):
        with patch.dict(os.environ,{'MADAR_SUPABASE_CLIENT_NETWORK':'madar-supabase-client','SUPABASE_URL':'http://madar-supabase:8000'}):
            for data in ([{'Internal':False,'Driver':'bridge'}],[{'Internal':True,'Driver':'host'}],[],{}):
                with patch.object(self.ops,'run',return_value=json.dumps(data)):
                    with self.assertRaises(RuntimeError):self.ops._validate_supabase_client_network()
            with patch.object(self.ops,'run',return_value=json.dumps([{'Internal':True,'Driver':'bridge'}])):
                self.ops._validate_supabase_client_network()
            with patch.dict(os.environ,{'SUPABASE_URL':'https://hosted.example'}):
                with self.assertRaises(RuntimeError):self.ops._validate_supabase_client_network()

    def test_unknown_network_and_missing_overlay_fail_closed(self):
        with patch.dict(os.environ,{'MADAR_SUPABASE_CLIENT_NETWORK':'other'}):
            with self.assertRaises(RuntimeError):self.ops._supabase_client_files()
        with patch.dict(os.environ,{'MADAR_SUPABASE_CLIENT_NETWORK':'madar-supabase-client'}):
            (self.root/'web/precutover/docker-compose.supabase-client.yml').unlink()
            with self.assertRaises(RuntimeError):self.ops._supabase_client_files()
