import sys
from pathlib import Path

# Add services/api to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api"))
