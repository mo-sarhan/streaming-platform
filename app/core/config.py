from pydantic_settings import BaseSettings,SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL:str
    AWS_ENDPOINT_URL:str
    AWS_ACCESS_KEY_ID:str
    AWS_SECRET_ACCESS_KEY:str
    REGION_NAME:str
    CELERY_BROKER_URL:str
    
    model_config = SettingsConfigDict(
        env_file='.env',
        extra='ignore'
    )

    
settings = Settings()