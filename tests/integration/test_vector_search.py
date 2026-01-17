import sys
from pathlib import Path

import pytest
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# Add db to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "db"))


@pytest.fixture(scope="function")
def clean_db(docker_ip, docker_services):
    """Create a clean database with test data."""
    engine = create_engine(
        "postgresql+psycopg://app:app@localhost:5432/calendar_ai",
        poolclass=StaticPool,
        pool_pre_ping=True,
        echo=False,
    )
    conn = engine.connect()

    # Reset schema
    conn.execute(text("DROP SCHEMA public CASCADE"))
    conn.execute(text("CREATE SCHEMA public"))
    conn.commit()

    # Apply migration
    from migrations.env import run_migrations_online
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://app:app@localhost:5432/calendar_ai")
    run_migrations_online()

    yield conn

    conn.close()


def test_insert_10_vectors(clean_db):
    """Test inserting 10 vectors into the database."""
    # Insert 10 documents with embeddings
    for i in range(10):
        # Create deterministic embeddings based on index
        embedding = np.zeros(384)
        embedding[i % 384] = 1.0

        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        clean_db.execute(text(f"""
            INSERT INTO documents (user_id, content, doc_type)
            VALUES ('user1', 'document {i}', 'note')
            RETURNING id
        """))
        doc_id = clean_db.execute(text("SELECT lastval()")).scalar()

        clean_db.execute(text(f"""
            INSERT INTO embeddings (document_id, embedding, model_version)
            VALUES ({doc_id}, '{embedding_str}'::vector(384), 'bge-small')
        """))

    clean_db.commit()

    # Verify count
    result = clean_db.execute(text("SELECT COUNT(*) FROM embeddings"))
    count = result.scalar()
    assert count == 10, f"Expected 10 embeddings, got {count}"


def test_similarity_search_sorting(clean_db):
    """Test that similarity search returns correctly sorted results."""
    # Create a query vector - similar to document 5
    query_vector = np.zeros(384)
    query_vector[5] = 1.0
    query_str = f"[{','.join(str(x) for x in query_vector)}]"

    # Insert 10 documents with embeddings
    for i in range(10):
        embedding = np.zeros(384)
        embedding[i % 384] = 1.0

        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        clean_db.execute(text(f"""
            INSERT INTO documents (user_id, content, doc_type)
            VALUES ('user1', 'document {i}', 'note')
            RETURNING id
        """))
        doc_id = clean_db.execute(text("SELECT lastval()")).scalar()

        clean_db.execute(text(f"""
            INSERT INTO embeddings (document_id, embedding, model_version)
            VALUES ({doc_id}, '{embedding_str}'::vector(384), 'bge-small')
        """))

    clean_db.commit()

    # Perform similarity search - document 5 should be most similar (cosine = 1.0)
    result = clean_db.execute(text(f"""
        SELECT d.id, d.content, 1 - (e.embedding <=> '{query_str}'::vector(384)) as similarity
        FROM embeddings e
        JOIN documents d ON e.document_id = d.id
        ORDER BY e.embedding <=> '{query_str}'::vector(384)
        LIMIT 5
    """))
    rows = result.fetchall()

    # First result should be document 5 with similarity 1.0
    assert len(rows) >= 1, "Should return at least 1 result"
    assert "document 5" in rows[0][1], f"First result should be document 5, got {rows[0][1]}"
    assert abs(rows[0][2] - 1.0) < 0.01, f"First result similarity should be 1.0, got {rows[0][2]}"

    # Results should be sorted by similarity (descending)
    similarities = [row[2] for row in rows]
    assert similarities == sorted(similarities, reverse=True), "Results should be sorted by similarity descending"


def test_topk_limit(clean_db):
    """Test that topK query respects LIMIT."""
    query_vector = np.zeros(384)
    query_vector[0] = 1.0
    query_str = f"[{','.join(str(x) for x in query_vector)}]"

    # Insert 20 vectors
    for i in range(20):
        embedding = np.zeros(384)
        embedding[i % 5] = 1.0  # Only first 5 dimensions matter

        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        clean_db.execute(text(f"""
            INSERT INTO documents (user_id, content, doc_type)
            VALUES ('user1', 'document {i}', 'note')
            RETURNING id
        """))
        doc_id = clean_db.execute(text("SELECT lastval()")).scalar()

        clean_db.execute(text(f"""
            INSERT INTO embeddings (document_id, embedding, model_version)
            VALUES ({doc_id}, '{embedding_str}'::vector(384), 'bge-small')
        """))

    clean_db.commit()

    # Query top 3
    result = clean_db.execute(text(f"""
        SELECT d.id, d.content
        FROM embeddings e
        JOIN documents d ON e.document_id = d.id
        ORDER BY e.embedding <=> '{query_str}'::vector(384)
        LIMIT 3
    """))
    rows = result.fetchall()

    assert len(rows) == 3, f"Expected 3 results, got {len(rows)}"


def test_cosine_distance_formula(clean_db):
    """Test that cosine distance is calculated correctly."""
    # Document 0: [1, 0, 0, ...]
    v1 = np.zeros(384)
    v1[0] = 1.0
    v1_str = f"[{','.join(str(x) for x in v1)}]"

    # Document 1: [0, 1, 0, ...]
    v2 = np.zeros(384)
    v2[1] = 1.0
    v2_str = f"[{','.join(str(x) for x in v2)}]"

    # Query: [1, 1, 0, ...]
    query = np.zeros(384)
    query[0] = 1.0
    query[1] = 1.0
    query_str = f"[{','.join(str(x) for x in query)}]"

    # Insert documents
    for i, emb_str in enumerate([v1_str, v2_str]):
        clean_db.execute(text(f"""
            INSERT INTO documents (user_id, content, doc_type)
            VALUES ('user1', 'document {i}', 'note')
            RETURNING id
        """))
        doc_id = clean_db.execute(text("SELECT lastval()")).scalar()

        clean_db.execute(text(f"""
            INSERT INTO embeddings (document_id, embedding, model_version)
            VALUES ({doc_id}, '{emb_str}'::vector(384), 'bge-small')
        """))

    clean_db.commit()

    # Query and check distances
    result = clean_db.execute(text(f"""
        SELECT d.content, e.embedding <=> '{query_str}'::vector(384) as distance
        FROM embeddings e
        JOIN documents d ON e.document_id = d.id
        ORDER BY distance
    """))
    rows = result.fetchall()

    # Document 0: cos([1,1], [1,0]) = 1 / sqrt(2) = 0.707... => distance = 1 - 0.707 = 0.293
    # Document 1: same as document 0, symmetric
    # Both should have the same distance
    assert len(rows) == 2
    assert abs(rows[0][1] - rows[1][1]) < 0.001, "Both documents should have same distance"
    assert 0.2 < rows[0][1] < 0.4, f"Distance should be around 0.293, got {rows[0][1]}"


def test_different_users_isolated(clean_db):
    """Test that embeddings from different users are properly isolated."""
    # User 1 embeddings
    for i in range(5):
        embedding = np.zeros(384)
        embedding[i] = 1.0
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        clean_db.execute(text(f"""
            INSERT INTO documents (user_id, content, doc_type)
            VALUES ('user1', 'user1 doc {i}', 'note')
            RETURNING id
        """))
        doc_id = clean_db.execute(text("SELECT lastval()")).scalar()

        clean_db.execute(text(f"""
            INSERT INTO embeddings (document_id, embedding, model_version)
            VALUES ({doc_id}, '{embedding_str}'::vector(384), 'bge-small')
        """))

    # User 2 embeddings
    for i in range(5):
        embedding = np.zeros(384)
        embedding[i + 5] = 1.0
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        clean_db.execute(text(f"""
            INSERT INTO documents (user_id, content, doc_type)
            VALUES ('user2', 'user2 doc {i}', 'note')
            RETURNING id
        """))
        doc_id = clean_db.execute(text("SELECT lastval()")).scalar()

        clean_db.execute(text(f"""
            INSERT INTO embeddings (document_id, embedding, model_version)
            VALUES ({doc_id}, '{embedding_str}'::vector(384), 'bge-small')
        """))

    clean_db.commit()

    # Query for user1 only
    query_vector = np.zeros(384)
    query_vector[0] = 1.0
    query_str = f"[{','.join(str(x) for x in query_vector)}]"

    result = clean_db.execute(text(f"""
        SELECT d.user_id, COUNT(*) as cnt
        FROM embeddings e
        JOIN documents d ON e.document_id = d.id
        WHERE d.user_id = 'user1'
        GROUP BY d.user_id
    """))
    rows = result.fetchall()

    assert len(rows) == 1
    assert rows[0][1] == 5, "User1 should have 5 documents"
