import base64
from collections.abc import Mapping, MutableMapping
from collections import OrderedDict
from dataclasses import dataclass
import gzip
import io
import json
import re
import subprocess
from typing import Tuple
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

    @property
    def ok(self):
        return not (400 < self.status_code < 600)

    def raise_for_status(self):
        if not self.ok:
            raise HTTPError(f"{self.status_code} Server Error", response=self)

    @property
    def _content(self):
        content = self.content
        if self.headers.get("content-encoding") == "gzip":
            with gzip.open(io.BytesIO(content)) as f:
                content = f.read()
        return content

    @property
    def text(self):
        # Todo: decode using appropriate charset from content type
        return self._content.decode()

    def json(self):
        return json.loads(self._content)


def _fixup_request_args(
    method: str,
    url: str,
    data: bytes | dict[str, str],
    headers: dict[str, str],
    cookies: dict[str, str],
    params: dict[str, str],
    clienthello: str,
) -> Tuple[str, str, bytes, dict[str, str], dict[str, str], dict[str, str], str]:
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
    method = method.upper()
    return method, url, data, headers, cookies, params, clienthello


def request(
    method,
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    clienthello: str = "",
):
    method, url, data, headers, cookies, params, clienthello = _fixup_request_args(
        method, url, data, headers, cookies, params, clienthello
    )
    result = subprocess.run(
        [
            "curlinate",
            "-X",
            method.upper(),
            url,
            *[f"-H{key}: {value}" for key, value in headers.items()],
            *(["--body", base64.b64encode(data), "--body-base64"] if data else []),
            *(["--clienthello", clienthello] if clienthello else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = result.stdout
    stderr = result.stderr.decode()
    if result.returncode != 0:
        error = (
            stderr.strip().splitlines()[-1].strip()
            or f"exit status {result.returncode}"
        )
        raise RuntimeError(f"got error from curlinate subprocess: {error}")
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
    clienthello: str = "",
):
    return request(
        "DELETE",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        clienthello=clienthello,
    )


def get(
    url,
    *,
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    clienthello: str = "",
):
    return request(
        "GET",
        url,
        headers=headers,
        cookies=cookies,
        params=params,
        clienthello=clienthello,
    )


def patch(
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    clienthello: str = "",
):
    return request(
        "PATCH",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        clienthello=clienthello,
    )


def post(
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    clienthello: str = "",
):
    return request(
        "POST",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        clienthello=clienthello,
    )


def put(
    url,
    *,
    data: (bytes | dict[str, str]) = b"",
    headers: dict[str, str] = {},
    cookies: dict[str, str] = {},
    params: dict[str, str] = {},
    clienthello: str = "",
):
    return request(
        "PUT",
        url,
        data=data,
        headers=headers,
        cookies=cookies,
        params=params,
        clienthello=clienthello,
    )


class Session:
    def __init__(self, clienthello: str | None = None):
        self.proc = subprocess.Popen(
            ["curlinate", "multiple"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.clienthello = clienthello or ""

    def __del__(self):
        assert self.proc.stdin
        self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.__del__()

    def request(
        self,
        method,
        url,
        *,
        data: (bytes | dict[str, str]) = b"",
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        params: dict[str, str] = {},
        clienthello: str = "",
    ):
        if not clienthello:
            clienthello = self.clienthello
        method, url, data, headers, cookies, params, clienthello = _fixup_request_args(
            method, url, data, headers, cookies, params, clienthello
        )
        assert self.proc.stdin
        assert self.proc.stdout
        assert self.proc.stderr
        self.proc.stdin.write(
            json.dumps(
                {
                    "url": url,
                    "method": method,
                    "headers": [f"{key}: {value}" for key, value in headers.items()],
                    **(
                        {"body": base64.b64encode(data).decode(), "body_base64": True}
                        if data
                        else {}
                    ),
                    "clienthello": clienthello,
                    "conn_id": "curlinate",
                }
            ).encode()
            + b"\n"
        )
        line = self.proc.stdout.readline()
        if not line:
            try:
                error = (
                    self.proc.stderr.read().decode().strip().splitlines()[-1].strip()
                    or "unknown error"
                )
            except Exception:
                error = "unknown error"
            raise RuntimeError(f"got error from curlinate subprocess: {error}")
        resp = json.loads(line)
        resp_headers = CaseInsensitiveDict()
        for header in resp["headers"]:
            key, value = header.split(": ", maxsplit=1)
            resp_headers[key] = value
        return Response(resp["status"], resp_headers, base64.b64decode(resp["body"]))

    def delete(
        self,
        url,
        *,
        data: (bytes | dict[str, str]) = b"",
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        params: dict[str, str] = {},
        clienthello: str = "",
    ):
        return self.request(
            "DELETE",
            url,
            data=data,
            headers=headers,
            cookies=cookies,
            params=params,
            clienthello=clienthello,
        )

    def get(
        self,
        url,
        *,
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        params: dict[str, str] = {},
        clienthello: str = "",
    ):
        return self.request(
            "GET",
            url,
            headers=headers,
            cookies=cookies,
            params=params,
            clienthello=clienthello,
        )

    def patch(
        self,
        url,
        *,
        data: (bytes | dict[str, str]) = b"",
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        params: dict[str, str] = {},
        clienthello: str = "",
    ):
        return self.request(
            "PATCH",
            url,
            data=data,
            headers=headers,
            cookies=cookies,
            params=params,
            clienthello=clienthello,
        )

    def post(
        self,
        url,
        *,
        data: (bytes | dict[str, str]) = b"",
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        params: dict[str, str] = {},
        clienthello: str = "",
    ):
        return self.request(
            "POST",
            url,
            data=data,
            headers=headers,
            cookies=cookies,
            params=params,
            clienthello=clienthello,
        )

    def put(
        self,
        url,
        *,
        data: (bytes | dict[str, str]) = b"",
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        params: dict[str, str] = {},
        clienthello: str = "",
    ):
        return self.request(
            "PUT",
            url,
            data=data,
            headers=headers,
            cookies=cookies,
            params=params,
            clienthello=clienthello,
        )
