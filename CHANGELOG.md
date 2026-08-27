# Changelog

All notable changes to the **Free Fire Info Site — Official Dynamic Media Edition** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-08-21

### Added
- **Server Startup Token Warmup**: Automatic asynchronous pre-warming of JWT tokens across all supported regional Free Fire clusters on local server launch (`asyncio.run(initialize_tokens())`), eliminating first-request latency.
- **Background Daemon Token Refresher**: Background thread (`start_token_refresher`) automatically refreshing regional gateway authentication tokens every 7 hours (`25200s`) to ensure zero token expiration downtime.

### Changed
- **Optimized HTTP Transport Headers**: Cleaned up manual connection management headers (`Expect: 100-continue`, `Connection: Keep-Alive`, `Accept-Encoding: gzip`) in `create_jwt` and `GetAccountInformation` for robust compatibility across proxy gateways and modern HTTP clients.
- **Protobuf & Python Compatibility**: Enhanced dependency definitions and cross-runtime compatibility with Python 3.10 through 3.14.

---

## [2.0.0] - 2026-07-24

### Added
- **Official Garena CDN Integration**: Direct binary ASTC texture downloading from Garena Icon CDN (`dl-tata.freefireind.in` & `dl.tata.freefiremobile.com`) using player `bannerId` and `headPic`.
- **Native ASTC Texture Decoder**: Server-side decoding of 2D ASTC textures using `texture2ddecoder` and PIL/Pillow.
- **Full Unicode Font Stack Fallback**: Comprehensive character-level font stack fallback (`NotoSans`, `NotoSansCherokee`, `NotoSansSC`, `NotoSansMath`, `NotoSansSymbols`, `Microsoft Himalaya`, `Segoe UI Symbol`) rendering all Free Fire nicknames containing Cherokee, CJK, Tibetan, Math symbols, and special characters cleanly without missing glyph boxes (`🗙`).
- **Gameskinbo Card Layout & Styling**: 4:1 aspect ratio profile card with a 3px solid white square avatar frame, unblurred background graphics, and clean text layout (`Lvl. XX`).
- **Image Sharpness & Contrast Enhancement**: Automatic server-side contrast and sharpness enhancement (`ImageEnhance.Sharpness`) for Garena CDN textures.
- **Vercel & Serverless Support**: Added `vercel.json` and `wsgi.py` for one-click Vercel deployment.

### Changed
- Removed third-party external image composition dependencies.
- Replaced static sample avatar images with dynamic server-side generated WebP media endpoints (`/api/banner/banner_<UID>.webp` and `/api/avatar/avatar_<UID>.webp`).

### Fixed
- Fixed 180° texture orientation and bounding box trimming for Free Fire avatar icons.
- Fixed invisible Hangul filler (`\u3164`) and Braille blank spacing in guild names.

---

## [1.0.0] - 2026-07-01

### Added
- Initial release of Free Fire Info Checker with multi-region protobuf decryption.
- Player stats lookup (`level`, `likes`, `rank`, `guild`, `BR/CS points`).
