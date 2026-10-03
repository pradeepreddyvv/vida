import unittest
from unittest.mock import patch
import test_sync_and_approvals as core
from shared import db
from shared.job_progress import tracking, stage, public_job
from shared.planning_lock import agent_lock

class ProgressTests(unittest.TestCase):
    setUp=core.CoreTests.setUp
    tearDown=core.CoreTests.tearDown

    def test_stage_is_saved_only_for_current_job(self):
        db.put_item({'PK':'USER#a','SK':'JOB#one','status':'processing'})
        with tracking('a','one'):
            stage('Separating your request into actions')
        stage('Must not leak into previous job')
        self.assertEqual(db.get_item('USER#a','JOB#one')['stage'],'Separating your request into actions')

    def test_expired_worker_reports_interruption_not_endless_processing(self):
        with patch('shared.job_progress.time.time',return_value=200):
            job=public_job({'SK':'JOB#one','status':'processing','deadline':100})
            self.assertEqual(job['status'],'failed')
            self.assertIn('Check saved proposals',job['error'])
            self.assertEqual(public_job({'SK':'JOB#one','status':'completed','deadline':100})['status'],'completed')

    def test_lock_lease_tracks_runtime_and_still_excludes_concurrent_workers(self):
        with patch('shared.planning_lock.time.time',return_value=100):
            with agent_lock('a',lease_seconds=100):
                self.assertEqual(db.get_item('USER#a','AGENT_LOCK')['expires'],200)
                with self.assertRaises(ValueError):
                    with agent_lock('a',lease_seconds=100): pass
            self.assertIsNone(db.get_item('USER#a','AGENT_LOCK'))
