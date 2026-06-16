"""Tests for shared route request parsing helpers."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from zhihu_fiction.app.request_parsing import json_body, require_stripped, stripped_or_none


def test_require_stripped_returns_trimmed_string():
    body = {"run_id": "  run_1  "}

    assert require_stripped(body, "run_id") == "run_1"


@pytest.mark.parametrize("body", [{}, {"run_id": ""}, {"run_id": "   "}, {"run_id": None}])
def test_require_stripped_rejects_missing_or_blank_values(body):
    with pytest.raises(HTTPException) as exc_info:
        require_stripped(body, "run_id")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "run_id is required"


def test_stripped_or_none_returns_none_for_blank_values():
    assert stripped_or_none({"topic": "  测试主题 "}, "topic") == "测试主题"
    assert stripped_or_none({"topic": "   "}, "topic") is None
    assert stripped_or_none({}, "topic") is None


def test_json_body_returns_empty_dict_for_non_json_content_type():
    class Request:
        headers = {"content-type": "text/plain"}

        async def json(self):
            raise AssertionError("json() should not be called")

    import asyncio

    assert asyncio.run(json_body(Request())) == {}


def test_json_body_reads_json_content_type_with_charset():
    class Request:
        headers = {"content-type": "application/json; charset=utf-8"}

        async def json(self):
            return {"ok": True}

    import asyncio

    assert asyncio.run(json_body(Request())) == {"ok": True}
