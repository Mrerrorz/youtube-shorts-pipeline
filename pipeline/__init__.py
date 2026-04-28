"""YouTube Shorts Pipeline — AI-Native Content Engine."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

__version__ = "2.1.0-silentcapital"
