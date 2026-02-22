import sys
import os

# Add the project root to sys.path to ensure 'app' package is found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import main

if __name__ == "__main__":
    main()
