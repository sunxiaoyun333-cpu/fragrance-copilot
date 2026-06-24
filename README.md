# Fragrance Copilot

An AI-assisted workspace for turning ecommerce product links and product images
into structured fragrance product profiles and TikTok marketing plans.

## Features

- Extracts product details from ecommerce links and pasted share text
- Uses product images as a fallback when a marketplace page blocks extraction
- Supports scented candles, reed diffusers, fragrance gift sets, room sprays,
  and linen sprays
- Generates bilingual product profiles, hooks, scripts, captions, and replies
- Includes optional MoneyPrinterTurbo export support

## Local Setup

1. Create a virtual environment and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add the required API keys.

3. Start the app:

   ```bash
   streamlit run app.py
   ```

The local app runs at `http://localhost:8501`.

## Environment Variables

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `TAVILY_API_KEY`
- `MONEYPRINTER_API_BASE_URL` (optional)
