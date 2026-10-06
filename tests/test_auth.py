"""
Automated Test Suite for HTTP Basic Authentication in Outreach Agent Dashboard.
Verifies all 6 mandatory security constraints:
  1. Unauthenticated request to UI triggers 401 with WWW-Authenticate header.
  2. Invalid credentials return 401.
  3. Valid credentials succeed (200 OK) for static files and API endpoints.
  4. Direct API calls without credentials are rejected with 401.
  5. Unset AUTH_USERNAME/AUTH_PASSWORD fails closed (denies all access with 401).
  6. webhook_server.py remains completely independent with zero Basic Auth requirement.
"""
import os
import time
import base64
import unittest
import threading
from http.server import HTTPServer
import urllib.request
import urllib.error

# Set test credentials before importing web_dashboard
os.environ["AUTH_USERNAME"] = "testadmin"
os.environ["AUTH_PASSWORD"] = "testpass123!"

from web_dashboard import DashboardHandler


class TestHTTPBasicAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 5059
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = HTTPServer(("127.0.0.1", cls.port), DashboardHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        os.environ["AUTH_USERNAME"] = "testadmin"
        os.environ["AUTH_PASSWORD"] = "testpass123!"

    def _make_request(self, path, auth_tuple=None, method="GET", data=None):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, data=data, method=method)
        if auth_tuple:
            user, pwd = auth_tuple
            token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.getcode(), resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_01_unauthenticated_request_triggers_401_challenge(self):
        """1. Request without credentials returns 401 with WWW-Authenticate challenge header."""
        code, headers, _ = self._make_request("/")
        self.assertEqual(code, 401)
        auth_hdr = headers.get("WWW-Authenticate", "")
        self.assertIn('Basic realm="Outreach Agent"', auth_hdr)

    def test_02_invalid_credentials_denied_with_401(self):
        """2. Invalid credentials return 401 Unauthorized."""
        code, _, _ = self._make_request("/", auth_tuple=("testadmin", "wrongpassword"))
        self.assertEqual(code, 401)

        code, _, _ = self._make_request("/", auth_tuple=("wronguser", "testpass123!"))
        self.assertEqual(code, 401)

    def test_03_valid_credentials_succeed_for_ui_and_api(self):
        """3. Valid credentials return 200 OK for HTML, static assets, and API routes."""
        valid_auth = ("testadmin", "testpass123!")

        # Root HTML page
        code, _, body = self._make_request("/", auth_tuple=valid_auth)
        self.assertEqual(code, 200)
        self.assertIn(b"<!DOCTYPE html>", body)

        # Static assets
        code, headers, _ = self._make_request("/style.css", auth_tuple=valid_auth)
        self.assertEqual(code, 200)
        self.assertIn("text/css", headers.get("Content-Type", ""))

        code, headers, _ = self._make_request("/app.js", auth_tuple=valid_auth)
        self.assertEqual(code, 200)

        # API endpoint
        code, headers, body = self._make_request("/api/dashboard", auth_tuple=valid_auth)
        self.assertEqual(code, 200)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        self.assertIn(b"leads", body)

    def test_04_direct_api_call_without_credentials_rejected_401(self):
        """4. Direct API calls (GET and POST) without credentials return 401, not processed."""
        # Direct GET
        code, _, _ = self._make_request("/api/dashboard")
        self.assertEqual(code, 401)

        # Direct POST
        post_data = b'{"lead_id": "L001", "channel": "email"}'
        code, _, _ = self._make_request("/api/send-message", method="POST", data=post_data)
        self.assertEqual(code, 401)

        # Direct DB reset attempt
        code, _, _ = self._make_request("/api/reset-db", method="POST", data=b"{}")
        self.assertEqual(code, 401)

    def test_05_unset_credentials_fails_closed(self):
        """5. Unset AUTH_USERNAME/AUTH_PASSWORD fails closed — denies ALL access with 401."""
        os.environ["AUTH_USERNAME"] = ""
        os.environ["AUTH_PASSWORD"] = ""

        # Unauthenticated request -> 401
        code, _, _ = self._make_request("/")
        self.assertEqual(code, 401)

        # Even with credentials supplied -> 401 because server has no valid credentials configured
        code, _, _ = self._make_request("/", auth_tuple=("testadmin", "testpass123!"))
        self.assertEqual(code, 401)

        # API calls also fail closed -> 401
        code, _, _ = self._make_request("/api/dashboard")
        self.assertEqual(code, 401)

    def test_06_webhook_server_unaffected(self):
        """6. Confirm webhook_server.py is completely untouched by Basic Auth."""
        with open("webhook_server.py", "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("AUTH_USERNAME", content)
        self.assertNotIn("AUTH_PASSWORD", content)
        self.assertNotIn("_require_auth", content)
        self.assertNotIn("WWW-Authenticate", content)


if __name__ == "__main__":
    unittest.main()
