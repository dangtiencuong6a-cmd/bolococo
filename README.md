# Free Fire Info Site — Official Dynamic Media Edition (v2.0.0)

[![Version](https://img.shields.io/badge/version-2.0.0-orange.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Deploy to Vercel](https://vercel.com/button)](https://vercel.com/import/project?template=https://github.com/refatbd/FreeFireInfoSite)

A Flask-based Free Fire player information API and web application. This project generates dynamic player profile banners and avatars directly from official Garena Free Fire CDN assets (`bannerId` and `headPic`) with full Unicode character support and server-side image processing.

**Developer:** [refatbd](https://github.com/refatbd)  
**GitHub Repository:** [https://github.com/refatbd/FreeFireInfoSite](https://github.com/refatbd/FreeFireInfoSite)

---

## Key Features

- **Official Garena CDN Integration**: Automatically downloads numeric ASTC item textures from official Garena CDNs (`dl-tata.freefireind.in` & `dl.tata.freefiremobile.com`).
- **Native ASTC Texture Decoder**: Server-side decoding of 2D ASTC textures using `texture2ddecoder` and Pillow, rendering high-definition, upright WebP banners and avatars.
- **Full Unicode Character Fallback**: Comprehensive character-level font stack fallback (`NotoSans`, `NotoSansCherokee`, `NotoSansSC`, `NotoSansMath`, `NotoSansSymbols`, `Microsoft Himalaya`, `Segoe UI Symbol`) renders all Free Fire nicknames containing Cherokee, CJK, Tibetan, Math symbols, and special characters cleanly without missing glyph boxes (`🗙`).
- **Gameskinbo-Style Clean Layout**: 4:1 aspect ratio profile card with a 3px solid white square avatar border, unblurred background graphics, and clean text layout (`Lvl. XX`).
- **Multi-Region Support**: Full support for `BD`, `IND`, `SG`, `VN`, `TH`, `BR`, `US`, `NA`, `SAC`, `ID`, `RU`, `TW`, `ME`, `PK`, `CIS`, `EUROPE`.

---

## Requirements & System Dependencies

### System Requirements
- **Python**: `3.10` or higher (`3.10`, `3.11`, `3.12`, `3.14`)
- **OS**: Windows, Linux, or macOS

### Python Dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---|---|---|
| `Flask` | `>=3.0.0` | Web framework and routing |
| `flask-cors` | `>=4.0.0` | Cross-Origin Resource Sharing (CORS) |
| `httpx` | `>=0.27.0` | Async & sync HTTP client for API & Garena CDN requests |
| `Pillow` | `>=10.0.0` | Server-side image processing and WebP compositing |
| `texture2ddecoder` | `>=1.0.0` | Native decoder for Free Fire 2D ASTC textures |
| `protobuf` | `>=4.25.0` | Protobuf serialization & deserialization |
| `pycryptodome` | `>=3.20.0` | AES-CBC encryption/decryption for Garena protocols |
| `cachetools` | `>=5.3.0` | In-memory TTL caching for accounts & rendered WebP media |

---

## Getting Started

### Clone the Repository

To clone the repository, run the following command:

```bash
git clone https://github.com/refatbd/FreeFireInfoSite.git
cd FreeFireInfoSite
```

### Deploy via Vercel

You can deploy the project using the button below:

[![Deploy to Vercel](https://vercel.com/button)](https://vercel.com/import/project?template=https://github.com/refatbd/FreeFireInfoSite)

---

## Installation & Local Setup

```bash
# Create a virtual environment
python -m venv .venv
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**Linux / macOS:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open your browser at `http://127.0.0.1:5000`.

---

## API Endpoints & Documentation

### 1. Player Info JSON Endpoint

```http
GET /player-info?region=BD&uid=4422076728
```

#### Example JSON Response

```json
{
  "basicInfo": {
    "accountId": "4422076728",
    "nickname": "ᴛᴀʙᴀssᴜᴍ♡ʀ",
    "level": 67,
    "liked": 9196,
    "region": "BD",
    "createAt": "1637316422",
    "lastLoginAt": "1784889557",
    "rank": 313,
    "rankingPoints": 2348,
    "csRank": 324,
    "csRankingPoints": 223,
    "badgeCnt": 87,
    "headPic": 902050009,
    "bannerId": 901000116,
    "badgeId": 1001000098,
    "pinId": 910031004,
    "releaseVersion": "OB54",
    "seasonId": 52,
    "showBrRank": true,
    "showCsRank": true,
    "title": 904090024,
    "exp": 2121988
  },
  "clanBasicInfo": {
    "clanId": "3015421980",
    "clanName": "CRMNAL  SLDRS",
    "clanLevel": 5,
    "memberNum": 45,
    "capacity": 50
  },
  "captainBasicInfo": {
    "accountId": "4641089868",
    "nickname": "MR.REFAT",
    "level": 65
  },
  "socialInfo": {
    "signature": "Welcome to my profile!",
    "language": "English",
    "gender": "Female"
  },
  "mediaInfo": {
    "bannerUrl": "/api/banner/banner_4422076728.webp?region=BD&v=v7-901000116-902050009-1784900505",
    "avatarUrl": "/api/avatar/avatar_4422076728.webp?region=BD&v=v7-901000116-902050009-1784900505",
    "policy": "official-free-fire-cdn-only-with-local-fallback"
  }
}
```

---

### 2. Dynamic WebP Media Endpoints

```http
GET /api/banner/banner_<UID>.webp?region=<REGION>
GET /api/avatar/avatar_<UID>.webp?region=<REGION>
```

#### Local URLs Example

```text
http://127.0.0.1:5000/api/banner/banner_4422076728.webp?region=BD
http://127.0.0.1:5000/api/avatar/avatar_4422076728.webp?region=BD
```

---

## Asset Security Policy

`official_media.py` does not accept arbitrary remote URLs. It constructs paths strictly from validated numeric Free Fire item IDs and restricts HTTPS downloads to allowlisted Garena CDN hosts:

```text
dl-tata.freefireind.in
dl.tata.freefiremobile.com
```

Asset path template:

```text
/live/ABHotUpdates/IconCDN/android/<ITEM_ID>_rgb.astc
```

---

## Discord Bot

The Discord bot (`bot.py`) is a **thin HTTP client** that talks to the Flask
backend (`app.py`) — it does not scrape Garena itself. `app.py` is the data
engine (player JSON + pre-rendered WebP banner/avatar); the bot just forwards
that over HTTP and posts it to Discord.

```
Discord ──► bot.py ──HTTP──► app.py (Flask, http://127.0.0.1:5000)
                                ├─ /player-info     (player JSON)
                                ├─ /api/banner/...  (WebP banner)
                                ├─ /api/avatar/...  (WebP avatar)
                                └─ /api/regions     (region list)
```

**Commands**

| Command | Description |
|---|---|
| `/player <uid> [region]` | Look up a Free Fire profile. Fetches the JSON + WebP banner/avatar from the backend and posts them with key stats. `region` is optional and auto-detected. Also works as `!player`. |
| `/regions` | List supported region codes and aliases (fetched from the backend). |
| `/ffping` | Confirm the bot is online (shows gateway latency). |

**Run it** — the backend must be running first:

```bash
pip install -r requirements.txt          # discord.py + httpx + python-dotenv
export DISCORD_TOKEN="your-bot-token"     # or copy .env.example -> .env

# Terminal 1 — the data backend:
python app.py
# Terminal 2 — the bot:
python bot.py
```

Or start both together with one command:

```bash
python run.py
```

Point the bot at a different backend with the `FF_API_BASE_URL` env var
(default `http://127.0.0.1:5000`). If the backend is down, `/player` and
`/regions` tell you to start `python app.py` (or `python run.py`) first.

Create a bot and copy its token from <https://discord.com/developers/applications>.
The bot needs only outbound access to the backend; the backend needs the same
Garena API/CDN access as the web app (it warms + refreshes regional JWT tokens
on startup, like the Flask site).

---

## Testing

Run the unit test suite:

```bash
python -m pytest
```

---

## Developer & Credits

- **Developer:** [refatbd](https://github.com/refatbd)
- **GitHub Repository:** [https://github.com/refatbd/FreeFireInfoSite](https://github.com/refatbd/FreeFireInfoSite)

---

## Disclaimer

This is an unofficial community project and is not affiliated with or endorsed by Garena. Use in accordance with Garena/Free Fire terms of service and local privacy regulations.
