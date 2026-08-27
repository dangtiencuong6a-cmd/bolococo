"""
Run the Free Fire Info backend + Discord bot together.

Starts the Flask backend (app.py) in a background thread on
http://127.0.0.1:3000, then launches the Discord bot (bot.py) which calls
that backend over HTTP.

Usage:
    python run.py

Make sure DISCORD_TOKEN is set (in .env or as an environment variable) first.
Override the backend address with FF_API_BASE_URL if you change the port.
"""

import threading

from app import app as flask_app
import bot


def _run_flask() -> None:
    # Dev server in a thread; no reloader (would spawn a child process).
    flask_app.run(host="127.0.0.1", port=3000, debug=True, use_reloader=True)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    print("[*] Flask backend starting on http://127.0.0.1:3000 (background thread)")
    # bot.run blocks forever, driving the Discord gateway on the main thread.
    bot.bot.run(bot.DISCORD_TOKEN)
