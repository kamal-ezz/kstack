import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


COLLECTION = Path(__file__).resolve().parents[1]
SKILLS = {p.name for p in COLLECTION.iterdir() if (p / 'SKILL.md').is_file()}
spec = importlib.util.spec_from_file_location('installer', COLLECTION / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='skills installer ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.root), PATH=str(self.bin))
        self.env.pop('CODEX_HOME', None)
        self.env.pop('CLAUDE_CONFIG_DIR', None)

    def client(self, name):
        binary = self.bin / name
        binary.write_text('#!/bin/sh\nexit 0\n')
        binary.chmod(0o755)

    def run_installer(self, *args):
        return subprocess.run(
            [sys.executable, str(COLLECTION / 'install.py'), *args],
            env=self.env, cwd=self.root, capture_output=True, text=True,
        )

    def test_no_clients_does_not_write(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / '.codex').exists())
        self.assertFalse((self.root / '.claude').exists())

    def test_dry_run_does_not_write(self):
        self.client('codex')
        self.client('claude')
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / '.codex').exists())
        self.assertFalse((self.root / '.claude').exists())

    def test_links_all_skills_and_preserves_unrelated_files(self):
        for client in ('codex', 'claude'):
            self.client(client)
            sentinel = self.root / f'.{client}/skills/synced/keep.txt'
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text('keep')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        for client in ('codex', 'claude'):
            destination = self.root / f'.{client}/skills'
            self.assertEqual((destination / 'synced/keep.txt').read_text(), 'keep')
            for skill in SKILLS:
                self.assertTrue((destination / skill).is_symlink())
                self.assertEqual((destination / skill).resolve(), COLLECTION / skill)
            self.assertEqual((destination / 'davinci/LICENSE.txt').read_bytes(),
                             (COLLECTION / 'davinci/LICENSE.txt').read_bytes())
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        for client in ('codex', 'claude'):
            self.assertFalse((self.root / f'.{client}/skill-backups').exists())

    def test_custom_roots_and_target(self):
        self.client('codex')
        self.client('claude')
        self.env['CODEX_HOME'] = str(self.root / 'custom codex')
        self.env['CLAUDE_CONFIG_DIR'] = str(self.root / 'custom claude')
        result = self.run_installer('--target', 'codex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'custom codex/skills/ritchie').is_symlink())
        self.assertFalse((self.root / 'custom claude').exists())
        result = self.run_installer('--target', 'claude')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'custom claude/skills/ritchie').is_symlink())

    def test_backs_up_copies_wrong_links_and_broken_links(self):
        self.client('codex')
        skills = self.root / '.codex/skills'
        (skills / 'ritchie').mkdir(parents=True)
        (skills / 'ritchie/local.txt').write_text('old copy')
        outside = self.root / 'original skill'
        outside.mkdir()
        (outside / 'keep.txt').write_text('keep')
        (skills / 'linus').symlink_to(outside, target_is_directory=True)
        (skills / 'davinci').symlink_to(self.root / 'missing')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = self.root / '.codex/skill-backups'
        self.assertEqual(next(backups.glob('*/ritchie/local.txt')).read_text(), 'old copy')
        self.assertTrue(next(backups.glob('*/linus')).is_symlink())
        self.assertTrue(next(backups.glob('*/davinci')).is_symlink())
        self.assertEqual((outside / 'keep.txt').read_text(), 'keep')
        for skill in ('ritchie', 'linus', 'davinci'):
            self.assertEqual((skills / skill).resolve(), COLLECTION / skill)

    def test_source_edits_are_visible_without_rerunning(self):
        source = self.root / 'source/sample'
        source.mkdir(parents=True)
        (source / 'SKILL.md').write_text('before')
        target = self.root / 'client'
        installer.install_skill(source, target)
        installed = target / 'skills/sample'
        (source / 'SKILL.md').write_text('after')
        (source / 'asset.txt').write_text('new resource')
        self.assertEqual((installed / 'SKILL.md').read_text(), 'after')
        self.assertEqual((installed / 'asset.txt').read_text(), 'new resource')
        (source / 'asset.txt').unlink()
        self.assertFalse((installed / 'asset.txt').exists())

    def test_restores_previous_copy_if_link_placement_fails(self):
        source = self.root / 'source/sample'
        source.mkdir(parents=True)
        target = self.root / 'client'
        installed = target / 'skills/sample'
        installed.mkdir(parents=True)
        (installed / 'keep.txt').write_text('original')
        original_rename = Path.rename

        def rename(path, destination):
            if path.parent.name.startswith('.skill-install-'):
                raise OSError('simulated placement failure')
            return original_rename(path, destination)

        with patch.object(Path, 'rename', rename):
            with self.assertRaises(OSError):
                installer.install_skill(source, target)
        self.assertFalse(installed.is_symlink())
        self.assertEqual((installed / 'keep.txt').read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
