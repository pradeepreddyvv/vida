import unittest
from unittest.mock import patch
import test_sync_and_approvals  # establishes test environment and import path
from shared.ai import chat_turn


class ChatHistoryTests(unittest.TestCase):
    def messages(self, history):
        with patch('shared.ai.converse', return_value='ok') as call:
            chat_turn('system', 'current request', history)
            return call.call_args.args[1]

    def test_truncated_history_starts_with_user(self):
        result = self.messages([
            {'role':'assistant','content':'orphaned answer'},
            {'role':'assistant','content':'orphaned receipt'},
            {'role':'user','content':'earlier request'},
            {'role':'assistant','content':'earlier answer'},
        ])
        self.assertEqual([m['role'] for m in result], ['user','assistant','user'])
        self.assertEqual(result[0]['content'][0]['text'], 'earlier request')

    def test_assistant_only_history_still_sends_current_request(self):
        result = self.messages([{'role':'assistant','content':'old receipt'}])
        self.assertEqual(result, [{'role':'user','content':[{'text':'current request'}]}])

    def test_receipts_and_failed_retries_keep_text_with_alternating_roles(self):
        result = self.messages([
            {'role':'user','content':'first request'},
            {'role':'assistant','content':'proposal'},
            {'role':'assistant','content':'completed receipt'},
            {'role':'user','content':'failed request'},
        ])
        self.assertEqual([m['role'] for m in result], ['user','assistant','user'])
        self.assertIn('completed receipt', result[1]['content'][0]['text'])
        self.assertEqual(result[-1]['content'][0]['text'], 'failed request\n\ncurrent request')

    def test_invalid_or_empty_history_is_ignored(self):
        result = self.messages([{'role':'system','content':'untrusted'}, {'role':'user','content':''}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['content'][0]['text'], 'current request')
