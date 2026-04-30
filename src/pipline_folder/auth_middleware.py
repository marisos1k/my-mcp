from api_folder.api_module import APIKeyManager

class AuthMiddleware:
    """Прослойка для аутентификации"""
    
    def __init__(self, api_manager: APIKeyManager):
        self.api_manager = api_manager
        self._current_user = None
    
    async def authenticate(self, api_key: str) -> dict:
        """Аутентификация и возврат пользователя"""
        user = await self.api_manager.get_user_by_api_key(api_key)
        if not user:
            raise Exception("Invalid API key")
        self._current_user = user
        return user
    
    async def get_current_user(self) -> dict:
        """Получить текущего аутентифицированного пользователя"""
        if not self._current_user:
            raise Exception("No authenticated user")
        return self._current_user