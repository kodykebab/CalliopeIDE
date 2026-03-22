#!/usr/bin/env python3
"""
Calliope IDE — Entry Point

Starts the Flask backend server. Run from the repo root:

    python main.py [port]

Environment variables (set in .env or export before running):
    GEMINI_API_KEY   — required, your Google Gemini API key
    CORS_ORIGINS     — optional, comma-separated allowed origins
                       (default: http://localhost:3000,http://localhost:5173)
    DATABASE_URL     — optional, SQLAlchemy database URL
                       (default: sqlite:///calliope.db)
    PORT             — optional, port to run on (default: 8000)

Quick start:
    1. Copy .env.example to .env and fill in GEMINI_API_KEY
    2. pip install -r requirements.txt
    3. python main.py
    4. In another terminal: npm run dev
"""

import os
import sys
from dotenv import load_dotenv

# Load .env from repo root before importing anything else
load_dotenv()

def check_env():
    """Validate required environment variables before starting."""
    missing = []
    if not os.environ.get("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")
    if missing:
        print("Error: The following required environment variables are not set:")
        for var in missing:
            print(f"  - {var}")
        print("\nCopy .env.example to .env and fill in the missing values.")
        sys.exit(1)

def main():
    check_env()

    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))

    print(f"Starting Calliope IDE backend on port {port}...")
    print(f"Frontend should run on http://localhost:3000 (npm run dev)")
    print(f"Backend API available at http://localhost:{port}")
    print()

    # Import here so env vars are loaded first
    from server.agent import app
    app.run(port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")

if __name__ == "__main__":
    main()
