"""AIRISE Streamlit entry point configured for OKX only."""

import os

import real
from support_resistance import install as install_support_resistance


def _get_secret(name: str) -> str:
    """Read a setting from environment variables or Streamlit Secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(real.st.secrets.get(name, ""))
    except Exception:
        return ""


# Do not ship public/default login credentials in source code.
real.LOGIN_USERNAME = _get_secret("AIRISE_LOGIN_USERNAME")
real.LOGIN_PASSWORD = _get_secret("AIRISE_LOGIN_PASSWORD")

# Use one exchange provider for public market data and live trading.
real.EXCHANGES = {
    "OKX": {"id": ["okx"], "options": {"defaultType": "swap"}},
}

# Add pivot-based support/resistance levels to the analysis view and chart.
install_support_resistance(real)


def main() -> None:
    """Start the dashboard and explain missing deployment configuration clearly."""
    if not real.LOGIN_USERNAME or not real.LOGIN_PASSWORD:
        real.st.set_page_config(page_title="AIRISE BOT Setup", page_icon="🤖")
        real.st.error("AIRISE BOT berjalan, tetapi login belum dikonfigurasi.")
        real.st.markdown(
            "Atur `AIRISE_LOGIN_USERNAME` dan `AIRISE_LOGIN_PASSWORD` di environment "
            "lokal, GitHub Codespaces Secrets, atau Streamlit Community Cloud → "
            "App settings → Secrets. Setelah itu restart/reboot aplikasi."
        )
        real.st.code(
            'AIRISE_LOGIN_USERNAME = "nama_login_anda"\n'
            'AIRISE_LOGIN_PASSWORD = "password_kuat_anda"',
            language="toml",
        )
        return
    real.main()


if __name__ == "__main__":
    main()
