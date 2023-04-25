These are historic changes, see GitHub releases for the later changes. 

3.0.2 (2022-12-07)
Support read credentials from dict

3.0.0 (2022-09-26)
Rebranded from Annotell to Kognic.
Dropped deprecated FaultTolerantAuthRequestSession

2.0.0 (2022-05-02)
Refactor for backend separation, with optional dependencies for either httpx or requests.

1.8.0 (2022-04-12)
Initial support for httpx (BETA). Solves refresh token expiry by reset without the FaultTolerantAuthRequestSession
The library will be refactored by a breaking 2.0 release, and make the same changes to the requests version. The authsession module backed by requests is untouched for now.

1.7.0 (2022-04-11)
Fix compatibility issue with authlib >= 1.0.0. Resetting the auth session failed, when the refresh token had expired.

1.6.0 (2021-02-21)
Expose underlying requests.Session on FaultTolerantAuthRequestSession
Fix some thread locks

1.5.0 (2020-10-20)
Add FaultTolerantAuthRequestSession that handles token refresh on long running sessions.

1.4.0 (2020-04-16)
Add support for auth parameter, with path to credentials file or AnnotellCredentials object
Drop support for legacy API token
