"""AIRISE Streamlit entry point configured for OKX only."""

import real
from support_resistance import install as install_support_resistance

# Use one exchange provider for public market data and live trading.
real.EXCHANGES = {
    "OKX": {"id": ["okx"], "options": {"defaultType": "swap"}},
}

# Add pivot-based support/resistance levels to the analysis view and chart.
install_support_resistance(real)


if __name__ == "__main__":
    real.main()
