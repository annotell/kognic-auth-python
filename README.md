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
3. Set environment variables `KOGNIC_CLIENT_ID` and `KOGNIC_CLIENT_SECRET`
4. Set to credentials tuple `auth=(client_id, client_secret)`
5. Store credentials in the system keyring (see [Storing credentials in the keyring](#storing-credentials-in-the-keyring))

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
This is great for LLM use cases, the `kog get` is a lightweight curl, that hides any complexity of authentication and context management,
so you can just focus on the API call you want to make. This also avoids tokens being leaked to the shell history,
as you can use named environments and config files to manage your credentials.

The interface is currently marked experimental, and breaking changes may be made without a major version bump. Feedback is welcome to help stabilize the design.

### Configuration file

The CLI can be configured with a JSON file at `~/.config/kognic/environments.json`. This lets you define named environments, each with its own host, auth server, and credentials.

```json
{
  "default_environment": "production",
  "environments": {
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

Each environment has the following fields:
- `host` - The API hostname, used by `kog` to automatically match an environment based on the request URL.
- `auth_server` - The OAuth server URL used to fetch tokens.
- `credentials` *(optional)* - Where to load credentials from. Three formats are supported:
  - A file path: `"~/.config/kognic/credentials-prod.json"` (tilde `~` is expanded)
  - A keyring reference: `"keyring://production"` (loads from the system keyring under the named profile)
  - Omit entirely: credentials are read from environment variables or the keyring `default` profile

`default_environment` specifies which environment to use as a fallback when no `--env` flag is given and no URL match is found.

### get-access-token

Generate an access token for Kognic API authentication.

```bash
kognic-auth get-access-token [--server SERVER] [--credentials FILE] [--env NAME] [--env-config-file-path FILE]
```

**Options:**
- `--server` - Authentication server URL (default: `https://auth.app.kognic.com`)
- `--credentials` - Path to JSON credentials file. If not provided, credentials are read from environment variables.
- `--env` - Use a named environment from the config file.
- `--env-config-file-path` - Environment config file path (default: `~/.config/kognic/environments.json`)

When `--env` is provided, the auth server and credentials are resolved from the config file. Explicit `--server` or `--credentials` flags override the environment values.

**Examples:**
```bash
# Using environment variables (KOGNIC_CREDENTIALS or KOGNIC_CLIENT_ID/KOGNIC_CLIENT_SECRET)
kognic-auth get-access-token

# Using a credentials file
kognic-auth get-access-token --credentials ~/.config/kognic/credentials.json

# Using a named environment
kognic-auth get-access-token --env demo

# Using an environment but overriding the server
kognic-auth get-access-token --env demo --server https://custom.server
```

### credentials

Manage credentials stored in the system keyring. This is the recommended way to store credentials on a developer machine — more secure than a credentials file and no environment variables needed.

```bash
kognic-auth credentials load FILE [--env ENV]
kognic-auth credentials clear [--env ENV]
```

**`load`** — reads a Kognic credentials JSON file and stores the `client_id` and `client_secret` in the system keyring.

- `FILE` - Path to a Kognic credentials JSON file (the same format accepted by `--credentials`)
- `--env` - Profile name to store under (default: `default`). Use the environment name from `environments.json` to link the credentials to that environment.

**`clear`** — removes credentials from the keyring for the given profile.

**Examples:**
```bash
# Store credentials under the default profile (used as fallback when no credentials are configured)
kognic-auth credentials load ~/Downloads/credentials.json

# Store per-environment credentials
kognic-auth credentials load ~/Downloads/prod-creds.json --env production
kognic-auth credentials load ~/Downloads/demo-creds.json --env demo

# Remove credentials
kognic-auth credentials clear --env demo
```

### Storing credentials in the keyring

The system keyring (macOS Keychain, GNOME Keyring, Windows Credential Manager, etc.) is the recommended place to keep credentials on a developer machine. No credentials files on disk, no environment variables in shell profiles.

**Single-environment setup** — store once, works everywhere:
```bash
kognic-auth credentials load ~/Downloads/credentials.json
# All CLI commands and the SDK will now find credentials automatically
```

**Multi-environment setup** — store per-environment credentials and reference them in `environments.json`:
```bash
kognic-auth credentials load ~/Downloads/prod-creds.json --env production
kognic-auth credentials load ~/Downloads/demo-creds.json --env demo
```

Then in `~/.config/kognic/environments.json`, reference the keyring profiles with `keyring://`:
```json
{
  "default_environment": "production",
  "environments": {
    "production": {
      "host": "app.kognic.com",
      "auth_server": "https://auth.app.kognic.com",
      "credentials": "keyring://production"
    },
    "demo": {
      "host": "demo.kognic.com",
      "auth_server": "https://auth.demo.kognic.com",
      "credentials": "keyring://demo"
    }
  }
}
```

Now `kog get https://app.kognic.com/v1/projects` automatically picks up the `production` keyring credentials, and `kog get https://demo.kognic.com/v1/projects` picks up `demo`.

The `keyring://` URI also works in the `auth` parameter of API clients:
```python
client = BaseApiClient(auth="keyring://production")
```

**Credential resolution order** — when no explicit `auth` is provided, the SDK tries sources in this order:
1. `KOGNIC_CREDENTIALS` environment variable (path to credentials JSON file)
2. `KOGNIC_CLIENT_ID` + `KOGNIC_CLIENT_SECRET` environment variables
3. System keyring, `default` profile

### kog

Make an authenticated HTTP request to a Kognic API.

```bash
kog <METHOD> URL [-d DATA] [-H HEADER] [--format FORMAT] [--env NAME] [--env-config-file-path FILE]
```

**Options:**
- `METHOD` - Method, get, post, put, delete, patch, etc
- `URL` - Full URL to call
- `-d`, `--data` - Request body (JSON string)
- `-H`, `--header` - Header in `Key: Value` format (repeatable)
- `--format` - Output format (default: `json`). See [Output formats](#output-formats) below.
- `--env` - Force a specific environment (skip URL-based matching)
- `--env-config-file-path` - Environment config file path (default: `~/.config/kognic/environments.json`)

When `--env` is not provided, the environment is automatically resolved by matching the request URL's hostname against the `host` field of each environment in the config file.

**Examples:**
```bash
# GET request (default method), environment auto-resolved from URL hostname
kog get https://app.kognic.com/v1/projects

# Explicit environment
kog get https://demo.kognic.com/v1/projects --env demo

# POST with JSON body
kog post https://app.kognic.com/v1/projects -d '{"name": "test"}'

# Custom headers
kog get https://app.kognic.com/v1/projects -H "Accept: application/json"
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
kog get https://app.kognic.com/v1/projects --format=jsonl

# CSV output
kog get https://app.kognic.com/v1/projects --format=csv

# TSV output, easy to paste into spreadsheets
kog get https://app.kognic.com/v1/projects --format=tsv

# Markdown table
kog get https://app.kognic.com/v1/projects --format=table
```

**Exit codes:**
- `0` - Success (HTTP 2xx)
- `1` - Error (HTTP error, missing credentials, invalid input, etc.)

## Base API Clients

For building API clients that need authenticated HTTP requests, use the base clients.
These provide a `requests`/`httpx`-compatible interface with enhancements:

- OAuth2 authentication with automatic token refresh
- Automatic JSON serialization for jsonable objects
- Retry logic for transient errors (502, 503, 504)
- Sunset header handling (logs warnings for deprecated endpoints)
- Enhanced error messages with response body details

### Sync Client (requests)

```python
from kognic.auth.requests import BaseApiClient

class MyApiClient(BaseApiClient):
    def get_resource(self, resource_id: str):
        response = self.session.get(f"https://api.app.kognic.com/v1/resources/{resource_id}")
        return response.json()

# Usage with environment variables
client = MyApiClient()

# Or with explicit credentials
client = MyApiClient(auth=("my-client-id", "my-client-secret"))

# Or with credentials file
client = MyApiClient(auth="~/.config/kognic/credentials.json")
```

### Async Client (httpx)

```python
from kognic.auth.httpx import BaseAsyncApiClient

class MyAsyncApiClient(BaseAsyncApiClient):
    async def get_resource(self, resource_id: str):
        session = await self.session
        response = await session.get(f"https://api.app.kognic.com/v1/resources/{resource_id}")
        return response.json()

# Usage as async context manager
async with MyAsyncApiClient() as client:
    resource = await client.get_resource("123")
```

## Serialization & Deserialization

The `kognic.auth.serde` module provides utilities for serializing request bodies and deserializing responses.

### Serialization

`serialize_body()` converts objects to JSON-compatible dicts. Supports:
- Pydantic v2 models (`model_dump()`)
- Objects with `to_json()` or `to_dict()` methods
- Nested objects in dicts/lists are recursively serialized

```python
from pydantic import BaseModel
from kognic.auth.serde import serialize_body

class CreateRequest(BaseModel):
    name: str
    value: int

# Pydantic models
request = CreateRequest(name="test", value=42)
serialize_body(request)  # {"name": "test", "value": 42}

# Nested in containers
serialize_body({"items": [request]})  # {"items": [{"name": "test", "value": 42}]}

# Custom classes with to_dict()
class MyModel:
    def to_dict(self):
        return {"key": "value"}

serialize_body(MyModel())  # {"key": "value"}
```

### Deserialization

`deserialize()` extracts and converts API responses. Supports:
- Pydantic v2 models (`model_validate()`)
- Classes with `from_dict()` or `from_json()` methods
- Automatic envelope extraction (default key: `"data"`)

```python
from kognic.auth.serde import deserialize

# Deserialize to Pydantic model
response = client.session.get("https://api.app.kognic.com/v1/resource/123")
resource = deserialize(response, cls=ResourceModel)

# Deserialize list of models
response = client.session.get("https://api.app.kognic.com/v1/resources")
resources = deserialize(response, cls=list[ResourceModel])

# Custom envelope key
data = deserialize(response, cls=MyModel, enveloped_key="result")

# No envelope
data = deserialize(response, cls=MyModel, enveloped_key=None)
```

## Changelog
See Github releases from v3.1.0, historic changelog is available in CHANGELOG.md
