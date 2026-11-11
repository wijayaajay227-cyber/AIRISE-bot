# AIRISE Futures Trading Monitor

Dashboard Streamlit untuk melihat data futures dan simulasi trading. Entry point aplikasi adalah `app.py`.

## Jalankan lokal

Butuh Python 3.10+.

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:AIRISE_LOGIN_USERNAME = "nama_login_anda"
$env:AIRISE_LOGIN_PASSWORD = "password_kuat_anda"
python -m streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export AIRISE_LOGIN_USERNAME="nama_login_anda"
export AIRISE_LOGIN_PASSWORD="password_kuat_anda"
python -m streamlit run app.py --server.address 0.0.0.0
```

Buka URL yang ditampilkan Streamlit, biasanya `http://localhost:8501`. Gunakan kredensial yang sudah Anda konfigurasi di atas. Jika perintah `streamlit` tidak ditemukan, gunakan `python -m streamlit`.

## GitHub Codespaces

Dependencies di-install dari `requirements.txt`. Atur `AIRISE_LOGIN_USERNAME` dan `AIRISE_LOGIN_PASSWORD` di Codespaces Secrets, lalu jalankan:

```bash
python -m streamlit run app.py --server.address 0.0.0.0
```

Buka port **8501**.

## Streamlit Community Cloud

Pilih repository ini dan set **Main file path** ke `app.py`. Tambahkan dua nilai berikut di **App settings → Secrets**:

```toml
AIRISE_LOGIN_USERNAME = "nama_login_anda"
AIRISE_LOGIN_PASSWORD = "password_kuat_anda"
```

## Telegram bot (opsional)

Jalankan terpisah dari dashboard. Atur `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` sebagai environment variables/Secrets, lalu jalankan `python telegram_bot.py`. Jangan masukkan kredensial ke Git.

## Keamanan

Jangan commit token Telegram, API key/secret exchange, atau file `.env`. Token Telegram yang pernah terlanjur dipublikasikan di repository harus segera dicabut/dibuat ulang lewat BotFather. Mengganti isi file di commit terbaru tidak menghapus token dari riwayat Git.

Koneksi trading real dapat mengirim order sungguhan. Mulai dari mode demo dan jangan berikan izin withdrawal pada API key. Aplikasi ini bukan nasihat keuangan.
