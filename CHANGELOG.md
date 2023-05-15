# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.0.1

Initial version. Offers Go binary and Python package (which compiles
and installs the Go binary by default).

The Go binary has arguments/options:

* `<url>` (required)
* `-X, --method`
* `-H, --header`
* `--body`
* `--body-base64`
* `--ja3` (required)

The Python package has methods:

* `request`
* `delete`
* `get`
* `patch`
* `post`
* `put`

They support arguments/options (where appropriate):

* `method`
* `url`
* `data`
* `headers`
* `cookies`
* `params`

They return a response dataclass with fields:

* `status_code`
* `headers`
* `content`
