#!/usr/bin/env python3
"""Script to run Alembic migrations."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from alembic.config import Config
from alembic import command


def main():
    """Run Alembic migrations."""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        "postgresql+psycopg://app:app@localhost:5432/calendar_ai"
    )

    # Run upgrade head
    command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    main()
