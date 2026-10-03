import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
import test_sync_and_approvals as core
from api.routes import integrations

class OAuthRedirectTests(unittest.TestCase):
    setUp=core.CoreTests.setUp
    tearDown=core.CoreTests.tearDown

    def test_google_override_is_stable_across_hosts_and_does_not_change_notion(self):
        uri='https://api.example.com/prod/api/auth/google/callback'
        with patch.dict(os.environ,{'CALLBACK_BASE_URL':'https://web.example.com','GOOGLE_REDIRECT_URI':uri,'GOOGLE_CLIENT_ID':'test-client'}), patch('shared.oauth_config.load_credentials'):
            start=integrations.start_google_auth({},'a')
            params=parse_qs(urlparse(json.loads(start['body'])['url']).query)
            self.assertEqual(params['redirect_uri'],[uri])
            integrations._configure_callback({'requestContext':{'domainName':'another.execute-api.amazonaws.com','stage':'prod'}})
            self.assertEqual(integrations.GOOGLE_REDIRECT_URI,uri)
            self.assertEqual(integrations.NOTION_REDIRECT_URI,'https://web.example.com/api/auth/notion/callback')

    def test_invalid_google_override_is_rejected(self):
        for uri in ['http://example.com/api/auth/google/callback','https://example.com/api/auth/google/callback?x=1','https://example.com/api/auth/google/callback#fragment']:
            with patch.dict(os.environ,{'GOOGLE_REDIRECT_URI':uri}), patch('shared.oauth_config.load_credentials'), self.assertRaises(ValueError):
                integrations._configure_callback({})
