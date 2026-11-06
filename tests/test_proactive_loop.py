import threading
import unittest

from jarvis_assistant.proactive_loop import ProactiveLoop


class ProactiveLoopTests(unittest.TestCase):
    def test_emits_checked_messages_until_stopped(self):
        emitted: list[tuple[str, str]] = []
        stopped = threading.Event()
        sleeps = 0

        def check() -> list[str]:
            stopped.set()
            return ["Reminder: stretch"]

        def sleep(_seconds: float) -> None:
            nonlocal sleeps
            sleeps += 1

        loop = ProactiveLoop(
            check=check,
            emit=lambda kind, payload: emitted.append((kind, payload)),
            interval_seconds=30,
            should_stop=stopped.is_set,
            sleep=sleep,
        )

        loop.run_once()

        self.assertEqual(emitted, [("proactive_notice", "Reminder: stretch")])
        self.assertEqual(sleeps, 0)

    def test_checks_before_sleeping_so_due_notices_speak_up_immediately(self):
        stopped = threading.Event()
        calls: list[str] = []

        def check() -> list[str]:
            calls.append("check")
            stopped.set()
            return []

        def sleep(_seconds: float) -> None:
            calls.append("sleep")

        loop = ProactiveLoop(
            check=check,
            emit=lambda _kind, _payload: None,
            interval_seconds=30,
            should_stop=stopped.is_set,
            sleep=sleep,
        )

        loop.run_once()

        self.assertEqual(calls, ["check"])

    def test_stop_prevents_future_checks(self):
        checks: list[str] = []
        loop = ProactiveLoop(
            check=lambda: checks.append("check") or [],
            emit=lambda _kind, _payload: None,
            interval_seconds=30,
            should_stop=lambda: False,
            sleep=lambda _seconds: None,
        )

        loop.stop()
        loop.run_forever()

        self.assertEqual(checks, [])

    def test_run_once_uses_interruptible_wait_when_available(self):
        waits: list[float] = []
        sleeps: list[float] = []
        loop = ProactiveLoop(
            check=lambda: [],
            emit=lambda _kind, _payload: None,
            interval_seconds=30,
            should_stop=lambda: False,
            wait=lambda seconds: waits.append(seconds) or False,
            sleep=lambda seconds: sleeps.append(seconds),
        )

        loop.run_once()

        self.assertEqual(waits, [30])
        self.assertEqual(sleeps, [])

    def test_default_wait_can_be_interrupted_by_stop(self):
        checked = threading.Event()
        loop = ProactiveLoop(
            check=lambda: checked.set() or [],
            emit=lambda _kind, _payload: None,
            interval_seconds=10,
            should_stop=lambda: False,
        )

        thread = threading.Thread(target=loop.run_once)
        thread.start()
        checked.wait(timeout=1)
        loop.stop()
        thread.join(timeout=1)

        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
