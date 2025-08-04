from abc import ABC, abstractmethod

class Authenticator(ABC):

    @abstractmethod
    def authenticate(self, token: str) -> bool:
        pass
