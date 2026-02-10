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

## CLI

The package provides a command-line interface for generating access tokens, great for MCP integrations.

```bash
kognic-auth get-access-token [--server SERVER] [--credentials FILE]
```

**Options:**
- `--server` - Authentication server URL (default: `https://auth.app.kognic.com`)
- `--credentials` - Path to JSON credentials file. If not provided, credentials are read from environment variables.

The token endpoint is constructed by appending `/v1/auth/oauth/token` to the server URL. For example:
- Default: `https://auth.app.kognic.com/v1/auth/oauth/token`
- Custom: `https://custom.server/v1/auth/oauth/token`

**Exit codes:**
- `0` - Success
- `1` - Error (missing credentials, invalid credentials file, authentication failure, etc.)

**Examples:**
```bash
# Using environment variables (KOGNIC_CREDENTIALS or KOGNIC_CLIENT_ID/KOGNIC_CLIENT_SECRET)
kognic-auth get-access-token

# Using a credentials file
kognic-auth get-access-token --credentials ~/.config/kognic/credentials.json

# Using a custom authentication server
kognic-auth get-access-token --server https://auth.<env>.kognic.com
```

## Base API Clients

For building API clients that need authenticated HTTP requests, use the V2 base clients.
These provide a requests/httpx-compatible interface with enhancements:

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
client = MyApiClient(client_id="...", client_secret="...")

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

## Changelog
See Github releases from v3.1.0, historic changelog is available in CHANGELOG.md
