from datetime import datetime, timedelta
from typing import Optional
from unittest import TestCase

import httpx
import pytest
import requests

from kognic.auth._sunset import DATETIME_FMT, handle_sunset

SUNSET_HEADER = "sunset-date"


def date_to_str(date: datetime):
    return date.strftime(DATETIME_FMT)


SUNSET_DATE_LONG_TIME_AGO = "2024-02-22T16:21:20.880547Z"  # => error
SUNSET_DATE_5_DAYS_AGO = date_to_str(datetime.now())  # now => error
SUNSET_DATE_IN_13_DAYS = date_to_str(datetime.now() + timedelta(days=13))  # in 13 days => error
SUNSET_DATE_IN_15_DAYS = date_to_str(datetime.now() + timedelta(days=15))  # in 15 days => warning
SUNSET_DATE_WRONG_FORMAT = "2024-02-22T16:21:20Z"  # => error

url = "https://example.com/endpoint?key=1"


def make_requests_response(sunset_date: Optional[str]) -> requests.Response:
    response = requests.Response()
    if sunset_date:
        response.headers[SUNSET_HEADER] = sunset_date
    response.request = requests.Request("GET", url)
    return response


def make_httpx_response(sunset_date: Optional[str]) -> httpx.Response:
    headers = {SUNSET_HEADER: sunset_date} if sunset_date else None
    return httpx.Response(status_code=200, headers=headers, request=httpx.Request("GET", url))


def run_test_with_response(caplog, response, expected_log_level: Optional[str]):
    handle_sunset(response)
    if expected_log_level:
        log_record = caplog.records[0]
        assert log_record.levelname == expected_log_level
        assert "Endpoint has been deprecated and will be removed at" in log_record.message
        assert log_record.message.endswith(f"Endpoint: GET {str(response.request.url).split('?')[0]}")


class TestSunsetDateRequests(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_when_sunset_date_not_set(self):
        response = make_requests_response(None)
        run_test_with_response(self._caplog, response, None)

    def test_when_sunset_date_invalid(self):
        response = make_requests_response(SUNSET_DATE_WRONG_FORMAT)
        run_test_with_response(self._caplog, response, None)

    def test_when_sunset_date_long_time_ago(self):
        response = make_requests_response(SUNSET_DATE_LONG_TIME_AGO)
        run_test_with_response(self._caplog, response, "ERROR")

    def test_when_sunset_date_5_days_ago(self):
        response = make_requests_response(SUNSET_DATE_5_DAYS_AGO)
        run_test_with_response(self._caplog, response, "ERROR")

    def test_when_sunset_date_in_13_days(self):
        response = make_requests_response(SUNSET_DATE_IN_13_DAYS)
        run_test_with_response(self._caplog, response, "ERROR")

    def test_when_sunset_date_in_15_days(self):
        response = make_requests_response(SUNSET_DATE_IN_15_DAYS)
        run_test_with_response(self._caplog, response, "WARNING")


class TestSunsetDateHttpx(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_when_sunset_date_not_set(self):
        response = make_httpx_response(None)
        run_test_with_response(self._caplog, response, None)

    def test_when_sunset_date_invalid(self):
        response = make_httpx_response(SUNSET_DATE_WRONG_FORMAT)
        run_test_with_response(self._caplog, response, None)

    def test_when_sunset_date_long_time_ago(self):
        response = make_httpx_response(SUNSET_DATE_LONG_TIME_AGO)
        run_test_with_response(self._caplog, response, "ERROR")

    def test_when_sunset_date_5_days_ago(self):
        response = make_httpx_response(SUNSET_DATE_5_DAYS_AGO)
        run_test_with_response(self._caplog, response, "ERROR")

    def test_when_sunset_date_in_13_days(self):
        response = make_httpx_response(SUNSET_DATE_IN_13_DAYS)
        run_test_with_response(self._caplog, response, "ERROR")

    def test_when_sunset_date_in_15_days(self):
        response = make_httpx_response(SUNSET_DATE_IN_15_DAYS)
        run_test_with_response(self._caplog, response, "WARNING")
