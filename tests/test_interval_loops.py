import unittest
from unittest import mock

from bin import mediamtx_collector, mediamtx_systeminfo


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class IntervalLoopTests(unittest.TestCase):
    def test_jobs_repeat_on_fixed_interval_after_initial_delay(self):
        for module in (mediamtx_collector, mediamtx_systeminfo):
            with self.subTest(module=module.__name__):
                clock = FakeClock()
                starts = []

                def job():
                    starts.append(clock.now)
                    if len(starts) == 3:
                        raise KeyboardInterrupt
                    clock.now += 2.0

                with (
                    mock.patch.object(module.time, "monotonic", clock.monotonic),
                    mock.patch.object(module.time, "sleep", clock.sleep),
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        module._run_interval_loop(job, 5.0)

                self.assertEqual(starts, [5.0, 10.0, 15.0])
                self.assertEqual(clock.sleeps, [5.0, 3.0, 3.0])

    def test_job_exception_does_not_stop_loop(self):
        for module in (mediamtx_collector, mediamtx_systeminfo):
            with self.subTest(module=module.__name__):
                clock = FakeClock()
                calls = 0

                def job():
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        raise RuntimeError("test failure")
                    raise KeyboardInterrupt

                with (
                    mock.patch.object(module.time, "monotonic", clock.monotonic),
                    mock.patch.object(module.time, "sleep", clock.sleep),
                    self.assertLogs(level="ERROR"),
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        module._run_interval_loop(job, 5.0)

                self.assertEqual(calls, 2)
                self.assertEqual(clock.sleeps, [5.0, 5.0])


if __name__ == "__main__":
    unittest.main()
