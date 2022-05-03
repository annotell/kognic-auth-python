from annotell.auth.requests.auth_session import RequestsAuthSession
import warnings

# for compatibility
from annotell.auth import DEFAULT_HOST

def FaultTolerantAuthRequestSession(*args, **kwargs):
    """Keep this interface for compatibility"""
    warnings.warn("Deprecated, please use explicit "
                  "annotell.auth.requests.auth_session.RequestsAuthSession", DeprecationWarning)
    return RequestsAuthSession(*args, **kwargs).session

