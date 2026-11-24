---
status: accepted
---

# The bearer token is not re-attached once requests has stripped it

When a redirect leaves the original host, requests removes the `Authorization` header, but the sync client's 401 handler stays registered on the redirected request. The handler re-authenticates only when the request still carries the `Bearer` header it was given, and there is no allowlist for Kognic hosts.

Checking for the header reuses requests' own decision about when credentials may follow a redirect, so the library does not keep a second origin comparison that could drift from it. An allowlist would be security-sensitive code for a case that no Kognic API spec shows: the only documented redirect goes to a signed URL, which needs no token.

## Consequences

- A redirect from one Kognic host to another that needs authentication fails with a 401. The fix is to call the target host directly.
- A request whose `Authorization` header was replaced with other credentials on the way is left alone as well.
