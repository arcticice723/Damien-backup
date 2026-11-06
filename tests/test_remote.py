import json
import threading
import unittest
import urllib.error
import urllib.request

from jarvis_assistant.remote import RemoteControlServer


class RemoteControlServerTests(unittest.TestCase):
    def test_submit_command_waits_for_completion(self):
        received = {}
        server = RemoteControlServer(
            "127.0.0.1",
            0,
            "123456",
            command_callback=lambda request_id, text: received.update({"id": request_id, "text": text}),
            status_callback=lambda: {"status": "ready"},
        )

        def complete_later():
            while "id" not in received:
                pass
            server.complete(received["id"], "Done.")

        threading.Thread(target=complete_later, daemon=True).start()

        self.assertEqual(server.submit_command("hello", timeout_seconds=2), "Done.")
        self.assertEqual(received["text"], "hello")

    def test_http_command_requires_pin(self):
        received = {}
        server = RemoteControlServer(
            "127.0.0.1",
            0,
            "123456",
            command_callback=lambda request_id, text: (
                received.update({"id": request_id, "text": text}),
                server.complete(request_id, "Accepted."),
            ),
            status_callback=lambda: {"status": "ready"},
        )
        server.start()
        try:
            bad_request = urllib.request.Request(
                f"http://127.0.0.1:{server.port}/api/command",
                data=json.dumps({"pin": "000000", "text": "hello"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(bad_request, timeout=2)
            self.assertEqual(error.exception.code, 403)

            good_request = urllib.request.Request(
                f"http://127.0.0.1:{server.port}/api/command",
                data=json.dumps({"pin": "123456", "text": "hello"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(good_request, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["response"], "Accepted.")
            self.assertEqual(received["text"], "hello")
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
