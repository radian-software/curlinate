package main

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"

	"github.com/alecthomas/kong"
	"github.com/refraction-networking/utls"
	"golang.org/x/net/http2"
)

type argsType struct {
	URL         string   `arg:"" help:"Fully qualified URL to contact" required:"" json:"url"`
	Method      string   `short:"X" name:"method" help:"HTTP method to use" default:"GET" json:"method"`
	Headers     []string `sep:"none" short:"H" name:"header" help:"Additional http headers in format 'Header: Value'" json:"headers"`
	Body        string   `name:"body" help:"Request body, must be UTF-8 due to limitation in argument parser" json:"body"`
	BodyBase64  bool     `name:"body-base64" help:"Assume request body is base64 encoded, so null bytes can be used" json:"body_base64"`
	ClientHello string   `name:"clienthello" help:"Base64 encoded raw ClientHello message to emulate" env:"CLIENTHELLO" json:"clienthello"`
	ConnId      string   `kong:"-" json:"conn_id"`
	multiple    bool
	useJson     bool
}

type sessionResp struct {
	Status  int      `json:"status"`
	Headers []string `json:"headers"`
	Body    []byte   `json:"body"`
}

func getMapKeys(m map[string]string) []string {
	keys := []string{}
	for key := range m {
		keys = append(keys, key)
	}
	return keys
}

var savedConns = map[string]*tls.UConn{}

func mainE(args *argsType) error {
	// First check if we are in session mode, if so, read new args
	// from stdin and recurse.
	if args.multiple {
		fmt.Fprintln(os.Stderr, "ignoring args and reading commands from stdin")
		scanner := bufio.NewScanner(os.Stdin)
		for scanner.Scan() {
			subargs := argsType{}
			err := json.Unmarshal(scanner.Bytes(), &subargs)
			if err != nil {
				return err
			}
			subargs.useJson = true
			err = mainE(&subargs)
			if err != nil {
				return err
			}
		}
		return nil
	}
	// Need to validate args again because it is possible to
	// bypass the cmdline validation in session mode
	if args.URL == "" {
		return errors.New("url is required")
	}
	// Kong doesn't seem to want to read bytes as base64 like
	// json, so we have to do it manually
	if args.ClientHello == "" {
		args.ClientHello = os.Getenv("CLIENTHELLO")
	}
	clienthello := []byte{}
	if args.ClientHello != "" {
		encoder := base64.NewDecoder(base64.StdEncoding, bytes.NewReader([]byte(os.Getenv("CLIENTHELLO"))))
		var err error
		clienthello, err = io.ReadAll(encoder)
		if err != nil {
			return err
		}
	}
	// Proceed to main logic
	parsedURL, err := url.Parse(args.URL)
	if err != nil {
		return err
	}
	// Parse the headers into a map
	parsedHeaders := http.Header{}
	for _, header := range args.Headers {
		splits := strings.SplitN(header, ": ", 2)
		if len(splits) != 2 {
			return fmt.Errorf("bad header format: %v", header)
		}
		key := splits[0]
		value := splits[1]
		parsedHeaders.Add(key, value)
	}
	if err != nil {
		return err
	}
	// Parse the body into a byte array
	parsedBody := []byte(args.Body)
	if args.BodyBase64 {
		encoder := base64.NewDecoder(base64.StdEncoding, bytes.NewReader(parsedBody))
		parsedBody, err = io.ReadAll(encoder)
		if err != nil {
			return err
		}
	}
	var tlsConn *tls.UConn = nil
	if args.ConnId != "" {
		tlsConn = savedConns[args.ConnId]
	}
	if tlsConn == nil {
		var tlsId tls.ClientHelloID
		var tlsSpec *tls.ClientHelloSpec
		if len(clienthello) > 0 {
			tlsId = tls.HelloCustom
			tlsFingerprinter := &tls.Fingerprinter{}
			tlsSpec, err = tlsFingerprinter.FingerprintClientHello(clienthello)
			if err != nil {
				return err
			}
		} else {
			tlsId = tls.HelloFirefox_56
			tlsSpec = nil
		}
		if parsedURL.Scheme != "https" {
			return fmt.Errorf("unsupported scheme %s, only https is allowed", parsedURL.Scheme)
		}
		host := parsedURL.Host
		if !strings.Contains(host, ":") {
			host += ":443"
		}
		tcpConn, err := net.Dial("tcp", host)
		if err != nil {
			return err
		}
		tlsConfig := tls.Config{ServerName: parsedURL.Hostname()}
		tlsConn = tls.UClient(tcpConn, &tlsConfig, tlsId)
		if tlsSpec != nil {
			err = tlsConn.ApplyPreset(tlsSpec)
			if err != nil {
				return err
			}
		}
		err = tlsConn.Handshake()
		if err != nil {
			return err
		}
		if args.ConnId == "" {
			defer tlsConn.Close()
		} else {
			savedConns[args.ConnId] = tlsConn
		}
	}
	req := &http.Request{
		Method: args.Method,
		URL:    parsedURL,
		Header: parsedHeaders,
		Body:   io.NopCloser(bytes.NewReader(parsedBody)),
	}
	var resp *http.Response
	alpn := tlsConn.HandshakeState.ServerHello.AlpnProtocol
	switch alpn {
	case "h2":
		req.Proto = "HTTP/2.0"
		req.ProtoMajor = 2
		req.ProtoMinor = 0

		tr := http2.Transport{}
		clientConn, err := tr.NewClientConn(tlsConn)
		if err != nil {
			return err
		}
		resp, err = clientConn.RoundTrip(req)
		if err != nil {
			return err
		}
	case "http/1.1", "":
		req.Proto = "HTTP/1.1"
		req.ProtoMajor = 1
		req.ProtoMinor = 1
		err := req.Write(tlsConn)
		if err != nil {
			return err
		}
		resp, err = http.ReadResponse(bufio.NewReader(tlsConn), req)
		if err != nil {
			return err
		}
	default:
		return fmt.Errorf("unexpected ALPN: %s", alpn)
	}
	if !args.useJson {
		fmt.Fprintf(os.Stderr, "status %s\n", resp.Status)
		for key, vals := range resp.Header {
			for _, val := range vals {
				fmt.Fprintf(os.Stderr, "header %s: %s\n", key, val)
			}
		}
	}
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if !args.useJson {
		fmt.Fprintf(os.Stderr, "body %d bytes\n", len(respBody))
		fmt.Printf("%s", respBody)
	} else {
		headers := []string{}
		for key, vals := range resp.Header {
			for _, val := range vals {
				headers = append(headers, fmt.Sprintf("%s: %s", key, val))
			}
		}
		msg, err := json.Marshal(sessionResp{
			Status:  resp.StatusCode,
			Headers: headers,
			Body:    respBody,
		})
		if err != nil {
			return err
		}
		fmt.Println(string(msg))
	}
	return nil
}

func main() {
	args := argsType{}
	if len(os.Args) == 2 && os.Args[1] == "multiple" {
		args.multiple = true
	} else {
		kong.Parse(&args)
	}
	err := mainE(&args)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fatal: %s\n", err.Error())
		os.Exit(1)
	}
}
