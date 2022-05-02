from annotell.auth.requests.auth_session import RequestsAuthSession
import warnings


def FaultTolerantAuthRequestSession(*args, **kwargs):
    """Keep this interface for compatibility"""
    warnings.warn("Deprecated, please use explicit "
                  "annotell.auth.requests.auth_session.RequestsAuthSession", DeprecationWarning)
    return RequestsAuthSession(*args, **kwargs).session

