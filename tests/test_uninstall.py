import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import uninstall as u


class UninstallTests(unittest.TestCase):
    def test_removes_owned_files_only_and_can_repeat(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(u.shutil, 'which', return_value=None), contextlib.redirect_stdout(io.StringIO()):
            home = Path(temp)
            owned = home / '.local/bin/frame-stereo'
            owned.parent.mkdir(parents=True)
            owned.write_text('launcher')
            other = owned.parent / 'another-app'
            other.write_text('keep')
            runtime = home / 'runtime'
            u.uninstall(home, runtime)
            u.uninstall(home, runtime)
            self.assertFalse(owned.exists())
            self.assertEqual(other.read_text(), 'keep')

    def test_failure_keeps_installed_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(u, 'restore', side_effect=RuntimeError('restore rejected')):
            home = Path(temp)
            owned = home / '.local/bin/frame-stereo'
            owned.parent.mkdir(parents=True)
            owned.write_text('launcher')
            with self.assertRaises(RuntimeError):
                u.uninstall(home, home / 'runtime')
            self.assertTrue(owned.exists())

    def test_restore_skips_recreated_handles_and_restores_hidden_screens(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(u.stereo, 'session', return_value='sid'), patch.object(u.stereo, 'run', return_value="'valve.steam.desktopgame.1' -- 'Game', not_visible X"), patch.object(u.stereo, 'helper') as helper, contextlib.redirect_stdout(io.StringIO()):
            path = Path(temp) / 'state.json'
            original = dict(handle='old', parallel=0, crossed=0, aspect=1)
            for live, expected_calls in [('new', 1), ('old', 2)]:
                helper.reset_mock()
                helper.return_value = dict(original, handle=live)
                u.stereo.save(path, {'sid:old:valve.steam.desktopgame.1': original})
                u.restore(path)
                self.assertEqual(helper.call_count, expected_calls)
                self.assertEqual(path.read_text(), '{}')
