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
python -m streamlit run app.py
```

Terminal akan menampilkan URL; buka `http://localhost:8501`. Jika aplikasi berjalan di Codespaces, buka tab **Ports**, pastikan port **8501** berstatus **Forwarded**, lalu klik **Open in Browser**. Jangan hanya membuka file Python di editor.

Jika Streamlit tidak muncul, lihat pesan error di terminal. Coba `python -m pip install -r requirements.txt`, lalu restart dengan `python -m streamlit run app.py`. Pastikan port 8501 tidak dipakai proses lain.

## GitHub Codespaces

Dependencies di-install dari `requirements.txt`. Atur `AIRISE_LOGIN_USERNAME` dan `AIRISE_LOGIN_PASSWORD` di Codespaces Secrets, lalu restart Codespace. Jika server tidak mulai otomatis, jalankan di terminal:

```bash
python -m streamlit run app.py
```

Buka port **8501** dari tab **Ports**. Konfigurasi `.streamlit/config.toml` mengikat server ke `0.0.0.0:8501` agar dapat di-forward.

## Streamlit Community Cloud

Pilih repository ini dan set **Main file path** ke `app.py`. Tambahkan dua nilai berikut di **App settings → Secrets**, lalu klik **Reboot app**:

```toml
AIRISE_LOGIN_USERNAME = "nama_login_anda"
AIRISE_LOGIN_PASSWORD = "password_kuat_anda"
```

## Telegram bot (opsional)

Jalankan terpisah dari dashboard. Atur `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` sebagai environment variables/Secrets, lalu jalankan `python telegram_bot.py`. Jangan masukkan kredensial ke Git.

## Keamanan

Jangan commit token Telegram, API key/secret exchange, atau file `.env`. Token Telegram yang pernah terlanjur dipublikasikan di repository harus segera dicabut/dibuat ulang lewat BotFather. Mengganti isi file di commit terbaru tidak menghapus token dari riwayat Git.

Koneksi trading real dapat mengirim order sungguhan. Mulai dari mode demo dan jangan berikan izin withdrawal pada API key. Aplikasi ini bukan nasihat keuangan.
