# Curlinate

This is a command-line utility and Python library to simplify TLS
fingerprint forgery.

As you may know, TLS fingerprinting is a common defense against
third-party integration with or reverse engineering of a web service.
By monitoring the behavior of the client's TLS implementation, it is
possible to distinguish between different clients. This is essentially
the same as user-agent sniffing, but since TLS fingerprinting is a
more recent development, tools for forgery are not yet as widely
available.

Curlinate offers no technical innovation, simply convenience. I
developed it because I found that existing forgery tools were clumsy
and hard to use. I wanted something that would require no custom code
to integrate into an application: just call it like `curl` or Python
`requests`, and provide the TLS fingerprint to forge as a parameter.

## Status

This is a hack that works well enough for me. Your mileage may vary. I
implemented this as a standalone project because I found that I needed
it as a dependency for multiple unrelated reverse engineering efforts,
and wanted to avoid maintaining duplicate code.

If this project proves useful for the community, I will be happy to
make it more production ready.

## Installation

Curlinate consists of two components: a command-line utility written
in Go, and a Python library which wraps it (optional). If you install
the Python library, it will automatically compile and install the
command-line utility as part of the package. Otherwise, you can
compile and install the command-line utility to your location of
choice. At this time precompiled binaries are not available.

To wit: either `go build .` to compile the command-line utility
`curlinate`, or `pip3 install .` to install the Python package, which
will also compile and install the `curlinate` binary.

You need Go to compile the binary, and you need Python/Pip if you
elect to install the Python package. There are no other dependencies.

## Usage

First, obtain the TLS ClientHello packet whose fingerprint you would
like to forge. The most straightforward way to do this is to monitor
your network traffic with Wireshark and identify the appropriate
packet by IP address. If you are reverse engineering a mobile
application then one option is to use
[Wireguard](https://www.wireguard.com/) to force device traffic to be
forwarded through your laptop acting as a router. In any case, copy
the raw ClientHello packet contents and convert the binary to base64
format. This is the input to Curlinate which tells it the fingerprint
you wish to spoof. Note that Curlinate will not send the exact same
ClientHello; instead, it will use
[utls](https://github.com/refraction-networking/utls) to synthesize a
new packet appropriate to the connection your application is making,
but with the same fingerprint.

### Command-line utility

A subset of curl syntax is provided:

```
% curlinate https://...
    [--clienthello "some raw packet in base64"]
    [-X, --method METHOD]
    [-H, --header "Your-Header: Some value"]...
    [--body "raw request body"]
    [--body-base64]
```

If you do not provide `--clienthello` then a default TLS fingerprint
is used (no guarantee is made about which one). You can also specify
this parameter using the environment variable `CLIENTHELLO` (same
base64 format) if that is easier.

As with curl, the method defaults to GET. If you provide a request
body then this does not automatically change the method to POST,
unlike curl.

Request bodies must be provided using `--body`. There is no support at
present for reading from stdin. If you want to send a binary request
body (i.e., something that has null bytes or doesn't form valid
UTF-8), then you should base64-encode it for `--body` and add
`--body-base64`.

The validation for `-H` is more strict than in curl; the colon and
following space are both required.

Generally speaking, assume `curlinate` is not as featureful as curl so
you should not be surprised if a feature is missing or limited.

### Output format

The response body is printed to stdout. No post-processing is done.

Informational data in the following format is printed on stderr:

```
status 200
header Content-Type: text/html
header ...
body 277 bytes
```

In the case of any other data being printed on stderr, it will be a
fatal error and a non-zero exit status will be returned.

### Multiple requests

Some use cases require reusing the same TCP connection for multiple
requests. This is supported by the command-line tool albeit in a more
awkward manner. Pass a single argument `multiple` to start Curlinate
in multi-request mode. In this mode you submit requests as single-line
JSON messages to stdin, and get the results back in the same format on
stdout. The normal output format described above is not used.
Concurrent requests are not supported, but you can have concurrent
connections open simultaneously.

In multi-request mode, you have access to the same options but they
are passed as JSON keys instead of command-line arguments:

* `https://...` becomes `"url": "https://..."`
* `--clienthello "some raw packet in base64"` becomes `"clienthello":
  "some raw packet in base64"`
* `-X, --method METHOD` becomes `"method": "METHOD"`
* `-H, --header "Your-Header: Some value"...` becomes `"headers":
  ["Your-Header: Some values", ...]`
* `--body "raw request body"` becomes `"body": "raw request body"`
* `--body-base64` becomes `"body_base64": true`

In multi-request mode there is a new option supported as well, the
`conn_id` key. This is an optional string. When it is omitted the
behavior is as normal. With `conn_id` as a non-empty string, the
connection is left open after the request completes, and if you submit
a following request with the same value for `conn_id`, then it will
reuse the same connection. (You must ensure that the connection can be
reused for the subsequent request, so for example it must be a request
to the same host.)

```json
{"url":"https://www.google.com","clienthello":"..."}
```

The response JSON has the keys `status` (integer), `headers` (array of
strings, `Key: value`), and `body_base64`.

### Python interface

The Python package exposes a similar interface to that of
[Requests](https://docs.python-requests.org/en/latest/index.html),
although Requests is not a dependency. So:

```python
import curlinate

resp = curlinate.post("https://httpbin.org/post", headers={
  "X-Foobar": "Quux",
}, cookies={
  "auth-token": "l3tm3in",
  "goog-random-personal-data-for-the-hivemind": "...",
}, params={
  "q": "some query parameter",
}, data="some nonsense for the body", clienthello="...")
print(resp.status_code, resp.headers, resp.content)
```

The interface is minimal, so only the keyword arguments and attributes
shown above are supported at present (along with the other common http
request verbs, and the generic `request` method that takes a `method`
argument). The only addition to the Requests interface is the
`clienthello` option (you can also use the `CLIENTHELLO` environment
variable as a default).

The implementation is just invoking the command-line utility in a
subprocess and parsing the output. It is impossible to make the
request from pure Python because the standard library does not offer
sufficient control over the network stack.

You can also reuse connections with the Session interface, note
however that other features of Session from Requests (such as tracking
cookies) are not supported and you must do this manually:

```python
import curlinate

with curlinate.Session() as s:
    resp1 = s.get("https://httpbin.org/get")
    resp2 = s.post("https://httpbin.org/post")
```

As a convenience you can pass a `clienthello` argument to the
`Session` constructor; this will be used as a default for calls on
that session. Note that there is no support for intelligent connection
pooling; unlike with Requests, all requests submitted in the same
`Session` *must* be routable on the same TCP connection. In addition,
`Session` objects do not handle cookie management or other state; they
are solely a way to expose the ability to force multiple requests to
use the same connection in case this is required for an application.
Cookies can still be handled manually.

## Thanks to

* [ja3transport](https://github.com/CUCyber/ja3transport), used in the
  original implementation although I since moved away from JA3 due to
  limitations
* [utls](https://github.com/refraction-networking/utls), powers all of
  the actual complexity with regard to TLS
* [kong](https://github.com/alecthomas/kong), command-line argument
  parsing

## Legal note

No comment is made on the legality of any particular use case of this
code. Please consult your legal team.

What I will say is that reverse engineering is certainly ethical and
pro-democratic, and from a moral standpoint should be encouraged
wherever possible, because it acts as a necessary counterweight to the
otherwise rampant and unchecked violations of privacy and consumer
rights by Silicon Valley megacorporations.
