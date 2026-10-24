import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('azure_release', Path(__file__).parents[1] / 'release.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
IMAGE = 'registry.azurecr.io/app@sha256:' + 'a' * 64
OLD = 'registry.azurecr.io/app@sha256:' + 'b' * 64


def resource(name, *, job=None):
    config = {'activeRevisionsMode': 'Single'}
    container = {'name': name, 'image': OLD}
    if job:
        config = {'triggerType': job, 'provisioningState': 'Succeeded',
                  ('manualTriggerConfig' if job == 'Manual' else 'scheduleTriggerConfig'):
                  {'parallelism': 1, 'replicaCompletionCount': 1}}
        container['command'] = (['alembic', 'upgrade', 'head'] if job == 'Manual'
                                else ['python', '-m', 'app.dispatch_outbox'])
    elif name == 'api':
        config['ingress'] = {'external': True, 'fqdn': 'app.example.com',
                             'traffic': [{'revisionName': 'api--old', 'weight': 100}]}
    return {'name': name, 'properties': {'configuration': config, 'provisioningState': 'Succeeded',
            'latestReadyRevisionName': name + '--old', 'template': {'containers': [container],
            'scale': {'minReplicas': 1}}}}


class FakeRelease(module.Release):
    def __init__(self):
        super().__init__('sub', 'group', 'api', 'worker', 'migrate', 'schedule', IMAGE, 'r-test')
        self.resources = {'api': resource('api'), 'worker': resource('worker'),
                          'migrate': resource('migrate', job='Manual'),
                          'schedule': resource('schedule', job='Schedule')}
        self.events = []
        self.failure = None
        self.executions = []
        self.attempts = 2
        self.poll_seconds = 0

    def show(self, name, job=False):
        return copy.deepcopy(self.resources[name])

    def az(self, *args):
        self.events.append(('az', args))
        if args[:4] == ('containerapp', 'job', 'execution', 'list'):
            return self.executions
        return {}

    def run_job(self, name, container):
        self.events.append(('job', name))
        if self.failure == name:
            raise module.ReleaseError('job failed')

    def update_app(self, name, container, image, suffix):
        self.events.append(('app', name, image))
        if self.failure == name and image == IMAGE:
            raise module.ReleaseError('revision failed')
        return {'fqdn': 'candidate.example.com'}

    def update_scheduler(self, container, image):
        self.events.append(('scheduler', image))

    def smoke(self, host):
        self.events.append(('smoke', host))
        if self.failure == host:
            raise module.ReleaseError('smoke failed')

    def traffic(self, revision):
        self.events.append(('traffic', revision))
        if self.failure == 'rollback' and revision == 'api--old' and self.events.count(('traffic', revision)) > 1:
            raise module.ReleaseError('traffic restoration failed')
        if self.failure == 'rollback' and revision == 'api--r-test':
            raise module.ReleaseError('promotion failed')


class ReleaseTests(unittest.TestCase):
    def test_success_promotes_only_after_migration_candidate_worker_and_outbox(self):
        release = FakeRelease()
        release.run()
        events = release.events
        positions = [events.index(event) for event in [
            ('job', 'migrate'), ('smoke', 'candidate.example.com'),
            ('app', 'worker', IMAGE), ('job', 'schedule'), ('traffic', 'api--r-test'),
            ('smoke', 'app.example.com')]]
        self.assertEqual(positions, sorted(positions))

    def test_custom_domain_is_checked_after_promotion_before_retiring_old_revision(self):
        release = FakeRelease()
        release.resources['api']['properties']['template']['containers'][0]['env'] = [
            {'name': 'PUBLIC_WEB_URL', 'value': 'https://fitness.example.com'}]
        release.run()
        events = release.events
        self.assertLess(events.index(('traffic', 'api--r-test')),
                        events.index(('smoke', 'fitness.example.com')))
        self.assertLess(events.index(('smoke', 'fitness.example.com')),
                        next(i for i, e in enumerate(events) if e[0] == 'az'
                             and e[1][:3] == ('containerapp', 'revision', 'deactivate')))

    def test_custom_domain_failure_restores_previous_release(self):
        release = FakeRelease()
        release.resources['api']['properties']['template']['containers'][0]['env'] = [
            {'name': 'PUBLIC_WEB_URL', 'value': 'https://fitness.example.com'}]
        release.failure = 'fitness.example.com'
        with self.assertRaises(module.ReleaseError):
            release.run()
        self.assertEqual([e for e in release.events if e[0] == 'traffic'][-1], ('traffic', 'api--old'))
        self.assertIn(('app', 'worker', OLD), release.events)
        self.assertIn(('scheduler', OLD), release.events)
        self.assertFalse(any(e[0] == 'az' and e[1][-1] == 'api--old' for e in release.events))

    def test_invalid_public_origin_fails_before_any_mutation(self):
        for url in ('http://fitness.example.com', 'https://user:pass@fitness.example.com',
                    'https://fitness.example.com/path', 'https://fitness.example.com?key=hidden'):
            with self.subTest(url=url):
                release = FakeRelease()
                release.resources['api']['properties']['template']['containers'][0]['env'] = [
                    {'name': 'PUBLIC_WEB_URL', 'value': url}]
                with self.assertRaisesRegex(module.ReleaseError, 'PUBLIC_WEB_URL'):
                    release.run()
                self.assertEqual(release.events, [])

    def test_migration_failure_never_changes_app_or_traffic(self):
        release = FakeRelease()
        release.failure = 'migrate'
        with self.assertRaises(module.ReleaseError):
            release.run()
        self.assertFalse(any(event[0] in {'traffic', 'app', 'scheduler'} for event in release.events))

    def test_active_migration_blocks_a_second_execution(self):
        release = FakeRelease()
        release.executions = [{'properties': {'status': 'Running'}}]
        with self.assertRaisesRegex(module.ReleaseError, 'already active'):
            release.run()
        self.assertFalse(any(event[0] == 'job' for event in release.events))

    def test_wrong_job_command_fails_before_mutation(self):
        release = FakeRelease()
        release.resources['migrate']['properties']['template']['containers'][0]['command'] = ['true']
        with self.assertRaisesRegex(module.ReleaseError, 'Job command'):
            release.run()
        self.assertEqual(release.events, [])

    def test_candidate_failure_leaves_old_traffic_and_worker(self):
        release = FakeRelease()
        release.failure = 'candidate.example.com'
        with self.assertRaises(module.ReleaseError):
            release.run()
        self.assertNotIn(('traffic', 'api--r-test'), release.events)
        self.assertNotIn(('app', 'worker', IMAGE), release.events)
        self.assertEqual([e for e in release.events if e[0] == 'traffic'][-1], ('traffic', 'api--old'))

    def test_outbox_failure_restores_background_images(self):
        release = FakeRelease()
        release.failure = 'schedule'
        with self.assertRaises(module.ReleaseError):
            release.run()
        self.assertIn(('app', 'worker', OLD), release.events)
        self.assertIn(('scheduler', OLD), release.events)
        self.assertNotIn(('traffic', 'api--r-test'), release.events)

    def test_failed_traffic_restore_does_not_deactivate_candidate(self):
        release = FakeRelease()
        release.failure = 'rollback'
        with self.assertRaises(module.ReleaseError):
            release.run()
        self.assertFalse(any(e[0] == 'az' and e[1][:3] == ('containerapp', 'revision', 'deactivate')
                             for e in release.events))

    def test_tag_only_image_is_rejected(self):
        with self.assertRaises(module.ReleaseError):
            module.Release('s', 'g', 'a', 'w', 'm', 'j', 'repo:latest', 'r-test')

    def test_job_polls_exact_execution_and_stops_it_on_failure(self):
        release = FakeRelease()
        replies = [ {'name': 'migration-123'},
                    {'name': 'migration-123', 'properties': {'status': 'Running'}},
                    {'name': 'migration-123', 'properties': {'status': 'Failed'}}, {} ]
        with patch.object(release, 'az', side_effect=replies) as az, self.assertRaises(module.ReleaseError):
            module.Release.run_job(release, 'migrate', 'migrate')
        for call in az.call_args_list[1:]:
            self.assertIn('migration-123', call.args)
        self.assertEqual(az.call_args_list[-1].args[:3], ('containerapp', 'job', 'stop'))

    def test_wrong_execution_cannot_report_success(self):
        release = FakeRelease()
        replies = [{'name': 'migration-123'}, {'name': 'other', 'properties': {'status': 'Succeeded'}}, {}]
        with patch.object(release, 'az', side_effect=replies), self.assertRaisesRegex(module.ReleaseError, 'different job'):
            module.Release.run_job(release, 'migrate', 'migrate')


if __name__ == '__main__':
    unittest.main()
