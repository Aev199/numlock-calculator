import types
import unittest

import app_single_instance


class FakeKernel32:
    def __init__(self, last_error=0):
        self.last_error = last_error
        self.created_events = []
        self.created_mutexes = []
        self.signaled = []
        self.closed = []

    def CreateEventW(self, _security, manual_reset, initial_state, name):
        self.created_events.append((manual_reset, initial_state, name))
        return 101

    def CreateMutexW(self, _security, initial_owner, name):
        self.created_mutexes.append((initial_owner, name))
        return 202

    def GetLastError(self):
        return self.last_error

    def SetEvent(self, handle):
        self.signaled.append(handle)
        return True

    def WaitForSingleObject(self, _handle, _timeout):
        return app_single_instance.WAIT_FAILED

    def CloseHandle(self, handle):
        self.closed.append(handle)
        return True


class SingleInstanceTests(unittest.TestCase):
    def make_app(self):
        calls = []
        activations = []
        app = types.SimpleNamespace(
            main=lambda: calls.append("main"),
            show_window=lambda: activations.append("show"),
            _window=None,
            _quitting=False,
        )
        return app, calls, activations

    def test_second_instance_signals_existing_process_and_exits(self):
        app, calls, _activations = self.make_app()
        kernel = FakeKernel32(app_single_instance.ERROR_ALREADY_EXISTS)
        app_single_instance.install(app, kernel32=kernel, platform_name="nt")

        app.main()

        self.assertEqual(calls, [])
        self.assertEqual(kernel.signaled, [101])
        self.assertCountEqual(kernel.closed, [101, 202])

    def test_first_instance_runs_and_releases_native_handles(self):
        app, calls, _activations = self.make_app()
        kernel = FakeKernel32(0)
        app_single_instance.install(app, kernel32=kernel, platform_name="nt")

        app.main()

        self.assertEqual(calls, ["main"])
        self.assertIn(101, kernel.signaled)
        self.assertCountEqual(kernel.closed, [101, 202])
        self.assertIsNone(app._single_instance_mutex)
        self.assertIsNone(app._single_instance_event)

    def test_non_windows_entry_point_is_unchanged(self):
        app, calls, _activations = self.make_app()
        kernel = FakeKernel32(0)
        app_single_instance.install(app, kernel32=kernel, platform_name="posix")

        app.main()

        self.assertEqual(calls, ["main"])
        self.assertEqual(kernel.created_events, [])
        self.assertEqual(kernel.created_mutexes, [])

    def test_install_is_idempotent(self):
        app, _calls, _activations = self.make_app()
        kernel = FakeKernel32(0)
        app_single_instance.install(app, kernel32=kernel, platform_name="posix")
        first = app.main
        app_single_instance.install(app, kernel32=kernel, platform_name="posix")
        self.assertIs(app.main, first)


if __name__ == "__main__":
    unittest.main()
