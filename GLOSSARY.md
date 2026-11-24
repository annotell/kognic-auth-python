# Kognic Auth

Authentication for Kognic APIs, and the base HTTP clients that other Kognic API clients are built on.

## Language

**Attempt**:
One request sent on the wire. A call with three retries makes up to four attempts.
_Avoid_: Try, call (one call can span several attempts)

**Cut-off response**:
A response whose connection closes or resets after the headers have arrived and before the body is complete.
_Avoid_: Truncated body, broken body, partial response

**Cut-off retry**:
A repeat of a request because its response was cut off.
_Avoid_: Body retry (it reads as if it concerned the request body)

**Replayable body**:
A request body that can be sent again in full: no body, bytes, text, or a stream that can be rewound to where it started.
_Avoid_: Rewindable body, retryable body
