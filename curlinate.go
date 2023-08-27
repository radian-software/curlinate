package main

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"

	"github.com/CUCyber/ja3transport"
	"github.com/alecthomas/kong"
)

var presets = map[string]string{
	"chrome_78":    "769,47-53-5-10-49161-49162-49171-49172-50-56-19-4,0-10-11,23-24-25,0",
	"safari_604_1": "771,4865-4866-4867-49196-49195-49188-49187-49162-49161-52393-49200-49199-49192-49191-49172-49171-52392-157-156-61-60-53-47-49160-49170-10,65281-0-23-13-5-18-16-11-51-45-43-10-21,29-23-24-25,0",
}

type argsType struct {
	URL        string   `arg:"" help:"Fully qualified URL to contact" required:"" json:"url"`
	Method     string   `short:"X" name:"method" help:"HTTP method to use" default:"GET" json:"method"`
	Headers    []string `sep:"none" short:"H" name:"header" help:"Additional http headers in format 'Header: Value'" json:"headers"`
	Body       string   `name:"body" help:"Request body, must be UTF-8 due to limitation in argument parser" json:"body"`
	BodyBase64 bool     `name:"body-base64" help:"Assume request body is base64 encoded, so null bytes can be used" json:"body_base64"`
	JA3        string   `name:"ja3" help:"Raw JA3 fingerprint to forge, or name of existing preset" env:"JA3" required:"" json:"ja3"`
	multiple   bool
	useJson    bool
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

func isValidJA3(ja3 string) bool {
	parts := strings.Split(ja3, ",")
	if len(parts) != 5 {
		return false
	}
	for _, part := range parts {
		subparts := strings.Split(part, "-")
		for _, subpart := range subparts {
			if _, err := strconv.Atoi(subpart); err != nil {
				return false
			}
		}
	}
	return true
}

var savedClients = map[string]*ja3transport.JA3Client{}

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
	if args.JA3 == "" {
		args.JA3 = os.Getenv("JA3")
		if args.JA3 == "" {
			return errors.New("ja3 is required")
		}
	}
	// Proceed to main logic
	parsedURL, err := url.Parse(args.URL)
	if err != nil {
		return err
	}
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
	parsedBody := []byte(args.Body)
	if args.BodyBase64 {
		encoder := base64.NewDecoder(base64.StdEncoding, bytes.NewReader(parsedBody))
		parsedBody, err = io.ReadAll(encoder)
		if err != nil {
			return err
		}
	}
	req := http.Request{
		Method: args.Method,
		URL:    parsedURL,
		Header: parsedHeaders,
		Body:   io.NopCloser(bytes.NewReader(parsedBody)),
	}
	if ja3, ok := presets[args.JA3]; ok {
		args.JA3 = ja3
	} else if !isValidJA3(args.JA3) {
		return fmt.Errorf("not a valid JA3 string or a known preset: %s (valid presets: %s)", args.JA3, strings.Join(getMapKeys(presets), ", "))
	}
	client, ok := savedClients[args.JA3]
	if !ok {
		client, err = ja3transport.NewWithString(args.JA3)
		if err != nil {
			return err
		}
		savedClients[args.JA3] = client
	}
	resp, err := client.Do(&req)
	if err != nil {
		return err
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
