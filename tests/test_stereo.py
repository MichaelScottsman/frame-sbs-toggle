import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import frame_stereo as fs


class Tests(unittest.TestCase):
    def setUp(self):
        mocked = patch.object(fs, "visible_layers", return_value=False)
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_discovery_excludes_subviews_and_ui(self):
        listing = "\n".join([
            "'valve.steam.desktopgame.123' -- 'Game', 1920x1080 visible VROverlayType_Dashboard_Main",
            "'valve.steam.desktopgame.123.layer1' -- 'Layer', visible VROverlayType_Subview",
            "'valve.steam.desktopgame.123.thumb' -- 'Thumb', visible VROverlayType_Dashboard_Thumbnail",
            "'valve.steam.gamepadui.main' -- 'Steam', visible VROverlayType_Dashboard_Main",
            "'valve.steam.desktopgame.0' -- 'Gamescope', not_visible VROverlayType_Dashboard_Main",
        ])
        self.assertEqual(fs.discover(listing), [('valve.steam.desktopgame.123', True), ('valve.steam.desktopgame.0', False)])

    def test_stream_detection_excludes_cursor_and_thumbnail(self):
        listing = "\n".join([
            "'steamlink_openvr-overlay' -- 'Game [Streaming]', 1920x1080 visible VROverlayType_Dashboard_Main",
            "'steamlink_openvr-overlay.thumb' -- 'Streaming Client', not_visible VROverlayType_Dashboard_Thumbnail",
            "'steamlink_openvr-cursor' -- 'Streaming Client', visible VROverlayType_Basic",
            "'valve.steam.desktopgame.0' -- 'Gamescope', not_visible VROverlayType_Dashboard_Main",
        ])
        self.assertEqual(fs.choose(fs.discover(listing)), 'steamlink_openvr-overlay')
        self.assertEqual(len(fs.discover(listing)), 2)

    def test_stream_does_not_change_gamescope_composition(self):
        with patch.object(fs, 'visible_layers') as layers, patch.object(fs, 'run') as run:
            fs.flatten('steamlink_openvr-overlay', None, {}, 'session')
            layers.assert_not_called()
            run.assert_not_called()

    def test_selection(self):
        with self.assertRaisesRegex(RuntimeError, 'No visible'):
            fs.choose([('a', False)])
        with self.assertRaisesRegex(RuntimeError, 'Multiple'):
            fs.choose([('a', True), ('b', True)])
        self.assertEqual(fs.choose([('a', False)], 'a'), 'a')
        with self.assertRaises(RuntimeError):
            fs.choose([('a', True)], 'system.systemui')

    def test_restore_idempotence_swap_and_restart(self):
        current = dict(handle='123', parallel=0, crossed=0, aspect=1.25, visible=1)
        def fake(key, state=None):
            if state is not None:
                current.update(state)
            return dict(current)
        with tempfile.TemporaryDirectory() as directory, patch.object(fs, 'helper', side_effect=fake), contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory) / 'state.json'
            fs.operate('on', 'a', False, path, 'session1')
            fs.operate('on', 'a', True, path, 'session1')
            self.assertEqual((current['parallel'], current['crossed'], current['aspect']), (False, True, 2.5))
            fs.operate('off', 'a', False, path, 'session1')
            self.assertEqual(current['aspect'], 1.25)
            fs.operate('off', 'a', False, path, 'session1')
            fs.operate('toggle', 'a', False, path, 'session1')
            fs.operate('toggle', 'a', False, path, 'session1')
            self.assertEqual(current['aspect'], 1.25)
            fs.operate('on', 'a', False, path, 'session1')
            current.update(parallel=0, crossed=0, aspect=1.0)
            fs.operate('off', 'a', False, path, 'session2')
            self.assertEqual(current['aspect'], 1.0)

    def test_reenable_preserves_saved_aspect_without_repeated_doubling(self):
        current = dict(handle='123', parallel=1, crossed=0, aspect=2.0, visible=1)
        original = dict(current, parallel=0, aspect=1.0)
        def fake(key, state=None):
            if state is not None:
                current.update(state)
            return dict(current)
        with tempfile.TemporaryDirectory() as directory, patch.object(fs, 'helper', side_effect=fake), contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory) / 'state.json'
            fs.save(path, {'session:123:a': original})
            fs.operate('on', 'a', False, path, 'session')
            self.assertEqual(current['aspect'], 2.0)
            self.assertTrue(current['parallel'])
            fs.operate('off', 'a', False, path, 'session')
            self.assertEqual(current, original)

    def test_composition_owned_until_last_screen_restored(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fs, 'visible_layers', side_effect=[True, False]), patch.object(fs, 'run') as run:
            path = Path(directory) / 'state.json'
            data = {'session:123:a': {}}
            fs.flatten('a', path, data, 'session')
            run.assert_any_call(['gamescopectl', 'composite_force', '1'])
            run.reset_mock()
            fs.restore_composition(path, data, 'session')
            run.assert_not_called()
            data.pop('session:123:a')
            fs.restore_composition(path, data, 'session')
            run.assert_any_call(['gamescopectl', 'composite_force', '0'])
            self.assertNotIn('_composition', data)

    def test_switch_formats_then_toggle_off(self):
        current = dict(handle='123', parallel=0, crossed=0, aspect=1.25, visible=1)
        def fake(key, state=None):
            if state is not None:
                current.update(state)
            return dict(current)
        with tempfile.TemporaryDirectory() as directory, patch.object(fs, 'helper', side_effect=fake), contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory) / 'state.json'
            fs.operate('toggle', 'a', False, path, 'session', 'full')
            self.assertTrue(current['parallel'])
            self.assertEqual(current['aspect'], 1.25)
            fs.operate('toggle', 'a', False, path, 'session', 'half')
            self.assertTrue(current['parallel'])
            self.assertEqual(current['aspect'], 2.5)
            fs.operate('toggle', 'a', False, path, 'session', 'full')
            self.assertTrue(current['parallel'])
            self.assertEqual(current['aspect'], 1.25)
            fs.operate('toggle', 'a', False, path, 'session', 'full')
            self.assertFalse(current['parallel'])
            self.assertEqual(current['aspect'], 1.25)

    def test_failure_retains_recovery_state(self):
        current = dict(handle='123', parallel=0, crossed=0, aspect=1.5, visible=1)
        def fake(key, state=None):
            if state is not None:
                raise RuntimeError('reset by compositor')
            return dict(current)
        with tempfile.TemporaryDirectory() as directory, patch.object(fs, 'helper', side_effect=fake):
            path = Path(directory) / 'state.json'
            with self.assertRaisesRegex(RuntimeError, 'reset'):
                fs.operate('on', 'a', False, path, 'session')
            self.assertIn('1.5', path.read_text())


if __name__ == '__main__':
    unittest.main()
