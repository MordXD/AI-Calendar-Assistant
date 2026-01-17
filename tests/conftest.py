import sys
import time
from pathlib import Path

import pytest

# Add db to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "db"))


@pytest.fixture(scope="session")
def docker_ip():
    """Get the Docker host IP.

    On Linux this is localhost, on Docker Desktop it's the Docker internal IP.
    """
    return "localhost"


@pytest.fixture(scope="session")
def docker_services(docker_ip):
    """Wait for Docker services to be ready.

    This is a simple fixture - you may want to use testcontainers-docker
    or pytest-docker for more robust testing.
    """
    # Wait for PostgreSQL
    for _ in range(30):
        try:
            import psycopg
            conn = psycopg.connect(
                host=docker_ip,
                port=5432,
                user="app",
                password="app",
                dbname="calendar_ai",
                connect_timeout=2,
            )
            conn.close()
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("PostgreSQL did not start in time")

    # Wait for Redis
    for _ in range(30):
        try:
            import redis
            r = redis.Redis(host=docker_ip, port=6379, socket_connect_timeout=2)
            r.ping()
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("Redis did not start in time")

    # Wait for OpenSearch
    for _ in range(30):
        try:
            import requests
            resp = requests.get(f"http://{docker_ip}:9200", timeout=2)
            if resp.status_code == 200:
                break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("OpenSearch did not start in time")

    yield

    # Cleanup happens automatically
