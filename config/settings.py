from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    gcp_project_id: str
    bq_dataset: str
    api_url: str
    api_key: str
    excel_path: str
    request_timeout: int
    google_application_credentials: str
    model_config = SettingsConfigDict(frozen=True, env_file=".env")

def get_settings() -> Settings:
    return Settings()