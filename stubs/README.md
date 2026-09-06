# Local type stubs

Authlib ships no `py.typed` and is entirely unannotated, so under strict pyright every
value that comes out of it is `Unknown`. The published `types-Authlib` package does not
help: measured against this repo it produced a zero-error delta, because its members are
almost all `Incomplete` and its `OAuth2Session` drops the `requests.Session` base class
that we rely on for `.mount()`.

These stubs cover only the authlib surface this package actually touches. They are a
development-time aid and are not shipped in the wheel. Extend them when you start using
another authlib symbol.
