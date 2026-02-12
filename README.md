# Kognic Authentication

Python 3 library providing foundations for Kognic Authentication
on top of the `requests` or `httpx` libraries.

Install with `pip install kognic-auth[requests]` or `pip install kognic-auth[httpx]`

Builds on the standard OAuth 2.0 Client Credentials flow. There are a few ways to provide auth credentials to our api
 clients. Kognic Python clients such as in `kognic-io` accept an `auth` parameter that
  can be set explicitly or you can omit it and use environment variables.

There are a few ways to set your credentials in `auth`.
1. Set the environment variable `KOGNIC_CREDENTIALS` to point to your Api Credentials file.
The credentials will contain the Client Id and Client Secret.
2. Set to the credentials file path like `auth="~/.config/kognic/credentials.json"`
3. Set environment variables `KOGNIC_CLIENT_ID` and`KOGNIC_CLIENT_SECRET`
4. Set to credentials tuple `auth=(client_id, client_secret)`

API clients such as the `InputApiClient` accept this `auth` parameter.

Under the hood, they commonly use the AuthSession class which is implements a `requests` session with automatic token
 refresh. An `httpx` implementation is also available.
```python
from kognic.auth.requests.auth_session import RequestsAuthSession

sess = RequestsAuthSession()

# make call to some Kognic service with your token. Use default requests
sess.get("https://api.app.kognic.com")
```

## CLI (Experimental)

The package provides a command-line interface for generating access tokens and making authenticated API calls.
This is great for LLM use cases, the `kognic-auth call` is a lightweight curl, that hides any complexity of authentication and context management,
so you can just focus on the API call you want to make. This also avoids tokens being leaked to the shell history,
as you can use named contexts and config files to manage your credentials.

The interface is currently marked experimental, and breaking changes may be made without a major version bump. Feedback is welcome to help stabilize the design.

### Configuration file

The CLI can be configured with a JSON file at `~/.config/kognic/config.json`. This lets you define named contexts for different environments, each with its own host, auth server, and credentials.

```json
{
  "default_context": "production",
  "contexts": {
    "production": {
      "host": "app.kognic.com",
      "auth_server": "https://auth.app.kognic.com",
      "credentials": "~/.config/kognic/credentials-prod.json"
    },
    "demo": {
      "host": "demo.kognic.com",
      "auth_server": "https://auth.demo.kognic.com",
      "credentials": "~/.config/kognic/credentials-demo.json"
    }
  }
}
```

Each context has the following fields:
- `host` - The API hostname, used by `call` to automatically match a context based on the request URL.
- `auth_server` - The OAuth server URL used to fetch tokens.
- `credentials` *(optional)* - Path to a JSON credentials file. Tilde (`~`) is expanded. If omitted, credentials are read from environment variables.

`default_context` specifies which context to use as a fallback when no `--context` flag is given and no URL match is found.

### get-access-token

Generate an access token for Kognic API authentication.

```bash
kognic-auth get-access-token [--server SERVER] [--credentials FILE] [--context NAME] [--config FILE]
```

**Options:**
- `--server` - Authentication server URL (default: `https://auth.app.kognic.com`)
- `--credentials` - Path to JSON credentials file. If not provided, credentials are read from environment variables.
- `--context` - Use a named context from the config file.
- `--config` - Config file path (default: `~/.config/kognic/config.json`)

When `--context` is provided, the auth server and credentials are resolved from the config file. Explicit `--server` or `--credentials` flags override the context values.

**Examples:**
```bash
# Using environment variables (KOGNIC_CREDENTIALS or KOGNIC_CLIENT_ID/KOGNIC_CLIENT_SECRET)
kognic-auth get-access-token

# Using a credentials file
kognic-auth get-access-token --credentials ~/.config/kognic/credentials.json

# Using a named context
kognic-auth get-access-token --context demo

# Using a context but overriding the server
kognic-auth get-access-token --context demo --server https://custom.server
```

### call

Make an authenticated HTTP request to a Kognic API.

```bash
kognic-auth call URL [-X METHOD] [-d DATA] [-H HEADER] [--format FORMAT] [--context NAME] [--config FILE]
```

**Options:**
- `URL` - Full URL to call
- `-X`, `--request` - HTTP method (default: `GET`)
- `-d`, `--data` - Request body (JSON string)
- `-H`, `--header` - Header in `Key: Value` format (repeatable)
- `--format` - Output format (default: `json`). See [Output formats](#output-formats) below.
- `--context` - Force a specific context (skip URL-based matching)
- `--config` - Config file path (default: `~/.config/kognic/config.json`)

When `--context` is not provided, the context is automatically resolved by matching the request URL's hostname against the `host` field of each context in the config file.

**Examples:**
```bash
# GET request (default method), context auto-resolved from URL hostname
kognic-auth call https://app.kognic.com/v1/projects

# Explicit context
kognic-auth call https://demo.kognic.com/v1/projects --context demo

# POST with JSON body
kognic-auth call https://app.kognic.com/v1/projects -X POST -d '{"name": "test"}'

# Custom headers
kognic-auth call https://app.kognic.com/v1/projects -H "Accept: application/json"
```

#### Output formats

The `--format` option controls how JSON responses are printed. For `jsonl`, `csv`, `tsv`, and `table`, the command automatically extracts the list from responses that are either a top-level JSON array or a JSON object with a single key holding an array (e.g. `{"data": [...]}`). If the response doesn't match this shape, it falls back to pretty-printed JSON.

| Format  | Description |
|---------|-------------|
| `json`  | Pretty-printed JSON (default) |
| `jsonl` | One JSON object per line ([JSON Lines](https://jsonlines.org/)) |
| `csv`   | Comma-separated values with a header row |
| `tsv`   | Tab-separated values with a header row |
| `table` | Markdown table with aligned columns |

Nested values (dicts and lists) are JSON-serialized in `csv`, `tsv`, and `table` output.

```bash
# One JSON object per line, useful for piping to jq or grep
kognic-auth call https://app.kognic.com/v1/projects --format=jsonl

# CSV output
kognic-auth call https://app.kognic.com/v1/projects --format=csv

# TSV output, easy to paste into spreadsheets
kognic-auth call https://app.kognic.com/v1/projects --format=tsv

# Markdown table
kognic-auth call https://app.kognic.com/v1/projects --format=table
```

**Exit codes:**
- `0` - Success (HTTP 2xx)
- `1` - Error (HTTP error, missing credentials, invalid input, etc.)

## Changelog
See Github releases from v3.1.0, historic changelog is available in CHANGELOG.md
