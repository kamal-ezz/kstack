#!/usr/bin/env python3
"""Behavioral skill evaluations in disposable, resource-limited Docker containers."""

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'my-skills-eval:codex-0.165.0'
LIMIT = 64 * 1024 * 1024


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def relative_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Unsafe relative path: {name}')
    return path


def catalog():
    cases = json.loads((ROOT / 'evals/cases.json').read_text())
    ids = set()
    for case in cases:
        if case.get('fixture'):
            fixture = ROOT / 'evals/fixtures' / relative_name(case['fixture'])
            files = {}
            for path in sorted(fixture.rglob('*')):
                if path.is_symlink():
                    raise ValueError(f'Fixture must not contain links: {path}')
                if path.is_file() and '__pycache__' not in path.parts:
                    files[str(path.relative_to(fixture))] = path.read_text()
            if not files:
                raise ValueError(f'Fixture is empty or missing: {fixture}')
            case['files'] = {**files, **case['files']}
        if not re.fullmatch(r'[a-z0-9-]+', case['id']) or case['id'] in ids:
            raise ValueError('Case IDs must be unique lowercase names')
        ids.add(case['id'])
        for name in [*case['files'], *case.get('changes', {}), *case.get('staged', [])]:
            path = relative_name(name)
            if not path.parts or '.git' in path.parts:
                raise ValueError(f'Invalid fixture path: {name}')
        rubric_ids = [item['id'] for item in case['rubric']]
        if len(set(rubric_ids)) != len(rubric_ids):
            raise ValueError('Rubric IDs must be unique within each case')
    return cases


def write_files(root, files):
    for name, contents in files.items():
        path = root / relative_name(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)


def snapshot(root):
    records = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if relative.parts[0] == '.git':
            continue
        if path.is_symlink():
            records[str(relative)] = {'link': os.readlink(path)}
        elif path.is_file():
            records[str(relative)] = {
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'mode': path.stat().st_mode & 0o777,
            }
    return records


def archive_tree(root):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'Input snapshots must not contain symlinks: {path}')
            info = archive.gettarinfo(str(path), str(path.relative_to(root)))
            info.uid = info.gid = 1000
            if path.is_file():
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
            elif path.is_dir():
                archive.addfile(info)
            else:
                raise ValueError(f'Unsupported input: {path}')
    return output.getvalue()


def extract_workspace(archive_path, destination):
    """Never follow agent-created links or extract special files onto the host."""
    destination.mkdir(parents=True)
    skipped = []
    total = 0
    with tarfile.open(fileobj=archive_path, mode='r:*') as archive:
        for index, member in enumerate(archive):
            if index >= 10000:
                raise ValueError('Too many workspace artifacts')
            relative = relative_name(member.name)
            if not relative.parts or relative.parts[0] == '.git':
                continue
            path = destination / relative
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                total += member.size
                if member.size > 8 * 1024 * 1024 or total > LIMIT:
                    raise ValueError('Workspace artifacts exceed capture limits')
                path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation also rejects duplicate archive paths.
                with path.open('xb') as target:
                    shutil.copyfileobj(archive.extractfile(member), target)
                path.chmod(member.mode & 0o777)
            else:
                skipped.append({'path': str(relative), 'type': str(member.type), 'target': member.linkname})
    return skipped


class Container:
    def __init__(self, image, network='none'):
        self.image = image
        self.network = network
        self.name = 'skill-eval-' + uuid.uuid4().hex[:12]

    def __enter__(self):
        command = [
            'docker', 'run', '-d', '--name', self.name, '--init', '--read-only',
            '--user', '1000:1000', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--pids-limit=256', '--memory=2g', '--cpus=2', '--network', self.network,
            '--tmpfs', '/workspace:rw,size=128m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/home/agent:rw,size=64m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/tmp:rw,size=256m,mode=1777', self.image,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=30)
            self.exec(['mkdir', '-p', '/home/agent/.codex/skills'])
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args):
        subprocess.run(['docker', 'rm', '-f', self.name], capture_output=True, timeout=30)

    def exec(self, command, *, data=None, timeout=30, check=True):
        return subprocess.run(
            ['docker', 'exec', '-i', self.name, *command], input=data,
            capture_output=True, timeout=timeout, check=check,
        )

    def copy(self, root, destination):
        self.exec(['tar', '--extract', '--file=-', '--directory', destination,
                   '--no-same-owner'], data=archive_tree(root))

    def export(self, destination):
        # /workspace is a 128MB tmpfs, bounding archive size even for bad runs.
        with tempfile.TemporaryFile() as stream:
            subprocess.run(['docker', 'exec', self.name, 'tar', '--create', '--file=-',
                            '--exclude=./.git', '--directory=/workspace', '.'],
                           stdout=stream, stderr=subprocess.PIPE, check=True, timeout=30)
            stream.seek(0)
            return extract_workspace(stream, destination)


def git_state(container):
    def git(*args):
        return container.exec([
            'git', '--no-pager', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
            *args,
        ]).stdout.decode()
    return {
        'head': git('rev-parse', 'HEAD').strip(),
        'commit_count': int(git('rev-list', '--count', 'HEAD')),
        'last_commit_files': git('diff-tree', '--root', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines(),
        'subject': git('log', '-1', '--format=%s').strip(),
        'staged_diff': git('diff', '--cached', '--no-ext-diff', '--no-textconv', '--binary'),
        'status': git('status', '--porcelain=v1'),
    }


def runtime_facts(container):
    code = """import json, shutil, subprocess
names = ['python3', 'python', 'node', 'git', 'chromium', 'codex', 'gh', 'docker', 'gcloud', 'aws', 'ansible', 'vagrant']
versions = ['python3', 'node', 'git', 'chromium', 'codex']
tools = {name: shutil.which(name) for name in names}
print(json.dumps({'working_directory': '/workspace', 'tools': tools,
    'versions': {name: subprocess.check_output([name, '--version'], text=True).strip() for name in versions},
    'configured_mcp_servers': [], 'persistent_browser_session': False,
    'hosting_or_cloud_credentials_configured': False}))
"""
    return json.loads(container.exec(['python3', '-c', code]).stdout)


def evaluation_prompt(case, runtime, invocation='implicit', baseline=False):
    request = case['prompt']
    if invocation == 'explicit' and not baseline:
        request = 'Use ' + ', '.join('$' + name for name in case['skills']) + '.\n\n' + request
    return 'Runtime capabilities:\n' + json.dumps(runtime, indent=2) + '\n\nUser request:\n' + request


def harness_snapshot():
    return {str(path.relative_to(ROOT / 'evals')): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / 'evals').rglob('*'))
            if path.suffix in ('.py', '.mjs') and 'fixtures' not in path.relative_to(ROOT / 'evals').parts}


def initialize(container, case, inputs):
    workspace = inputs / 'workspace'
    workspace.mkdir()
    write_files(workspace, case['files'])
    container.copy(workspace, '/workspace')
    for command in [
        ['git', 'init', '-q', '--initial-branch=main'],
        ['git', 'config', 'user.name', 'Skill Evaluation'],
        ['git', 'config', 'user.email', 'eval@example.invalid'],
        ['git', 'add', '.'],
        ['git', 'commit', '--allow-empty', '-qm', 'Initial fixture'],
    ]:
        container.exec(command)
    if case.get('changes'):
        write_files(workspace, case['changes'])
        with tempfile.TemporaryDirectory() as folder:
            write_files(Path(folder), case['changes'])
            container.copy(Path(folder), '/workspace')
    if case.get('staged'):
        container.exec(['git', 'add', '--', *case['staged']])
    return snapshot(workspace), git_state(container)


class Content(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.words = []
        self.hidden = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.words.extend(data.split())


def independent_python(output, code, image, extra_files=None):
    with Container(image) as judge:
        judge.copy(output, '/workspace')
        if extra_files:
            with tempfile.TemporaryDirectory() as folder:
                write_files(Path(folder), extra_files)
                judge.copy(Path(folder), '/tmp')
        try:
            result = judge.exec(['python3', '-B', '-c', code], check=False, timeout=15)
            return result.returncode == 0, (result.stdout + result.stderr).decode(errors='replace')
        except subprocess.TimeoutExpired:
            return False, 'Generated code exceeded the independent check time limit.'


def automatic_checks(case, output, before, before_git, after_git, skipped, image):
    after = snapshot(output)
    results = [{'id': 'captured-artifacts', 'passed': not skipped,
                'evidence': 'Unsupported links/special files: ' + json.dumps(skipped)}]
    for check in case['checks']:
        if check == 'unchanged':
            passed = before == after and before_git == after_git
            evidence = 'Compared file contents/modes, HEAD, index, and Git status before and after.'
        elif check == 'commit_scope':
            passed = (after_git['commit_count'] == before_git['commit_count'] + 1
                      and after_git['last_commit_files'] == ['app.py']
                      and after_git['staged_diff'] == before_git['staged_diff']
                      and before == after)
            evidence = 'Compared commit count, committed paths, staged patch, and working files.'
        elif check == 'basket_behavior':
            code = '''from basket import total_cents
assert total_cents([]) == 0
assert total_cents([{"price_cents": 250, "quantity": 3}]) == 750
assert total_cents([{"price_cents": 199, "quantity": 2}, {"price_cents": 350, "quantity": 0}, {"price_cents": 75, "quantity": 3}]) == 623
print("Independent quantity, zero-quantity, empty, and multi-item checks passed.")'''
            passed, evidence = independent_python(output, code, image)
        elif check == 'session_behavior':
            code = (ROOT / 'evals/checks/session_behavior.py').read_text()
            passed, evidence = independent_python(
                output, code, image, {'reference_session.py': case['files']['session.py']})
            session = output / 'session.py'
            changed = session.is_file() and session.read_text() != case['files']['session.py']
            passed = passed and changed
            if not changed:
                evidence += '\nRequested refactor did not change session.py.'
        elif check == 'page_contract':
            html = output / 'index.html'
            passed = html.is_file() and Content(html.read_text()).words == Content(case['files']['index.html']).words
            evidence = 'Compared page text with the fixture; visual identity and behavior still need human review.'
        else:
            raise ValueError(f'Unknown automatic check: {check}')
        results.append({'id': check, 'passed': passed, 'evidence': evidence})
    return results


def screenshots(output, run, image):
    with Container(image) as browser:
        browser.copy(output, '/workspace')
        for width in (375, 1280):
            name = f'viewport-{width}.png'
            command = [
                'chromium', '--headless', '--no-sandbox', '--disable-dev-shm-usage',
                '--disable-gpu', '--hide-scrollbars', '--run-all-compositor-stages-before-draw',
                '--virtual-time-budget=1000', f'--window-size={width},900',
                f'--screenshot=/tmp/{name}', 'file:///workspace/index.html',
            ]
            result = browser.exec(command, timeout=30, check=False)
            (run / f'{name}.log').write_bytes(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(f'Chromium failed at {width}px; see screenshot log')
            (run / name).write_bytes(browser.exec(['cat', f'/tmp/{name}'], timeout=15).stdout)


def redact(run, secrets):
    for path in run.rglob('*'):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            cleaned = data
            for secret in secrets:
                cleaned = cleaned.replace(secret.encode(), b'[REDACTED]')
            if cleaned != data:
                path.write_bytes(cleaned)


def secret_strings(value):
    if isinstance(value, dict):
        return [text for item in value.values() for text in secret_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in secret_strings(item)]
    return [value] if isinstance(value, str) and len(value) > 24 else []


def response_from_events(path):
    messages = []
    for line in path.read_text(errors='replace').splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get('item', {})
        if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
            messages.append(item.get('text', ''))
    return '\n\n'.join(messages)


def status(result):
    if result.get('error'):
        return 'infrastructure-error'
    if any(not item['passed'] for item in result['automatic']):
        return 'fail'
    verdicts = [item['verdict'] for item in result['rubric']]
    if 'fail' in verdicts:
        return 'fail'
    return 'needs-review' if 'pending' in verdicts else 'pass'


def write_report(run, result):
    result['status'] = status(result)
    save(run / 'result.json', result)
    lines = [f"# {result['case']}: {result['status']}", '',
             'Automatic checks are separate from human judgment. A successful agent exit is not a passing evaluation.', '']
    if result.get('error'):
        lines += ['Infrastructure error: ' + result['error'], '']
    for item in result['automatic']:
        lines += [f"- {'PASS' if item['passed'] else 'FAIL'}: {item['id']} — {item['evidence']}"]
    lines += ['', '## Human rubric', '']
    for item in result['rubric']:
        lines += [f"- {item['id']} [{item['verdict']}]: {item['question']}",
                  '  Evidence: ' + item.get('evidence', '')]
    lines += ['', 'Inspect response.md, events.jsonl, before/after snapshots, workspace/, and any viewport PNGs.']
    (run / 'report.md').write_text('\n'.join(lines) + '\n')


def run_case(args, case, batch, iteration, image_id, auth):
    run = batch / f"{case['id']}-{iteration}"
    run.mkdir()
    inputs = run / 'inputs'
    inputs.mkdir()
    skills = inputs / 'skills'
    skills.mkdir()
    if not args.baseline:
        for skill in sorted(args.skills_root.iterdir()):
            if skill.is_dir() and not skill.is_symlink() and (skill / 'SKILL.md').is_file():
                shutil.copytree(skill, skills / skill.name, symlinks=True)
        for name in case['skills']:
            if not (skills / name / 'SKILL.md').is_file():
                raise ValueError(f'Missing skill in snapshot: {name}')
    (inputs / 'request.txt').write_text(case['prompt'])
    manifest = {
        'case': case['id'], 'iteration': iteration, 'model': args.model, 'effort': args.effort,
        'image': image_id, 'baseline': args.baseline, 'invocation': args.invocation,
        'timeout_seconds': args.timeout, 'skill_snapshot': snapshot(skills),
        'harness_snapshot': harness_snapshot(),
        'scenario': case, 'started_at': datetime.now(timezone.utc).isoformat(),
    }
    save(run / 'manifest.json', manifest)
    started = time.monotonic()
    result = {'case': case['id'], 'automatic': [],
              'rubric': [dict(item, verdict='pending', evidence='') for item in case['rubric']]}
    secrets = secret_strings(json.loads(auth))
    try:
        with Container(args.image, network='bridge') as container:
            before, before_git = initialize(container, case, inputs)
            save(run / 'before.json', {'files': before, 'git': before_git})
            container.copy(skills, '/home/agent/.codex/skills')
            # Only the Codex credential is sent, never the host home or config.
            with tempfile.TemporaryDirectory() as folder:
                credential = Path(folder) / 'auth.json'
                credential.write_bytes(auth)
                credential.chmod(0o600)
                container.copy(Path(folder), '/home/agent/.codex')
            runtime = runtime_facts(container)
            save(inputs / 'runtime.json', runtime)
            prompt = evaluation_prompt(case, runtime, args.invocation, args.baseline)
            (inputs / 'prompt.txt').write_text(prompt)
            manifest['runtime'] = runtime
            manifest['codex_version'] = runtime['versions']['codex']
            save(run / 'manifest.json', manifest)
            command = [
                'docker', 'exec', '-i', container.name, 'timeout', '--signal=TERM',
                '--kill-after=5s', f'{args.timeout}s', 'codex', 'exec', '--json',
                '--ephemeral', '--ignore-user-config', '--ignore-rules',
                '--sandbox', 'danger-full-access', '--model', args.model,
                '-c', 'model_reasoning_effort=' + json.dumps(args.effort),
                '-c', 'cli_auth_credentials_store="file"', '-C', '/workspace', '-',
            ]
            timed_out = False
            with (run / 'events.jsonl').open('wb') as stdout, (run / 'stderr.log').open('wb') as stderr:
                try:
                    agent = subprocess.run(command, input=prompt.encode(), stdout=stdout,
                                           stderr=stderr, timeout=args.timeout + 15)
                    result['agent_exit_code'] = agent.returncode
                    if agent.returncode == 124:
                        result['error'] = 'Agent exceeded the configured time limit; partial artifacts captured.'
                except subprocess.TimeoutExpired:
                    timed_out = True
                    result['error'] = 'Agent exceeded the configured time limit.'
            if timed_out:
                # Exiting the context removes the container and all remaining processes.
                return
            after_git = git_state(container)
            skipped = container.export(run / 'workspace')
            save(run / 'after.json', {'files': snapshot(run / 'workspace'), 'git': after_git, 'skipped': skipped})
        if result['agent_exit_code']:
            result.setdefault('error', 'Codex exited unsuccessfully; inspect redacted logs.')
        else:
            result['automatic'] = automatic_checks(case, run / 'workspace', before, before_git, after_git, skipped, args.image)
            if case.get('screenshots'):
                screenshots(run / 'workspace', run, args.image)
    except KeyboardInterrupt:
        result['error'] = 'Run interrupted.'
        raise
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        detail = str(error)
        stderr = getattr(error, 'stderr', None)
        if stderr:
            detail += '\n' + (stderr.decode(errors='replace') if isinstance(stderr, bytes) else stderr)
        (run / 'infrastructure.log').write_text(detail)
        result['error'] = f'{type(error).__name__}: see infrastructure.log.'
    finally:
        result['elapsed_seconds'] = round(time.monotonic() - started, 2)
        if (run / 'events.jsonl').exists():
            (run / 'response.md').write_text(response_from_events(run / 'events.jsonl'))
        write_report(run, result)
        redact(run, secrets)
        print(f"{case['id']} [{iteration}]: {result['status']} — {run / 'report.md'}", flush=True)
    return result


def positive(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError('must be positive')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list', help='List scenarios and intended skill routing')
    build = commands.add_parser('build', help='Build the pinned Codex runtime image')
    build.add_argument('--image', default=IMAGE)
    run = commands.add_parser('run', help='Run selected cases; uses your Codex account')
    run.add_argument('--case', action='append', required=True, help='Case ID; repeat or use all')
    run.add_argument('--model', required=True, help='Exact Codex model; never chosen implicitly')
    run.add_argument('--effort', default='high', choices=['low', 'medium', 'high', 'xhigh'])
    run.add_argument('--image', default=IMAGE)
    run.add_argument('--repeat', type=positive, default=1)
    run.add_argument('--timeout', type=positive, default=180)
    run.add_argument('--baseline', action='store_true', help='Run without this collection installed')
    run.add_argument('--invocation', choices=['implicit', 'explicit'], default='implicit')
    run.add_argument('--skills-root', type=Path, default=ROOT)
    run.add_argument('--output', type=Path, default=ROOT / '.eval-runs')
    run.add_argument('--auth-file', type=Path,
                     default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'auth.json')
    review = commands.add_parser('review', help='Record a human rubric verdict with evidence')
    review.add_argument('run', type=Path)
    review.add_argument('--criterion', required=True)
    review.add_argument('--verdict', choices=['pass', 'fail', 'not-applicable'], required=True)
    review.add_argument('--evidence', required=True)
    compare = commands.add_parser('compare', help='Summarize two batches without hiding pending reviews')
    compare.add_argument('before', type=Path)
    compare.add_argument('after', type=Path)
    args = parser.parse_args()
    cases = catalog()
    if args.command == 'list':
        for case in cases:
            print(f"{case['id']}: {', '.join(case['skills'])}")
    elif args.command == 'build':
        subprocess.run(['docker', 'build', '-t', args.image, str(ROOT / 'evals')], check=True)
    elif args.command == 'review':
        result = json.loads((args.run / 'result.json').read_text())
        matches = [item for item in result['rubric'] if item['id'] == args.criterion]
        if not matches or not args.evidence.strip():
            parser.error('Provide an existing rubric criterion and nonempty evidence')
        matches[0].update(verdict=args.verdict, evidence=args.evidence)
        write_report(args.run, result)
        print(result['status'])
    elif args.command == 'compare':
        def summary(root):
            results = {}
            for path in sorted(root.glob('*/result.json')):
                item = json.loads(path.read_text())
                results.setdefault(item['case'], []).append(item['status'])
            return results
        before, after = summary(args.before), summary(args.after)
        if not before or not after:
            parser.error('Both paths must contain batch results')
        for case in before.keys() & after.keys():
            def configurations(root):
                fields = ('model', 'effort', 'image', 'invocation', 'scenario',
                          'timeout_seconds', 'runtime', 'harness_snapshot')
                return {json.dumps({field: manifest.get(field, '<unrecorded>') for field in fields}, sort_keys=True)
                        for path in root.glob('*/manifest.json')
                        if (manifest := json.loads(path.read_text()))['case'] == case}
            if configurations(args.before) != configurations(args.after):
                parser.error(f'{case}: model, effort, image, invocation, scenario, timeout, runtime, or harness differs; results are not comparable')
        print('Case\tBefore\tAfter')
        for case in sorted(before.keys() | after.keys()):
            print(f"{case}\t{', '.join(before.get(case, ['not run']))}\t{', '.join(after.get(case, ['not run']))}")
        print('Compare matching model, effort, image, scenarios, and invocation; repeats are independent samples.')
    elif args.command == 'run':
        requested = set(args.case)
        unknown = requested - {case['id'] for case in cases} - {'all'}
        if unknown:
            parser.error('Unknown cases: ' + ', '.join(sorted(unknown)))
        selected = [case for case in cases if 'all' in requested or case['id'] in requested]
        if args.repeat > 10 or args.timeout > 1800:
            parser.error('Use at most 10 repeats and 1800 seconds per case')
        auth = args.auth_file.read_bytes()
        json.loads(auth)
        image_id = subprocess.run(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'],
                                  check=True, capture_output=True, text=True).stdout.strip()
        args.output.mkdir(parents=True, exist_ok=True)
        batch = args.output / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
        batch.mkdir(mode=0o700)
        print(f'Batch: {batch}', flush=True)
        failed = False
        for case in selected:
            for iteration in range(1, args.repeat + 1):
                result = run_case(args, case, batch, iteration, image_id, auth)
                failed |= result is None or result['status'] in ('fail', 'infrastructure-error')
        return 1 if failed else 0
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Interrupted; disposable containers are cleaned up.', file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'{type(error).__name__}: evaluation command failed. Check paths, Docker, and authentication.', file=sys.stderr)
        sys.exit(1)
