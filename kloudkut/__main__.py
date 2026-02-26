"""Entry point for `python -m kloudkut` and `kloudkut` CLI."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import main  # noqa: E402

if __name__ == "__main__":
    main()
