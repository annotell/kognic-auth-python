import logging
from copy import copy
from datetime import datetime, timedelta
from authlib.oauth2.client import OAuth2Client

log = logging.getLogger(__name__)


class RefreshTokenExpiryFixOAuth2Client(OAuth2Client):
    """
    Override class to pop the refresh token from the oauth token is expired
    This will make the authlib start a new flow
    """

    @OAuth2Client.token.getter
    def token(self):
        refresh_expires_at = self.token_auth.token.get("refresh_expires_at") if self.token_auth.token else None
        if refresh_expires_at:
            soon = datetime.utcnow() + timedelta(seconds=5)
            if refresh_expires_at < soon:
                # return without refresh token if it's invalid,
                # this will make authlib start over with a new flow
                t = copy(self.token_auth.token)
                t.pop("refresh_token")
                return t

        return self.token_auth.token


