# Futures Trading Bot Monitor PRO

A Streamlit-based dashboard for monitoring Gate.io futures markets and simulating long/short trades.

## Setup

1. Create a Python virtual environment (recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Run locally

```bash
streamlit run app.py --server.address 0.0.0.0
```

## Deploy online

This app is ready for Streamlit Cloud:

1. Push the project to GitHub.
2. Open Streamlit Cloud.
3. Create a new app from the repository.
4. Set the main file to `app.py`.
5. Deploy.

## Notes

- The app uses `ccxt` to fetch Gate.io market data.
- If the live market data fails, Streamlit will display an error and fallback is limited to cached symbols.
- Update `app.py` to adjust symbol list, timeframes, or indicator settings.
## logo
letakkan file logo PNG kamu di sini dengan nama: airise_logo.png