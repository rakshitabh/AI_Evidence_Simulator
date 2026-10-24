"""
Configuration module for the AI Evidence-to-Decision Simulator.
Provides centralized path management, environment settings, and case constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AVAILABLE_DATA_DIR = DATA_DIR / "available"
RESTRICTED_DATA_DIR = DATA_DIR / "restricted"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ASSETS_DIR = BASE_DIR / "assets"
REPORTS_DIR = BASE_DIR / "reports"

# Ensure runtime directories exist
for directory in [DATA_DIR, AVAILABLE_DATA_DIR, RESTRICTED_DATA_DIR, PROCESSED_DATA_DIR, ASSETS_DIR, REPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "simulator.db")))

# Case Constants (Synthetic Case: NEXUS-CASE-2026-88)
CASE_ID = "NEXUS-CASE-2026-88"
CASE_TITLE = "Fictional Shipment Discrepancy: Nexus Electronics vs Vertex Semiconductor"
ORDER_VALUE_INR = 1800000  # ₹18,00,000 (INR 18 Lakhs)
ORDERED_QUANTITY = 500
BUYER_NAME = "Nexus Electronics India Pvt Ltd"
SUPPLIER_NAME = "Vertex Semiconductor Solutions Ltd"
COURIER_NAME = "SwiftLogistics India Pvt Ltd"
WAREHOUSE_LOCATION = "Nexus Central Warehouse Dock 4, Tech Park, Whitefield, Bengaluru"

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "15"))

# Access Control Settings
ACCESS_CONTROL_MODE = os.getenv("ACCESS_CONTROL_MODE", "strict")
MIN_REASON_WORD_COUNT = 8

# Scoring Rubric Constants (Total = 100)
RUBRIC_MAX_SCORES = {
    "evidence_extraction": 15,
    "grounded_analysis": 20,
    "conflict_detection": 20,
    "controlled_requests": 15,
    "scoring_validation": 15,
    "interface_report": 5,
    "code_quality": 10,
}

# UI Theme Colors (Navy, White, Teal)
THEME_NAVY = "#0F172A"       # Slate 900
THEME_NAVY_LIGHT = "#1E293B" # Slate 800
THEME_TEAL = "#0D9488"       # Teal 600
THEME_TEAL_LIGHT = "#14B8A6" # Teal 500
THEME_BG = "#F8FAFC"         # Slate 50
THEME_CARD_BG = "#FFFFFF"    # White
THEME_BORDER = "#E2E8F0"     # Slate 200
THEME_TEXT_MUTED = "#64748B" # Slate 500
THEME_ACCENT_RED = "#EF4444" # Red 500
THEME_ACCENT_AMBER = "#F59E0B"# Amber 500
THEME_ACCENT_GREEN = "#10B981"# Emerald 500
