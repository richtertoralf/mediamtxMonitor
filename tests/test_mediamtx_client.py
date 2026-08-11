import unittest
from unittest import mock

import requests

from bin.mediamtx_client import (
    DEFAULT_TIMEOUT_SECONDS,
    MediaMTXClient,
    MediaMTXDecodeError,
    MediaMTXHTTPError,
    MediaMTXRequestError,
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200, json_error=None):
        self.payload = payload
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class MediaMTXClientTests(unittest.TestCase):
    def test_get_json_uses_base_url_endpoint_params_and_default_timeout(self):
        session = FakeSession(FakeResponse({"items": []}))
        client = MediaMTXClient("http://localhost:9997/", session=session)

        result = client.get_json("/v3/paths/forward/list", {"path": "camera/main"})

        self.assertEqual(result, {"items": []})
        self.assertEqual(
            session.calls,
            [
                (
                    "http://localhost:9997/v3/paths/forward/list",
                    {"path": "camera/main"},
                    DEFAULT_TIMEOUT_SECONDS,
                )
            ],
        )

    def test_custom_timeout_is_applied(self):
        session = FakeSession(FakeResponse({"version": "1.20.0"}))
        client = MediaMTXClient(
            "http://media.example:9997", timeout=1.5, session=session
        )

        client.get_json("v3/info")

        self.assertEqual(session.calls[0][2], 1.5)

    def test_http_error_exposes_status_for_optional_endpoint_decision(self):
        client = MediaMTXClient(
            "http://localhost:9997", session=FakeSession(FakeResponse(status_code=404))
        )

        with self.assertRaises(MediaMTXHTTPError) as raised:
            client.get_json("/v3/rtspsconns/list")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(
            raised.exception.url,
            "http://localhost:9997/v3/rtspsconns/list",
        )

    def test_transport_error_is_translated(self):
        client = MediaMTXClient(
            "http://localhost:9997",
            session=FakeSession(error=requests.Timeout("too slow")),
        )

        with self.assertRaises(MediaMTXRequestError):
            client.get_json("/v3/info")

    def test_invalid_json_is_translated(self):
        client = MediaMTXClient(
            "http://localhost:9997",
            session=FakeSession(FakeResponse(json_error=ValueError("invalid"))),
        )

        with self.assertRaises(MediaMTXDecodeError):
            client.get_json("/v3/info")


class CollectorClientBoundaryTests(unittest.TestCase):
    def test_optional_secure_endpoint_404_is_silently_treated_as_empty(self):
        import bin.mediamtx_collector as collector

        client = mock.Mock()
        client.build_url.return_value = (
            "http://localhost:9997/v3/rtspsconns/list"
        )
        client.get_json.side_effect = MediaMTXHTTPError(
            "http://localhost:9997/v3/rtspsconns/list", 404
        )

        with (
            mock.patch.object(collector, "mediamtx_client", client),
            mock.patch.object(collector.logging, "warning") as warning,
        ):
            result = collector.fetch("/v3/rtspsconns/list")

        self.assertEqual(result, {"items": []})
        warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
