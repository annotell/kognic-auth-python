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
as you can use named environments and config files to manage your credentials.

The interface is currently marked experimental, and breaking changes may be made without a major version bump. Feedback is welcome to help stabilize the design.

### Configuration file

The CLI can be configured with a JSON file at `~/.config/kognic/config.json`. This lets you define named environments, each with its own host, auth server, and credentials.

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
- `host` - The API hostname, used by `call` to automatically match an environment based on the request URL.
- `auth_server` - The OAuth server URL used to fetch tokens.
- `credentials` *(optional)* - Path to a JSON credentials file. Tilde (`~`) is expanded. If omitted, credentials are read from environment variables.

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
- `--env-config-file-path` - Environment config file path (default: `~/.config/kognic/config.json`)

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

### call

Make an authenticated HTTP request to a Kognic API.

```bash
kognic-auth call URL [-X METHOD] [-d DATA] [-H HEADER] [--format FORMAT] [--env NAME] [--env-config-file-path FILE]
```

**Options:**
- `URL` - Full URL to call
- `-X`, `--request` - HTTP method (default: `GET`)
- `-d`, `--data` - Request body (JSON string)
- `-H`, `--header` - Header in `Key: Value` format (repeatable)
- `--format` - Output format (default: `json`). See [Output formats](#output-formats) below.
- `--env` - Force a specific environment (skip URL-based matching)
- `--env-config-file-path` - Environment config file path (default: `~/.config/kognic/config.json`)

When `--env` is not provided, the environment is automatically resolved by matching the request URL's hostname against the `host` field of each environment in the config file.

**Examples:**
```bash
# GET request (default method), environment auto-resolved from URL hostname
kognic-auth call https://app.kognic.com/v1/projects

# Explicit environment
kognic-auth call https://demo.kognic.com/v1/projects --env demo

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
