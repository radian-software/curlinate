import base64
from collections.abc import Mapping, MutableMapping
from collections import OrderedDict
from dataclasses import dataclass
import os
import re
import subprocess
import urllib.parse


# Cribbed from requests
class CaseInsensitiveDict(MutableMapping):
    def __init__(self, data=None, **kwargs):
        self._store = OrderedDict()
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key, value):
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, _ in self._store.values())

    def __len__(self):
        return len(self._store)

    def lower_items(self):
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other):
        if isinstance(other, Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        return dict(self.lower_items()) == dict(other.lower_items())

    def copy(self):
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self):
        return str(dict(self.items()))


class HTTPError(Exception):
    def __init__(self, msg, response):
        super().__init__(msg)
        self.response = response


@dataclass
class Response:
    status_code: int
    headers: CaseInsensitiveDict
    content: bytes

    def raise_for_status(self):
        if 400 < self.status_code < 600:
            raise HTTPError(f"{self.status_code} Server Error", response=self)

    @property
    def text(self):
        # Todo: decode using appropriate content type from response
        return self.content.decode()


def request(
    method,
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    ja3: str = "",
):
    if not (ja3 or os.environ.get("JA3")):
        raise RuntimeError(
            "need to specify ja3 keyword argument or set JA3 environment variable"
        )
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
        if not CaseInsensitiveDict(headers).get("content-type"):
            headers = {
                **headers,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            }
    if cookies:
        if CaseInsensitiveDict(headers).get("cookie"):
            raise RuntimeError(
                "can't use extra cookies with request that already has cookie header"
            )
        headers = {
            **headers,
            "Cookie": "; ".join(f"{key}={val}" for key, val in cookies.items()),
        }
    if params:
        if "?" in url:
            raise RuntimeError(
                "can't use extra query params with url that already has query string"
            )
        url += "?" + urllib.parse.urlencode(params)
    result = subprocess.run(
        [
            "curlinate",
            "-X",
            method.upper(),
            url,
            *[f"-H{key}: {value}" for key, value in headers.items()],
            *(["--body", base64.b64encode(data), "--body-base64"] if data else []),
            *(["--ja3", ja3] if ja3 else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = result.stdout
    stderr = result.stderr.decode()
    status_code_match = re.search(r"(?m)^status ([0-9]+)", stderr)
    try:
        if not status_code_match:
            raise ValueError
        status_code = int(status_code_match.group(1))
    except (AttributeError, ValueError) as _:
        raise RuntimeError(
            f"unable to parse output from curlinate subprocess: {repr(stderr)}"
        ) from None
    resp_headers = CaseInsensitiveDict()
    for key, value in re.findall(r"(?m)^header ([^:]+): (.+)", stderr):
        resp_headers[key] = value
    return Response(status_code, resp_headers, stdout)


def delete(
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    ja3: str = "",
):
    return request(
        "DELETE",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        ja3=ja3,
    )


def get(
    url,
    *,
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    ja3: str = "",
):
    return request(
        "GET",
        url,
        headers=headers,
        cookies=cookies,
        params=params,
        ja3=ja3,
    )


def patch(
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    ja3: str = "",
):
    return request(
        "PATCH",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        ja3=ja3,
    )


def post(
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    ja3: str = "",
):
    return request(
        "POST",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        ja3=ja3,
    )


def put(
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    ja3: str = "",
):
    return request(
        "PUT",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        ja3=ja3,
    )
