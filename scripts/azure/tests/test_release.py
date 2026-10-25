import copy
import importlib.util
import json
import stat
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
                  'manualTriggerConfig': None, 'scheduleTriggerConfig': None,
                  ('manualTriggerConfig' if job == 'Manual' else 'scheduleTriggerConfig'):
                  {'parallelism': 1, 'replicaCompletionCount': 1}}
        container['command'] = (['alembic', 'upgrade', 'head'] if job == 'Manual'
                                else ['python', '-m', 'app.dispatch_outbox'])
    elif name == 'api':
        config['ingress'] = {'external': True, 'fqdn': 'app.example.com',
                             'traffic': [{'revisionName': 'api--old', 'weight': 100}]}
    return {'name': name, 'location': 'southafricanorth', 'properties': {'configuration': config, 'provisioningState': 'Succeeded',
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

    def prepare_api(self, old_revision, location):
        self.events.append(('prepare', old_revision))
        self.traffic(old_revision)

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

    def test_worker_ingress_is_rejected_before_migration_or_mutation(self):
        for external in (True, False):
            with self.subTest(external=external):
                release = FakeRelease()
                release.resources['worker']['properties']['configuration']['ingress'] = {
                    'external': external, 'targetPort': 10000}
                with self.assertRaisesRegex(module.ReleaseError, 'Worker must have ingress disabled'):
                    release.run()
                self.assertEqual(release.events, [])

    def test_missing_active_trigger_cannot_fall_back_to_inactive_trigger(self):
        for name, active, inactive in (
            ('migrate', 'manualTriggerConfig', 'scheduleTriggerConfig'),
            ('schedule', 'scheduleTriggerConfig', 'manualTriggerConfig'),
        ):
            with self.subTest(job=name):
                release = FakeRelease()
                config = release.resources[name]['properties']['configuration']
                config[inactive] = config[active]
                config[active] = None
                with self.assertRaisesRegex(module.ReleaseError, 'Jobs must run one replica'):
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

    def test_mode_and_traffic_patch_does_not_read_or_replace_secrets(self):
        release = FakeRelease()
        ready = copy.deepcopy(release.resources['api'])
        ready['properties']['configuration']['activeRevisionsMode'] = 'Multiple'
        with patch.object(release, 'show', side_effect=[release.resources['api'], ready]), patch.object(release, 'az') as azure:
            module.Release.prepare_api(release, 'api--old', 'southafricanorth')
        args = azure.call_args.args
        self.assertEqual(args[:3], ('rest', '--method', 'patch'))
        self.assertIn('/resourceGroups/group/providers/Microsoft.App/containerApps/api?', args[args.index('--url') + 1])
        self.assertEqual(json.loads(args[args.index('--body') + 1]), {
            'location': 'southafricanorth', 'properties': {'configuration': {
                'activeRevisionsMode': 'Multiple',
                'ingress': {'traffic': [{'revisionName': 'api--old', 'weight': 100}]}}}})
        self.assertEqual(azure.call_count, 1)

    def test_prepare_waits_for_completion_even_when_new_configuration_is_visible(self):
        release = FakeRelease()
        pending = copy.deepcopy(release.resources['api'])
        pending['properties']['configuration']['activeRevisionsMode'] = 'Multiple'
        pending['properties']['provisioningState'] = 'InProgress'
        done = copy.deepcopy(pending)
        done['properties']['provisioningState'] = 'Succeeded'
        with patch.object(release, 'show', side_effect=[release.resources['api'], pending, done]) as show, patch.object(release, 'az') as azure:
            module.Release.prepare_api(release, 'api--old', 'southafricanorth')
        self.assertEqual(show.call_count, 3)
        self.assertEqual(azure.call_count, 1)

    def test_prepare_reuses_completed_pinned_configuration_without_another_write(self):
        release = FakeRelease()
        release.resources['api']['properties']['configuration']['activeRevisionsMode'] = 'Multiple'
        with patch.object(release, 'az') as azure:
            module.Release.prepare_api(release, 'api--old', 'southafricanorth')
        azure.assert_not_called()

    def test_prepare_does_not_accept_pending_or_failed_configuration(self):
        for status in ('InProgress', 'Failed', 'Canceled', None):
            with self.subTest(status=status):
                release = FakeRelease()
                state = copy.deepcopy(release.resources['api'])
                state['properties']['configuration']['activeRevisionsMode'] = 'Multiple'
                state['properties']['provisioningState'] = status
                with patch.object(release, 'show', return_value=state), patch.object(release, 'az') as azure, self.assertRaises(module.ReleaseError):
                    module.Release.prepare_api(release, 'api--old', 'southafricanorth')
                azure.assert_not_called()

    def test_traffic_rollback_waits_for_pending_write_and_verifies_repair(self):
        release = FakeRelease()
        pending = copy.deepcopy(release.resources['api'])
        pending['properties']['provisioningState'] = 'InProgress'
        pending['properties']['configuration']['activeRevisionsMode'] = 'Multiple'
        pending['properties']['configuration']['ingress']['traffic'] = [
            {'revisionName': 'api--r-test', 'weight': 100}]
        failed = copy.deepcopy(pending)
        failed['properties']['provisioningState'] = 'Failed'
        restored = copy.deepcopy(pending)
        restored['properties']['provisioningState'] = 'Succeeded'
        restored['properties']['configuration']['ingress']['traffic'] = [
            {'revisionName': 'api--old', 'weight': 100}]
        with patch.object(release, 'show', side_effect=[pending, failed, pending, restored]) as show, patch.object(release, 'az') as azure:
            module.Release.traffic(release, 'api--old')
        self.assertEqual(show.call_count, 4)
        self.assertEqual(azure.call_count, 1)
        self.assertIn('api--old=100', azure.call_args.args)

    def test_traffic_verification_waits_for_stale_state_and_rejects_failed_update(self):
        release = FakeRelease()
        old = copy.deepcopy(release.resources['api'])
        done = copy.deepcopy(old)
        done['properties']['configuration']['activeRevisionsMode'] = 'Multiple'
        with patch.object(release, 'show', side_effect=[old, done]) as show:
            release.wait_for_traffic('api--old')
        self.assertEqual(show.call_count, 2)
        done['properties']['provisioningState'] = 'Failed'
        with patch.object(release, 'show', return_value=done), self.assertRaises(module.ReleaseError):
            release.wait_for_traffic('api--old')

    def test_rest_cli_scope_and_safe_error_diagnostics(self):
        release = FakeRelease()
        success = module.subprocess.CompletedProcess([], 0, '{}', '')
        with patch.object(module.subprocess, 'run', return_value=success) as run:
            module.Release.az(release, 'rest', '--method', 'get', '--url', 'https://management.azure.com/')
            self.assertNotIn('--resource-group', run.call_args.args[0])
            self.assertIn('--subscription', run.call_args.args[0])
            module.Release.az(release, 'containerapp', 'show', '--name', 'api')
            self.assertIn('--resource-group', run.call_args.args[0])
        failure = module.subprocess.CompletedProcess([], 1, '',
            'ERROR: (AuthorizationFailed) private diagnostic token=do-not-display')
        with patch.object(module.subprocess, 'run', return_value=failure), self.assertRaises(module.ReleaseError) as caught:
            module.Release.az(release, 'containerapp', 'show', '--name', 'api')
        self.assertIn('AuthorizationFailed', str(caught.exception))
        self.assertNotIn('do-not-display', str(caught.exception))

    def test_job_image_override_preserves_complete_execution_template(self):
        for name in ('migrate', 'schedule'):
            with self.subTest(job=name):
                release = FakeRelease()
                template = release.resources[name]['properties']['template']
                template['containers'][0].update({
                    'env': [{'name': 'DATABASE_URL', 'secretRef': 'database-url'},
                            {'name': 'ENVIRONMENT', 'value': 'production'}],
                    'resources': {'cpu': 0.5, 'memory': '1Gi'},
                    'volumeMounts': [{'volumeName': 'scratch', 'mountPath': '/scratch'}],
                    'args': None,
                })
                template['volumes'] = [{'name': 'scratch', 'storageType': 'EmptyDir'}]
                template['initContainers'] = None
                original = copy.deepcopy(template)
                submitted = []
                paths = []

                def azure(*args, paths=paths, submitted=submitted):
                    if args[:3] == ('containerapp', 'job', 'start'):
                        self.assertNotIn('--image', args)
                        path = Path(args[args.index('--yaml') + 1])
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                        paths.append(path)
                        submitted.append(json.loads(path.read_text()))
                        return {'name': 'job-123'}
                    return {'name': 'job-123', 'properties': {'status': 'Succeeded'}}

                with patch.object(release, 'az', side_effect=azure):
                    module.Release.run_job(release, name, name)
                expected = copy.deepcopy(original)
                expected['containers'][0]['image'] = IMAGE
                self.assertEqual(submitted, [expected])
                self.assertEqual(template, original)
                self.assertFalse(paths[0].exists())

    def test_changed_job_container_fails_before_execution(self):
        release = FakeRelease()
        with patch.object(release, 'az') as azure, self.assertRaisesRegex(module.ReleaseError, 'container changed'):
            module.Release.run_job(release, 'migrate', 'wrong-container')
        azure.assert_not_called()

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
