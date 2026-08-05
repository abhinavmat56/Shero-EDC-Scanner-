# Shero — EDC Label Scanner

Scan or paste an ingredient list and Shero tells you which endocrine disrupting
chemicals (EDCs) are in it, how risky they are and what to watch out for.

## What changed from the original prototype

- **Scanner, not just chat.** Upload a photo or use your camera — Gemini's vision
  reads the label so you don't have to type ingredients by hand.
- **Fuzzy matching (`edc_matcher.py`).** Misspellings and naming variants
  ("Bisphenol-A" vs "BPA" vs "bisphenolA") still resolve correctly, via
  `rapidfuzz`.
- **Real results UI.** Risk-level counts, color-coded cards per chemical, and
  expandable details (health effects, where it's found, recommendations) —
  instead of a plain scrolling chat log.
- **Shero AI chat tab.** The original chatbot persona is still here, and it's
  now aware of your last scan so you can ask follow-up questions naturally
  ("is the Triclosan in my toothpaste actually dangerous?").

## Setup

1. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Add your Gemini API key:
   ```bash
   cp .env.example .env
   # then edit .env and paste your key in place of your_key_here
   ```

4. Run it:
   ```bash
   streamlit run app.py
   ```

   Streamlit will open the app in your browser (usually `http://localhost:8501`).

## Files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit app — scanning UI + chat tab |
| `edc_matcher.py` | Splits ingredient text and fuzzy-matches it against the database |
| `edc_database.json` | The EDC knowledge base (unchanged) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for your API key |

## Next ideas, if you want to keep going

- **Barcode/product lookup** — scan a barcode, pull ingredients from a product
  API (e.g. Open Food Facts / Open Beauty Facts) instead of relying on photo OCR.
- **Save scan history** — store past scans locally so users can build a
  "cabinet" of products they've checked.
- **Expand the database** — right now it covers ~30 chemicals; a scraper or
  manual expansion against a source like the EU's Endocrine Disruptor list
  would make matches more comprehensive.
- **Mobile app wrapper** — Streamlit works fine as a mobile web app, but a
  proper camera-first mobile UI (React Native / Flutter) would feel more
  native for on-the-go scanning in a store.
