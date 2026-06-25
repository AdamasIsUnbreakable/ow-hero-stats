import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from overwatch_stats.fandom_client import FandomApiError, FandomClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.headers = {}
        self.calls = 0

    def get(self, *args, **kwargs):
        payload = self.payloads.pop(0)
        self.calls += 1
        return FakeResponse(payload)


class FandomClientTests(unittest.TestCase):
    def test_rate_limit_response_is_retried(self):
        with TemporaryDirectory() as cache_dir:
            client = FandomClient(cache_dir=cache_dir, max_retries=2, retry_delay=0)
            client.session = FakeSession(
                [
                    {"error": {"code": "ratelimited", "info": "You've exceeded your rate limit."}},
                    {"cargoquery": [{"title": {"Name": "Ashe"}}]},
                ]
            )

            with patch("overwatch_stats.fandom_client.time.sleep"):
                rows = client.cargo_query(tables="Characters", fields="Name")

            self.assertEqual(rows, [{"Name": "Ashe"}])
            self.assertEqual(client.session.calls, 2)

    def test_non_retryable_api_error_is_raised(self):
        with TemporaryDirectory() as cache_dir:
            client = FandomClient(cache_dir=cache_dir, max_retries=2, retry_delay=0)
            client.session = FakeSession(
                [
                    {"error": {"code": "badvalue", "info": "Bad Cargo query."}},
                ]
            )

            with self.assertRaises(FandomApiError):
                client.cargo_query(tables="Characters", fields="Name")


if __name__ == "__main__":
    unittest.main()
