from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    quote_service_url: str = "http://localhost:8000"
    quote_service_timeout: float = 30.0

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-5.4-mini"
    agent_few_shot_count: int = 5
    agent_recursion_limit: int = 25


settings = Settings()
