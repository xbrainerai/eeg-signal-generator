from auth.authenticator import Authenticator

class MockAuthenticator(Authenticator):
    SECRET_KEY = "mock-secret-key"

    def authenticate(self, token: str | None) -> bool:
        if token is None:
            return False
        return token == MockAuthenticator.SECRET_KEY
