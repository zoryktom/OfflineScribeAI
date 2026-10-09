import socket
import unittest
import urllib.request

from offlinescribe.privacy import NetworkSandbox, NetworkSandboxViolation


class PrivacyTests(unittest.TestCase):
    def test_network_sandbox_blocks_socket_creation(self):
        with self.assertRaises(NetworkSandboxViolation):
            with NetworkSandbox("unit test"):
                socket.socket()

    def test_network_sandbox_blocks_urlopen_and_records_attempts(self):
        sandbox = NetworkSandbox("unit test")
        with self.assertRaises(NetworkSandboxViolation):
            with sandbox:
                urllib.request.urlopen("https://example.com")

        self.assertTrue(sandbox.attempts)
        self.assertEqual(sandbox.attempts[0].operation, "urllib.request.urlopen")


if __name__ == "__main__":
    unittest.main()
