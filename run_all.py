import threading
import subprocess
import time

def run_telegram_bot():
    subprocess.run(["python", "telegram_bot.py"])

def run_streamlit():
    subprocess.run(["streamlit", "run", "app.py"])

if __name__ == "__main__":
    # Jalankan di thread terpisah
    bot_thread = threading.Thread(target=run_telegram_bot)
    web_thread = threading.Thread(target=run_streamlit)
    
    bot_thread.start()
    time.sleep(2)  # Tunggu bot start
    web_thread.start()
    
    bot_thread.join()
    web_thread.join()