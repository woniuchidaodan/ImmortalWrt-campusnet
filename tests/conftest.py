"""测试公共夹具：一个假的 HTTP 会话，用来断言「我们到底发了什么请求」。

这类工具最容易出错的地方不是加密，而是**请求拼错**（字段名、端口、顺序）。
所以单元测试的重点放在"请求长什么样"，而不是端到端打真服务器。
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campusnet.providers.base import DetectContext  # noqa: E402
from campusnet.session import Response  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as fh:
        return fh.read()


def make_response(body: str = "", status: int = 200, headers: dict = None, url: str = "") -> Response:
    return Response(
        status=status,
        headers=headers or {},
        body=body.encode("utf-8"),
        url=url,
    )


class FakeSession:
    """按 URL 子串匹配返回值，并记录所有请求。"""

    def __init__(self, routes=None, default: Response = None) -> None:
        self.routes = list(routes or [])
        self.default = default or make_response("", status=404)
        self.calls = []

    # --- 用于断言
    @property
    def urls(self):
        return [call[1] for call in self.calls]

    def last(self, method: str = None):
        for call in reversed(self.calls):
            if method is None or call[0] == method:
                return call
        return None

    def find(self, needle: str):
        for call in self.calls:
            if needle in call[1]:
                return call
        return None

    # --- Session 接口
    def _resolve(self, url: str) -> Response:
        for matcher, response in self.routes:
            if callable(matcher):
                if matcher(url):
                    return response
            elif matcher in url:
                return response
        return self.default

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, None))
        return self._resolve(url)

    def post(self, url, data=None, **kwargs):
        self.calls.append(("POST", url, data))
        return self._resolve(url)

    def request(self, url, method="GET", data=None, **kwargs):
        self.calls.append((method.upper(), url, data))
        return self._resolve(url)


@pytest.fixture
def drcom_page() -> str:
    return fixture("drcom_login_page.html")


@pytest.fixture
def ctx_drcom(drcom_page) -> DetectContext:
    return DetectContext(
        url="http://10.20.30.1/",
        text=drcom_page,
        headers={"server": "DrcomServer1.0"},
    )
