from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """
    Email verification links. Same signing as password reset tokens, but they last
    ACCOUNT_ACTIVATION_TIMEOUT instead of PASSWORD_RESET_TIMEOUT, which Django's own
    check_token reads directly, so that check is re-implemented here with the longer window.
    """

    key_salt = "accounts.tokens.AccountActivationTokenGenerator"

    def check_token(self, user, token):
        if not (user and token):
            return False
        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        if not any(
            constant_time_compare(self._make_token_with_timestamp(user, ts, secret), token)
            for secret in [self.secret, *self.secret_fallbacks]
        ):
            return False

        return (self._num_seconds(self._now()) - ts) <= settings.ACCOUNT_ACTIVATION_TIMEOUT


account_activation_token = AccountActivationTokenGenerator()
