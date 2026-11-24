---
status: accepted
---

# The cut-off retry replays the whole request, and only a replayable body

requests reads a response body after urllib3's `Retry` has finished, so a cut-off response is not covered by it. The clients need their own cut-off retry for the methods in `RETRYABLE_METHODS`, and we decided three things about how it behaves. The first version in the sync client does not follow them yet; the work is tracked in annotell/kognic-soleng#2501.

- **It replays the whole request from the original URL.** Only the outermost send call retries, and it follows any redirect again. The retry decision stays on the method the caller chose, and a redirect to a signed URL gets a fresh URL on each attempt.
- **It never replays a body that is not replayable.** The original error reaches the caller instead. A consumed generator sent again uploads nothing, and the caller sees a success. A consumed file sent again leaves the server waiting for bytes that never come.
- **In the sync client, its attempt budget is separate from the status and connection retries.** Those belong to urllib3. requests hands urllib3 one `Retry` per adapter, and a cut-off error carries no response to read the remaining budget from, so the two cannot share a count.

## Considered Options

- **Retry only the hop that failed**, in a transport adapter. It would also retry the GET that follows a redirected POST, and would hit the redirecting endpoint once. Rejected because it moves the retry into a different layer for a case that no Kognic API spec shows.
- **Buffer a body that is not replayable**, so it can be sent again. Rejected because it holds a whole upload in memory to cover a rare failure.
- **Raise a dedicated exception** when a body is not replayable. Rejected because the caller already gets the error that describes what happened.

## Consequences

- A POST that is redirected to a GET is not retried when the GET's response is cut off.
- A PUT or DELETE with a generator body fails on the first cut-off response. Callers that need the retry pass bytes or a seekable stream.
- When 5xx responses and cut-off responses alternate, the sync client can make up to 16 attempts for one call instead of 4.
- urllib3's own status retry is outside this decision. It still sends a consumed generator body again, which is tracked in annotell/kognic-soleng#2624.
