"""
Run the Free Fire Info backend + Discord bot together.
Starts the Flask backend in a background thread, then launches the Discord bot.
"""
import os
import threading
from app import app as flask_app
import bot

def _run_flask() -> None:
    # ✅ SỬA: Dùng 0.0.0.0 + PORT từ biến môi trường (phù hợp Render + local)
    HOST = os.getenv('WEB_HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 3000))
    flask_app.run(host=HOST, port=PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    
    HOST = os.getenv('WEB_HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 3000))
    print(f"[*] Flask backend starting on http://{HOST}:{PORT} (background thread)")
    
    # ✅ Khởi động Discord bot trên luồng chính
    bot_token = getattr(bot, 'BOT_TOKEN', None) or getattr(bot, 'DISCORD_TOKEN', None)
    if not bot_token:
        print("[!] LỖI: Chưa đặt BOT_TOKEN / DISCORD_TOKEN!")
        print("    Hãy thêm vào file .env hoặc biến môi trường trên Render.")
        exit(1)
    
    print("[*] Discord bot đang khởi động...")
    bot.bot.run(bot_token)
