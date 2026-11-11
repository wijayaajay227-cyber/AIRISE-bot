"""AIRISE Streamlit entry point configured for OKX only."""

import real

# Use one exchange provider for public market data and live trading.
real.EXCHANGES = {
    "OKX": {"id": ["okx"], "options": {"defaultType": "swap"}},
}


if __name__ == "__main__":
    real.main()
