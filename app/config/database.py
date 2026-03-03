import os


def get_postgres_uri():
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", 5432)
    password = os.environ.get("POSTGRES_PASSWORD", "admin")
    user = os.environ.get("POSTGRES_USER", "admin")
    db_name = os.environ.get("POSTGRES_DB", "smart_routing_db")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"

def get_api_url():
    host = os.environ.get("API_HOST", "localhost")
    port = 8000 if host == "localhost" else 80
    return f"http://{host}:{port}"
