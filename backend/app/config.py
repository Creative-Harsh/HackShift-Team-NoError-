import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(str(ROOT / '.env'), str(ROOT / 'backend' / '.env')), extra='ignore')
    mongodb_uri: str = 'mongodb://127.0.0.1:27017'
    mongodb_database: str = 'pashuraksha'
    jwt_secret: str = ''
    jwt_expire_minutes: int = 480
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173'
    demo_mode: bool = True
    environment: str = 'development'
    gemini_api_key: SecretStr = SecretStr('')
    gemini_model: str = Field(default='', pattern=r'^[a-zA-Z0-9._-]*$')
    outbreak_radius_km: float = 5.0
    outbreak_window_hours: int = 72
    outbreak_abnormal_threshold: int = 40
    outbreak_suspected_threshold: int = 65

    @model_validator(mode='after')
    def secure_configuration(self):
        if self.environment == 'production':
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith('replace-'):
                raise ValueError('Production requires a private JWT_SECRET of at least 32 characters')
            if self.demo_mode:
                raise ValueError('Disable DEMO_MODE in production')
            if '*' in self.cors_origins:
                raise ValueError('Production requires explicit CORS origins')
        if not self.jwt_secret:
            self.jwt_secret = secrets.token_urlsafe(48)
        if not (0 < self.outbreak_radius_km <= 50):
            raise ValueError('OUTBREAK_RADIUS_KM must be in (0, 50]')
        if not (0 < self.outbreak_window_hours <= 720):
            raise ValueError('OUTBREAK_WINDOW_HOURS must be in (0, 720]')
        # Validate the same contract the calculation uses, before accepting reports.
        # In particular, the window must fit both growth intervals and the
        # suspected threshold cannot exceed the engine's critical threshold.
        from app.outbreak import OutbreakConfig
        OutbreakConfig(radius_km=self.outbreak_radius_km, window_hours=self.outbreak_window_hours,
                       abnormal_threshold=self.outbreak_abnormal_threshold,
                       suspected_threshold=self.outbreak_suspected_threshold)
        return self


@lru_cache
def get_settings():
    return Settings()
