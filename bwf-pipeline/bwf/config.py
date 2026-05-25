from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL
    postgres_user: str = "bwf"
    postgres_password: str = "changeme"
    postgres_db: str = "bwf_pipeline"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Scraping
    bwf_base_url: str = "https://extranet-lv.bwfbadminton.com/api"
    request_delay_seconds: float = 3.0
    request_timeout_seconds: float = 30.0
    max_retries: int = 3

    # Scheduler (format cron)
    discovery_cron: str = "0 8 * * 1"
    matches_cron: str = "0 10 * * 1"

    # Périmètre historique
    scrape_from_year: int = 2018

    # Catégories World Tour uniquement (22=Finals, 23=S1000, 24=S750, 25=S500, 26=S300)
    world_tour_category_ids: list[int] = [22, 23, 24, 25, 26]

    # Disciplines simples uniquement
    singles_disciplines: list[str] = ["MS", "WS"]

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()