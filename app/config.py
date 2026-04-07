"""앱 설정: DB, ODA, 스토리지, 개발 모드."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# libpq 클라이언트 인코딩 힌트
os.environ.setdefault("PGCLIENTENCODING", "UTF8")


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://caduser:cadpass@127.0.0.1:5432/cadmanage"
    upload_root: Path = Path("./data/uploads")
    oda_fc_path: str | None = None
    oda_dxf_version: str = "ACAD2018"
    dev_allow_dxf_upload: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 환경변수 ODA_FC_PATH 우선
        oda = os.environ.get("ODA_FC_PATH", "").strip()
        if oda and not self.oda_fc_path:
            self.oda_fc_path = oda or None


def get_settings() -> Settings:
    return Settings()
