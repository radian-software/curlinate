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
and hard to use (e.g.: no command-line usage, no Python library, no
support for JA3).

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

First, obtain the
[JA3](https://engineering.salesforce.com/tls-fingerprinting-with-ja3-and-ja3s-247362855967/)
string of the client whose TLS fingerprint you would like to forge.
There are several options. You can obtain a fingerprint from an
existing application or from a public database, or you can record your
own by capturing network packets with e.g. Wireshark and extracting
JA3 strings with e.g.
[pyJA3](https://github.com/salesforce/ja3/tree/master/python).

Some predefined JA3 strings are included built in Curlinate for
convenience. Instead of your own JA3 string, you can provide one of
these shorthands to use a built-in JA3:

* `chrome_78`
  (`769,47-53-5-10-49161-49162-49171-49172-50-56-19-4,0-10-11,23-24-25,0`)
* `safari_604_1`
  (`771,4865-4866-4867-49196-49195-49188-49187-49162-49161-52393-49200-49199-49192-49191-49172-49171-52392-157-156-61-60-53-47-49160-49170-10,65281-0-23-13-5-18-16-11-51-45-43-10-21,29-23-24-25,0`)

### Command-line utility

A subset of curl syntax is provided:

```
% curlinate https://...
    [--ja3 fingerprint-or-shorthand]
    [-X METHOD]
    [-H "Your-Header: Some value"]...
    [--body "raw request body"]
    [--body-base64]
```

Providing `--ja3` is required; there is no default. You can also
specify this option using the environment variable `JA3` instead, if
that is easier.

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

Generally speaking, assume `curlinate` is not as good as curl.

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
}, data="some nonsense for the body")
print(resp.status_code, resp.headers, resp.content)
```

The interface is minimal, so only the keyword arguments and attributes
are supported at present (along with the other common http request
verbs, and the generic `request` method that takes a `method`
argument).

The implementation is just invoking the command-line utility in a
subprocess and parsing the output. It is impossible to make the
request from pure Python because the standard library does not offer
sufficient control over the network stack.

## Thanks to

* [ja3transport](https://github.com/CUCyber/ja3transport), implements
  the actual logic of parsing JA3 strings and creating http requests
  to their specifications
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
