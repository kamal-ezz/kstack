import importlib.util
import ast
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evaluations', ROOT / 'evals/run.py')
evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evals)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_capture_rejects_path_traversal(self):
        for name in ('/tmp/escape', '../escape', 'nested/../../escape'):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as archive:
                info = tarfile.TarInfo(name)
                info.size = 1
                archive.addfile(info, io.BytesIO(b'x'))
            stream.seek(0)
            with self.assertRaises(ValueError):
                evals.extract_workspace(stream, self.root / name.replace('/', '_'))
        self.assertFalse((self.root / 'escape').exists())

    def test_capture_does_not_follow_links(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            link = tarfile.TarInfo('secret-link')
            link.type = tarfile.SYMTYPE
            link.linkname = '/home/kamal/.codex/auth.json'
            archive.addfile(link)
            file = tarfile.TarInfo('normal.txt')
            file.size = 4
            archive.addfile(file, io.BytesIO(b'safe'))
        stream.seek(0)
        output = self.root / 'output'
        skipped = evals.extract_workspace(stream, output)
        self.assertEqual(len(skipped), 1)
        self.assertFalse((output / 'secret-link').is_symlink())
        self.assertEqual((output / 'normal.txt').read_text(), 'safe')

    def test_capture_enforces_size_limits(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            info = tarfile.TarInfo('huge.txt')
            info.size = 9 * 1024 * 1024
            archive.addfile(info, io.BytesIO(b'x' * info.size))
        stream.seek(0)
        with self.assertRaises(ValueError):
            evals.extract_workspace(stream, self.root / 'output')

    def test_no_changes_check_detects_edits_and_commits(self):
        file = self.root / 'example.py'
        file.write_text('original')
        before = evals.snapshot(self.root)
        git = {'head': 'one'}
        case = {'checks': ['unchanged']}
        result = evals.automatic_checks(case, self.root, before, git, git, [], 'unused')
        self.assertTrue(all(check['passed'] for check in result))
        result = evals.automatic_checks(case, self.root, before, git, {'head': 'two'}, [], 'unused')
        self.assertFalse(result[-1]['passed'])
        file.write_text('edited')
        result = evals.automatic_checks(case, self.root, before, git, git, [], 'unused')
        self.assertFalse(result[-1]['passed'])

    def test_pass_requires_rubric_and_infrastructure_success(self):
        result = {'automatic': [{'passed': True}], 'rubric': [{'verdict': 'pending'}]}
        self.assertEqual(evals.status(result), 'needs-review')
        result['rubric'][0]['verdict'] = 'pass'
        self.assertEqual(evals.status(result), 'pass')
        result['automatic'][0]['passed'] = False
        self.assertEqual(evals.status(result), 'fail')
        result['error'] = 'timeout'
        self.assertEqual(evals.status(result), 'infrastructure-error')

    def test_credential_redaction_covers_artifacts_and_logs(self):
        secret = 'sensitive-' + 'x' * 30
        for name in ('events.jsonl', 'infrastructure.log', 'workspace/leak.txt'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(secret)
        evals.redact(self.root, [secret])
        for path in self.root.rglob('*'):
            if path.is_file():
                self.assertEqual(path.read_text(), '[REDACTED]')

    def test_cases_cover_all_skills_without_exposing_rubric_in_prompt(self):
        cases = evals.catalog()
        skills = {name for case in cases for name in case['skills']}
        self.assertEqual(skills, {'hamilton', 'vignelli', 'ramsay', 'linus', 'feynman', 'kranz'})
        for case in cases:
            self.assertTrue(case['rubric'])
            self.assertTrue(case['checks'])
            self.assertNotIn('rubric', case['files'])

    def test_runtime_context_is_identical_for_implicit_control_and_candidate(self):
        case = {'prompt': 'Explain example.py.', 'skills': ['feynman'],
                'rubric': [{'question': 'Private evaluator expectation'}]}
        runtime = {'tools': {'python3': '/usr/bin/python3'}}
        candidate = evals.evaluation_prompt(case, runtime)
        control = evals.evaluation_prompt(case, runtime, baseline=True)
        self.assertEqual(candidate, control)
        self.assertIn('/usr/bin/python3', candidate)
        self.assertNotIn('Private evaluator expectation', candidate)
        explicit = evals.evaluation_prompt(case, runtime, invocation='explicit')
        self.assertIn('$feynman', explicit)
        self.assertNotIn('$feynman', evals.evaluation_prompt(
            case, runtime, invocation='explicit', baseline=True))

    def test_manual_review_requires_and_persists_evidence(self):
        result = {'case': 'sample', 'automatic': [{'id': 'check', 'passed': True, 'evidence': 'tested'}],
                  'rubric': [{'id': 'clarity', 'question': 'Clear?', 'verdict': 'pending', 'evidence': ''}]}
        evals.write_report(self.root, result)
        arguments = ['run.py', 'review', str(self.root), '--criterion', 'clarity',
                     '--verdict', 'pass', '--evidence', 'response.md: clear worked example.']
        with patch.object(sys, 'argv', arguments), redirect_stdout(io.StringIO()):
            self.assertEqual(evals.main(), 0)
        saved = json.loads((self.root / 'result.json').read_text())
        self.assertEqual(saved['status'], 'pass')
        self.assertEqual(saved['rubric'][0]['evidence'], 'response.md: clear worked example.')
        arguments[-1] = ' '
        with patch.object(sys, 'argv', arguments), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                evals.main()
        self.assertEqual(error.exception.code, 2)

    def test_comparison_rejects_different_model_settings(self):
        before, after = self.root / 'before', self.root / 'after'
        manifest = {'case': 'sample', 'model': 'same-model', 'effort': 'high',
                    'image': 'same-image', 'invocation': 'implicit', 'scenario': {'prompt': 'same'}}
        for batch in (before, after):
            run = batch / 'sample-1'
            run.mkdir(parents=True)
            evals.save(run / 'manifest.json', manifest)
            evals.save(run / 'result.json', {'case': 'sample', 'status': 'needs-review'})
        arguments = ['run.py', 'compare', str(before), str(after)]
        with patch.object(sys, 'argv', arguments), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(evals.main(), 0)
        self.assertIn('needs-review', output.getvalue())
        manifest['effort'] = 'low'
        evals.save(after / 'sample-1/manifest.json', manifest)
        with patch.object(sys, 'argv', arguments), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                evals.main()
        self.assertEqual(error.exception.code, 2)


@unittest.skipUnless(os.environ.get('SKILL_EVAL_DOCKER') == '1', 'set SKILL_EVAL_DOCKER=1 after building the image')
class DockerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases = {case['id']: case for case in evals.catalog()}

    def test_snake_browser_reproducer_uses_real_focus_and_keyboard_events(self):
        case = self.cases['ramsay-browser-review']
        with evals.Container(evals.IMAGE) as container:
            evals.initialize(container, case, self.root)
            script = (ROOT / 'evals/checks/snake_browser.mjs').read_bytes()
            result = container.exec(['node', '--input-type=module'], data=script, timeout=40)
            evidence = json.loads(result.stdout)
            self.assertEqual(evidence['bodyPause']['status'], 'TAKE A BREATHER')
            self.assertEqual(evidence['speedSpace']['status'], 'IN THE GROOVE')
            self.assertEqual(evidence['speedSpace']['focus']['speed'], 'chill')
            self.assertTrue(all(event['trusted'] for event in evidence['speedSpace']['events']))

        # Negative control removes the button guard. This is a probe mutation,
        # not a recommended accessibility fix. The original-defect probe must fail.
        mutated = {**case, 'files': dict(case['files'])}
        mutated['files']['game.js'] = case['files']['game.js'].replace(
            "closest('button,a,input,select')", "closest('a,input,select')")
        self.assertNotEqual(mutated['files']['game.js'], case['files']['game.js'])
        (self.root / 'negative').mkdir()
        with evals.Container(evals.IMAGE) as container:
            evals.initialize(container, mutated, self.root / 'negative')
            result = container.exec(['node', '--input-type=module'], data=script, timeout=40, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'AssertionError', result.stderr)

    def test_runtime_capture_and_independent_grader(self):
        case = self.cases['hamilton-bug']
        inputs = self.root / 'inputs'
        inputs.mkdir()
        with evals.Container(evals.IMAGE) as container:
            before, git = evals.initialize(container, case, inputs)
            config = container.exec(['sh', '-c', 'test ! -e /home/kamal && test ! -e /var/run/docker.sock'])
            self.assertEqual(config.returncode, 0)
            config = json.loads(subprocess.run(
                ['docker', 'inspect', container.name, '--format', '{{json .HostConfig}}'],
                check=True, capture_output=True, text=True,
            ).stdout)
            self.assertTrue(config['ReadonlyRootfs'])
            self.assertFalse(config['Privileged'])
            self.assertFalse(config['Binds'])
            self.assertEqual(config['CapDrop'], ['ALL'])
            self.assertEqual(config['Memory'], 2 * 1024 ** 3)
            self.assertEqual(config['NanoCpus'], 2_000_000_000)
            self.assertEqual(config['NetworkMode'], 'none')
            denied = container.exec(['sh', '-c', 'touch /etc/should-not-exist'], check=False)
            self.assertNotEqual(denied.returncode, 0)
            skipped = container.export(self.root / 'workspace')
            self.assertEqual(evals.snapshot(self.root / 'workspace'), before)
        result = evals.automatic_checks(case, self.root / 'workspace', before, git, git, skipped, evals.IMAGE)
        self.assertFalse(result[-1]['passed'], 'Independent checker must reject the seeded bug')
        basket = self.root / 'workspace/basket.py'
        basket.write_text(basket.read_text().replace('item["price_cents"] for',
                                                   'item["price_cents"] * item["quantity"] for'))
        result = evals.automatic_checks(case, self.root / 'workspace', before, git, git, skipped, evals.IMAGE)
        self.assertTrue(result[-1]['passed'], result[-1]['evidence'])

    def test_commit_checker_preserves_staged_work(self):
        case = self.cases['linus-commit']
        inputs = self.root / 'inputs'
        inputs.mkdir()
        with evals.Container(evals.IMAGE) as container:
            before, before_git = evals.initialize(container, case, inputs)
            container.exec(['git', 'commit', '--only', '-qm', 'Update answer', '--', 'app.py'])
            after_git = evals.git_state(container)
            skipped = container.export(self.root / 'workspace')
        result = evals.automatic_checks(case, self.root / 'workspace', before, before_git, after_git, skipped, evals.IMAGE)
        self.assertTrue(result[-1]['passed'])
        after_git['staged_diff'] = ''
        result = evals.automatic_checks(case, self.root / 'workspace', before, before_git, after_git, skipped, evals.IMAGE)
        self.assertFalse(result[-1]['passed'])

    def test_session_checker_accepts_equivalent_refactor_and_rejects_regressions(self):
        case = self.cases['hamilton-session-refactor']
        workspace = self.root / 'workspace'
        workspace.mkdir()
        evals.write_files(workspace, case['files'])
        source = case['files']['session.py']
        # Formatting changes preserve semantics but are not a human readability pass.
        formatted = ast.unparse(ast.parse(source)) + '\n'
        (workspace / 'session.py').write_text(formatted)
        before = evals.snapshot(workspace)
        result = evals.automatic_checks(case, workspace, before, {}, {}, [], evals.IMAGE)
        self.assertTrue(result[-1]['passed'], result[-1]['evidence'])
        mutants = [
            source.replace('s["score"] += 1', 's["score"] += 0'),
            source.replace('s["queued"] is None', 'True'),
            source.replace('"fast": 90', '"fast": 91'),
        ]
        for mutation in mutants:
            self.assertNotEqual(mutation, source)
            (workspace / 'session.py').write_text(mutation)
            result = evals.automatic_checks(case, workspace, before, {}, {}, [], evals.IMAGE)
            self.assertFalse(result[-1]['passed'], 'Checker accepted a behavioral regression')
        (workspace / 'session.py').write_text(source)
        result = evals.automatic_checks(case, workspace, before, {}, {}, [], evals.IMAGE)
        self.assertFalse(result[-1]['passed'], 'An unchanged file is not the requested refactor')

    def test_runtime_manifest_matches_the_container(self):
        with evals.Container(evals.IMAGE) as container:
            runtime = evals.runtime_facts(container)
            self.assertEqual(runtime['working_directory'], '/workspace')
            self.assertIsNotNone(runtime['tools']['python3'])
            self.assertIsNotNone(runtime['tools']['chromium'])
            self.assertIsNone(runtime['tools']['python'])
            self.assertIsNone(runtime['tools']['gh'])
            self.assertEqual(runtime['configured_mcp_servers'], [])
            self.assertIn('0.165.0', runtime['versions']['codex'])

    def test_timeout_preserves_partial_workspace_and_stops_child(self):
        with evals.Container(evals.IMAGE) as container:
            code = "from pathlib import Path; import time; Path('partial.txt').write_text('started'); time.sleep(10); Path('finished.txt').write_text('wrong')"
            result = container.exec(['timeout', '--signal=TERM', '--kill-after=1s',
                                     '0.2s', 'python3', '-c', code], check=False)
            self.assertEqual(result.returncode, 124)
            skipped = container.export(self.root / 'workspace')
            self.assertFalse(skipped)
            self.assertEqual((self.root / 'workspace/partial.txt').read_text(), 'started')
            self.assertFalse((self.root / 'workspace/finished.txt').exists())

    def test_browser_screenshots(self):
        case = self.cases['vignelli-existing']
        workspace = self.root / 'workspace'
        workspace.mkdir()
        evals.write_files(workspace, case['files'])
        evals.screenshots(workspace, self.root, evals.IMAGE)
        for width in (375, 1280):
            self.assertTrue((self.root / f'viewport-{width}.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))


if __name__ == '__main__':
    unittest.main()
