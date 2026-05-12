"""
main.py — Entry point for Android LLM Agent

Usage:
    python main.py

Environment:
    Set AI_MODE and API keys in .env (see .env.example)
    Configure device coordinates in config/device.json (see config/device.example.json)
"""

from dotenv import load_dotenv

load_dotenv()

from auto_reply import run

if __name__ == "__main__":
    run()
