# AIRISE Futures Trading Monitor

Dashboard Streamlit untuk melihat data futures dan simulasi trading. Entry point aplikasi adalah `app.py`.

> **Penting:** GitHub Pages hanya melayani situs statis dan tidak menjalankan aplikasi Python/Streamlit. Jalankan lokal, gunakan Codespaces, atau deploy ke Streamlit Community Cloud.

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

Lalu buka `http://localhost:8501`. Jika Streamlit tidak muncul, periksa error di terminal dan pastikan port 8501 tidak dipakai proses lain.

## GitHub Codespaces

Dependencies di-install dari `requirements.txt`. Atur `AIRISE_LOGIN_USERNAME` dan `AIRISE_LOGIN_PASSWORD` di Codespaces Secrets, lalu jalankan:

```bash
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Buka tab **Ports**, pastikan port **8501** diteruskan, lalu klik **Open in Browser**.

## Streamlit Community Cloud

1. Buat app dari repository ini di Streamlit Community Cloud.
2. Atur **Main file path** ke `app.py`.
3. Di **App settings → Secrets**, tambahkan:

```toml
AIRISE_LOGIN_USERNAME = "nama_login_anda"
AIRISE_LOGIN_PASSWORD = "password_kuat_anda"
```

4. Simpan Secrets, lalu reboot/redeploy app. Buka URL yang diberikan Streamlit Cloud.

## Keamanan

Jangan commit token Telegram, API key/secret exchange, atau file `.env`. Jika token pernah dipublikasikan, cabut dan buat token baru; menghapus token dari versi terbaru tidak menghapusnya dari riwayat Git. Aplikasi ini bukan nasihat keuangan.
