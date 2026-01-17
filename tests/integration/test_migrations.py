import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Add db to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "db"))


@pytest.fixture(scope="module")
def test_db_url(docker_ip, docker_services):
    """Get test database URL from docker-compose."""
    return "postgresql+psycopg://app:app@localhost:5432/calendar_ai"


@pytest.fixture(scope="function")
def clean_db(test_db_url):
    """Create a clean database for each test."""
    engine = create_engine(
        test_db_url,
        poolclass=StaticPool,
        pool_pre_ping=True,
        echo=False,
    )
    conn = engine.connect()

    # Drop all tables if they exist
    conn.execute(text("DROP SCHEMA public CASCADE"))
    conn.execute(text("CREATE SCHEMA public"))
    conn.commit()

    yield conn

    conn.close()


def test_pgvector_extension_installed(clean_db):
    """Test that pgvector extension is available."""
    result = clean_db.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
    rows = result.fetchall()
    assert len(rows) == 0, "Extension should not exist before migration"

    # Apply migration
    from migrations.env import run_migrations_online
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app:app@localhost:5432/calendar_ai")
    run_migrations_online()

    # Check extension is installed
    result = clean_db.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
    rows = result.fetchall()
    assert len(rows) == 1, "pgvector extension should be installed"


def test_tables_exist(clean_db):
    """Test that all required tables are created."""
    # Apply migration
    from migrations.env import run_migrations_online
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app:app@localhost:5432/calendar_ai")
    run_migrations_online()

    # Check tables exist
    result = clean_db.execute(text("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """))
    tables = [row[0] for row in result.fetchall()]

    expected_tables = [
        "events",
        "documents",
        "embeddings",
        "rules",
        "audit_log",
        "alembic_version",  # Created by alembic
    ]

    for table in expected_tables:
        assert table in tables, f"Table {table} should exist"


def test_vector_type_exists(clean_db):
    """Test that vector type is created."""
    # Apply migration
    from migrations.env import run_migrations_online
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app:app@localhost:5432/calendar_ai")
    run_migrations_online()

    # Check vector type exists
    result = clean_db.execute(text("""
        SELECT typname
        FROM pg_type
        WHERE typname = 'vec_384'
    """))
    rows = result.fetchall()
    assert len(rows) == 1, "vec_384 type should exist"


def test_insert_and_select_embedding(clean_db):
    """Test inserting and selecting an embedding."""
    # Apply migration
    from migrations.env import run_migrations_online
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app:app@localhost:5432/calendar_ai")
    run_migrations_online()

    # Insert a document
    clean_db.execute(text("""
        INSERT INTO documents (user_id, content, doc_type)
        VALUES ('user1', 'test document', 'note')
        RETURNING id
    """))
    doc_id = clean_db.execute(text("SELECT lastval()")).scalar()

    # Insert an embedding
    import numpy as np
    embedding = np.random.rand(384).tolist()
    embedding_str = f"[{','.join(str(x) for x in embedding)}]"

    clean_db.execute(text(f"""
        INSERT INTO embeddings (document_id, embedding, model_version)
        VALUES ({doc_id}, '{embedding_str}'::vector(384), 'bge-small')
    """))
    clean_db.commit()

    # Select the embedding
    result = clean_db.execute(text("""
        SELECT document_id, model_version
        FROM embeddings
        WHERE document_id = :doc_id
    """), {"doc_id": doc_id})
    row = result.fetchone()

    assert row is not None, "Embedding should exist"
    assert row[0] == doc_id, "Document ID should match"
    assert row[1] == "bge-small", "Model version should match"


def test_ivfflat_index_exists(clean_db):
    """Test that ivfflat index is created."""
    # Apply migration
    from migrations.env import run_migrations_online
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app:app@localhost:5432/calendar_ai")
    run_migrations_online()

    # Check index exists
    result = clean_db.execute(text("""
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = 'embeddings_embedding_idx'
    """))
    rows = result.fetchall()
    assert len(rows) == 1, "ivfflat index should exist"
