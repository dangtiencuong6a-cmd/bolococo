"""
Free Fire Info — Bot Discord (phiên bản client HTTP)
======================================================

Bot là một lớp giao diện Discord mỏng. Nó KHÔNG tự gọi API Garena,
mà giao tiếp với backend Flask (``app.py``) qua HTTP, rồi hiển thị
toàn bộ dữ liệu trả về kèm ảnh banner/avatar đã render sẵn (WebP).

Kiến trúc
---------
    Discord  ──►  bot.py  ──HTTP──►  app.py  (Flask, http://127.0.0.1:5000)
                                        │
                                        ├─ /player-info      (JSON người chơi)
                                        ├─ /api/banner/...   (ảnh banner WebP)
                                        ├─ /api/avatar/...   (ảnh avatar WebP)
                                        └─ /api/regions      (danh sách vùng)

Chạy
----
    python app.py          # khởi backend (localhost:5000)
    python bot.py          # khởi bot (terminal khác)

Hoặc chạy cả hai bằng một lệnh:
    python run.py

Trỏ bot sang backend khác bằng biến môi trường FF_API_BASE_URL.

Tác giả: refatbd (https://github.com/refatbd)
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import os
import re
from typing import Optional, Tuple

import httpx
import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("ff-discord-bot")

# --- Nạp .env (để DISCORD_TOKEN hoạt động mà không cần export thủ công) --------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_env() -> None:
    """Điền os.environ từ file .env.

    Ưu tiên python-dotenv nếu có, nếu không dùng bộ phân tích tích hợp sẵn.
    Tìm cạnh script trước, sau đó là thư mục hiện tại (CWD).
    """
    candidates = (os.path.join(BASE_DIR, ".env"), ".env")
    try:
        from dotenv import load_dotenv  # type: ignore

        for path in candidates:
            if os.path.exists(path):
                load_dotenv(path)
                return
    except Exception:  # dotenv chưa cài -> dùng fallback bên dưới
        pass

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip()
                    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                        val = val[1:-1]  # bỏ dấu ngoặc quanh giá trị
                    os.environ.setdefault(key, val)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Không thể đọc %s: %s", path, exc)


_load_env()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
if not DISCORD_TOKEN:
    raise SystemExit(
    "❌ Không tìm thấy DISCORD_TOKEN.\n"
    "  • Tạo file .env từ .env.example và điền token, HOẶC\n"
    "  • export DISCORD_TOKEN=\"token-cua-ban\"\n"
    "Tạo bot tại https://discord.com/developers/applications"
)

# Nơi đặt backend Flask. Ghi đè bằng FF_API_BASE_URL nếu cần.
FF_API_BASE_URL = os.getenv("FF_API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

# Không cần quyền truy cập (privileged intent) nào cho lệnh slash/prefix.
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# --------------------------------------------------------------------------- #
# Từ điển tên vật phẩm (giải mã ID vật phẩm từ file item_names.txt)
# --------------------------------------------------------------------------- #
_ITEM_NAMES: Optional[dict] = None
_ITEM_NAMES_ERR = False


def get_item_names() -> dict:
    """Nạp bảng ánh xạ {id: tên_vật_phẩm} từ item_names.txt (chỉ một lần)."""
    global _ITEM_NAMES, _ITEM_NAMES_ERR
    if _ITEM_NAMES is not None or _ITEM_NAMES_ERR:
        return _ITEM_NAMES or {}

    path = os.path.join(BASE_DIR, "item_names.txt")
    if not os.path.exists(path):
        _ITEM_NAMES_ERR = True
        LOGGER.warning("Không tìm thấy item_names.txt tại %s", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            arr = json.load(fh)
        names: dict = {}
        for obj in arr:
            try:
                names[int(obj["id"])] = obj.get("name_text") or obj.get("name") or ""
            except (KeyError, TypeError, ValueError):
                continue
        _ITEM_NAMES = names
        LOGGER.info("Đã nạp %d tên vật phẩm từ %s", len(names), path)
    except Exception as exc:  # noqa: BLE001
        _ITEM_NAMES_ERR = True
        LOGGER.warning("Lỗi nạp item_names.txt: %s", exc)
        return {}
    return _ITEM_NAMES or {}


def resolve_item(item_id) -> str:
    """Trả về 'Tên vật phẩm (ID xxx)', hoặc 'ID xxx' nếu không tìm thấy tên."""
    if item_id in (None, "", 0):
        return "—"
    names = get_item_names()
    try:
        name = names.get(int(item_id))
    except (TypeError, ValueError):
        name = None
    if name:
        return f"{name} (ID {item_id})"
    return f"ID {item_id}"


# Dịch nhãn các phần (section) cấp cao nhất.
SECTION_LABELS = {
    "basicInfo": "Thông tin cơ bản",
    "clanBasicInfo": "Quân đoàn (Clan)",
    "socialInfo": "Xã hội",
    "petInfo": "Thú nuôi (Pet)",
    "creditInfo": "Tín dụng",
    "profileInfo": "Hồ sơ",
    "captainBasicInfo": "Đội trưởng",
    "creditScoreInfo": "Điểm tín dụng",
    "diamondCostRes": "Kim cương đã tiêu",
    "externalIconInfo": "Biểu tượng ngoài",
    "socialHighLightsWithBasicInfo": "Nổi bật xã hội",
    "weaponSkinShows": "Skin vũ khí",
    "mediaInfo": "Media",
}

# Dịch nhãn các trường phổ biến.
LABELS = {
    "accountId": "UID tài khoản",
    "nickname": "Tên người chơi",
    "level": "Cấp độ",
    "exp": "Kinh nghiệm (EXP)",
    "expPercent": "Phần trăm EXP",
    "liked": "Lượt thích",
    "likedPercent": "Phần trăm thích",
    "rank": "Mã rank BR",
    "rankingPoints": "Hạng (BR)",
    "csRank": "Mã rank CS",
    "csRankingPoints": "Hạng (CS - sao)",
    "badgeCnt": "Số huy hiệu",
    "badgeId": "Huy hiệu",
    "createAt": "Ngày tạo",
    "lastLoginAt": "Đăng nhập cuối",
    "region": "Vùng",
    "headPic": "Ảnh đại diện",
    "bannerId": "Banner",
    "title": "Danh hiệu",
    "pinId": "Ghim",
    "petId": "Thú nuôi",
    "bpLevel": "Cấp Battle Pass",
    "bpExp": "EXP Battle Pass",
    "clanName": "Tên quân đoàn",
    "clanLevel": "Cấp quân đoàn",
    "clanId": "ID quân đoàn",
    "memberNum": "Thành viên quân đoàn",
    "capacity": "Sức chứa quân đoàn",
    "signature": "Chữ ký",
    "role": "Vai trò",
    "maxRank": "Hạng cao nhất (BR)",
    "csMaxRank": "Hạng cao nhất (CS)",
    "showBrRank": "Hiển thị hạng BR",
    "evoCrystal": "Tinh thể Evo",
    "creditScore": "Điểm tín dụng",
    "accountPrefers": "Tùy chọn tài khoản",
    "accountType": "Loại tài khoản",
    "showCsRank": "Hiển thị hạng CS",
    "releaseVersion": "Phiên bản game",
    "seasonId": "Mùa giải",
    "weaponSkinShows": "Skin vũ khí",
    "bpLevel": "Cấp Battle Pass",
    "bpExp": "EXP Battle Pass",
    "modePrefer": "Chế độ ưu tiên",
    "rankShow": "Hiển thị hạng",
    "gender": "Giới tính",
    "language": "Ngôn ngữ",
}


def _humanize(key: str) -> str:
    """Tách camelCase/snake_case thành nhãn dễ đọc (hỗ trợ tiếng Việt phía sau)."""
    # Chèn khoảng trắng trước mỗi chữ hoa (trừ chữ đầu) để tách camelCase.
    spaced = re.sub(r"(?<!^)([A-Z])", r" \1", key)
    parts = [p for p in re.split(r"[ _]+", spaced) if p]
    return " ".join(p.capitalize() for p in parts)


def _label(key: str) -> str:
    return LABELS.get(key, _humanize(key))


def _fmt_ts(ts) -> str:
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError):
        return "—"


# Bảng hạng BR (Free Fire) — nguồn: bảng xếp hạng tiếng Việt của user.
# (tên VN, tên EN, RP tối thiểu, RP tối đa không tính, số bậc phụ)
# BR: trường `rankingPoints` là Điểm Rank (RP) quyết định hạng;
#     trường `rank` là mã nội bộ không dùng để tra.
RANK_TIERS = [
    ("Đồng", "Bronze", 1000, 1300, 3),
    ("Bạc", "Silver", 1300, 1600, 3),
    ("Vàng", "Gold", 1600, 2100, 4),
    ("Bạch Kim", "Platinum", 2100, 2750, 5),
    ("Kim Cương", "Diamond", 2750, 3500, 5),
    ("Huyền Thoại", "Heroic", 3500, 4900, 2),
    ("Huyền Thoại CC", "Elite Heroic", 4900, 7100, 3),
    ("Cao Thủ", "Master", 7100, 9000, 2),
    ("Cao Thủ Cao Cấp", "Elite Master", 9000, 10000, 3),
]
_ROMAN = ["", "I", "II", "III", "IV", "V", "VI"]


def _rank_from_rp(rp) -> str:
    """Quy đổi Điểm Rank (RP) sang tên hạng tiếng Việt + bậc phụ (I-VI)."""
    try:
        rp = int(rp)
    except (TypeError, ValueError):
        return "—"
    if rp >= 10000:
        return "Thách Đấu (Grandmaster)"
    for vn, en, lo, hi, divs in RANK_TIERS:
        if lo <= rp < hi:
            if divs <= 1:
                return f"{vn} ({en})"
            frac = (rp - lo) / (hi - lo) if hi > lo else 0
            d = max(1, min(divs, int(frac * divs) + 1))
            roman = _ROMAN[d]
            return f"{vn} {roman} ({en} {roman})"
    return "Đồng I (Bronze I)"  # dưới mức Bronze


# Bảng hạng CS (Clash Squad) — hệ SAO, không phải RP.
# Nguồn: bảng xếp hạng tiếng Việt của user.
# `csRankingPoints` là TỔNG SỐ SAO (không phải RP). Quy đổi tổng sao sang hạng.
# (tên VN, tên EN, sao tối thiểu, sao tối đa không tính, số bậc phụ)
CS_STAR_TIERS = [
    ("Đồng", "Bronze", 1, 4, 3),          # 1-3 sao (3 bậc)
    ("Bạc", "Silver", 4, 7, 4),           # 4-6 sao (4 bậc)
    ("Vàng", "Gold", 7, 11, 5),           # 7-10 sao (5 bậc)
    ("Bạch Kim", "Platinum", 11, 16, 6),  # 11-15 sao (6 bậc)
    ("Kim Cương", "Diamond", 16, 21, 7),  # 16-20 sao (7 bậc)
    ("Huyền Thoại", "Heroic", 21, 25, 4), # 21-24 sao (is_star=1)
    ("Huyền Thoại CC", "Elite Heroic", 25, 50, 1),   # 25-49 sao
    ("Cao Thủ", "Master", 50, 100, 1),               # 50-99 sao
    ("Cao Thủ Cao Cấp", "Elite Master", 100, 1000, 1),  # 100-999 sao
]


def _rank_from_stars(stars) -> str:
    """Quy đổi TỔNG SỐ SAO CS (csRankingPoints) sang tên hạng tiếng Việt + bậc phụ."""
    try:
        stars = int(stars)
    except (TypeError, ValueError):
        return "—"
    if stars >= 1000:
        return "Thách Đấu (Grandmaster)"
    for vn, en, lo, hi, divs in CS_STAR_TIERS:
        if lo <= stars < hi:
            if divs <= 1:
                return f"{vn} ({en})"
            frac = (stars - lo) / (hi - lo) if hi > lo else 0
            d = max(1, min(divs, int(frac * divs) + 1))
            roman = _ROMAN[d]
            return f"{vn} {roman} ({en} {roman})"
    return "Đồng I (Bronze I)"  # 0 sao hoặc dưới mức Bronze


def _fmt_value(leaf_key: str, value) -> str:
    if value is None or value == "":
        return "—"
    # Boolean trước, tránh nhầm với int (bool là lớp con của int).
    if isinstance(value, bool):
        return "Có" if value else "Không"

    # Chuẩn hoá số dạng chuỗi (protobuf JSON thường trả int64 thành string,
    # ví dụ createAt/lastLoginAt/rankingPoints), để các bước dưới xử lý nhất quán.
    num = None
    if isinstance(value, str) and value.lstrip("-").isdigit():
        try:
            num = int(value)
        except ValueError:
            num = None
    elif isinstance(value, (int, float)):
        num = value

    # Hạng BR: `rankingPoints` là Điểm Rank (RP) -> tra bảng RP.
    if leaf_key == "rankingPoints":
        tier = _rank_from_rp(value if num is None else num)
        return f"{tier} • {int(num):,} RP" if num is not None else tier
    # Hạng CS: `csRankingPoints` là TỔNG SỐ SAO -> tra thang sao.
    if leaf_key == "csRankingPoints":
        tier = _rank_from_stars(value if num is None else num)
        return f"{tier} • {int(num):,} ★" if num is not None else tier

    # ID vật phẩm (headPic, bannerId, title, badgeId, pinId, petId, skinId, …,
    # kể cả id nằm trong danh sách như weaponSkinShows) -> giải mã thành tên.
    if _is_item_id(leaf_key, value):
        return resolve_item(value)

    # Dấu thời gian -> ngày giờ cụ thể.
    # Công thức: lấy giá trị, nếu > 10^10 thì là mili-giây (chia 1000),
    # rồi đổi từ epoch sang giờ địa phương: datetime.fromtimestamp(ts).
    if num is not None and (
        leaf_key in TIMESTAMP_FIELDS
        or (leaf_key and leaf_key.lower().endswith("at") and abs(num) > 1_000_000_000)
    ):
        ts = num
        if ts > 10_000_000_000:  # mili-giây -> giây
            ts = ts / 1000
        return _fmt_ts(ts)

    if num is not None:
        try:
            return f"{int(num):,}"
        except (TypeError, ValueError):
            return str(value)
    s = str(value)
    return s if s else "—"


# Các trường là dấu thời gian (giây) cần định dạng ngày giờ.
TIMESTAMP_FIELDS = {"createAt", "lastLoginAt", "timestamp", "createAtField", "lastLoginAtField"}


def flatten_player(data: dict) -> list:
    """Giải toàn bộ JSON thành danh sách (section, nhãn, giá_trị)."""
    rows: list = []
    if not isinstance(data, dict):
        return rows

    for section_key, section_val in data.items():
        if section_key == "mediaInfo":
            continue  # bỏ qua URL media do backend tự thêm
        sec_label = SECTION_LABELS.get(section_key, _humanize(section_key))
        if isinstance(section_val, (dict, list)):
            # raw_prefix giữ nguyên khoá API (để nhận diện ID/timestamp),
            # display_prefix là nhãn tiếng Việt dùng để hiển thị.
            _walk(sec_label, section_val, section_key, "", rows)
        else:
            rows.append((sec_label, _label(section_key), _fmt_value(section_key, section_val)))
    return rows


def _walk(sec_label, node, raw_prefix, display_prefix, rows) -> None:
    if isinstance(node, dict):
        if not node:
            rows.append((sec_label, display_prefix or "—", "—"))
            return
        for k, v in node.items():
            new_raw = f"{raw_prefix}.{k}" if raw_prefix else k
            new_disp = f"{display_prefix}.{_label(k)}" if display_prefix else _label(k)
            _walk(sec_label, v, new_raw, new_disp, rows)
    elif isinstance(node, list):
        if not node:
            rows.append((sec_label, display_prefix or "—", "(rỗng)"))
            return
        for i, v in enumerate(node):
            new_raw = f"{raw_prefix}[{i}]"
            new_disp = f"{display_prefix}[{i}]"
            _walk(sec_label, v, new_raw, new_disp, rows)
    else:
        raw_key = raw_prefix.rsplit(".", 1)[-1] if "." in raw_prefix else raw_prefix
        rows.append((sec_label, display_prefix or "—", _fmt_value(raw_key, node)))


# --------------------------------------------------------------------------- #
# HTTP client tới backend Flask
# --------------------------------------------------------------------------- #
async def _api_get(path: str, params: Optional[dict] = None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await client.get(f"{FF_API_BASE_URL}{path}", params=params)


async def fetch_player(uid: str, region: Optional[str]) -> Tuple[Optional[dict], Optional[str]]:
    """Trả về (json_người_chơi, None) khi thành công hoặc (None, lỗi) khi thất bại."""
    params = {"uid": uid}
    if region:
        params["region"] = region
    try:
        resp = await _api_get("/player-info", params)
    except (httpx.ConnectError, httpx.ConnectTimeout, OSError) as exc:
        return None, f"BACKEND_DOWN:{exc}"

    if resp.status_code == 200:
        try:
            return resp.json(), None
        except Exception:  # noqa: BLE001
            return None, f"{resp.status_code}:Phản hồi không phải JSON hợp lệ."

    try:
        msg = resp.json().get("error", resp.text)
    except Exception:
        msg = resp.text
    return None, f"{resp.status_code}:{msg}"


async def fetch_media(kind: str, uid: str, region: Optional[str]) -> Optional[bytes]:
    """Lấy ảnh WebP (banner/avatar) đã render, trả về bytes hoặc None."""
    params = {}
    if region:
        params["region"] = region
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{FF_API_BASE_URL}/api/{kind}/{kind}_{uid}.webp", params=params
            )
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Lấy media thất bại %s/%s: %s", kind, uid, exc)
    return None


# --------------------------------------------------------------------------- #
# Nhận diện ID vật phẩm (mở rộng: tất cả trường tên gợi ý vật phẩm đều được thử giải mã)
# --------------------------------------------------------------------------- #
_ITEM_RE = re.compile(
    r"(headpic|bannerid|\btitle\b|badgeid|pinid|petid|skinid|frameid|avatarid|outfitid|emoteid|weaponskin|headicon|petinfo|skin|avatar|frame|emote|outfit|pin\b)",
    re.IGNORECASE,
)
# ID nội bộ KHÔNG phải vật phẩm trong catalog -> không thử giải mã.
_NON_ITEM_IDS = {
    "accountid", "clanid", "captainid", "seasonid",
    "accounttype", "accountprefers", "maxrank", "csmaxrank",
    "rank", "csrank",
}


def _is_item_id(raw_key: str, value) -> bool:
    """Có phải ID vật phẩm Free Fire không (dựa vào tên trường + giá trị)."""
    if value is None or value == "":
        return False
    s = str(value).strip()
    if not s or s == "0":
        return False
    low = raw_key.lower()
    if low in _NON_ITEM_IDS:
        return False
    if not _ITEM_RE.search(low):
        return False
    # Chỉ giải mã khi giá trị là số nguyên (int hoặc chuỗi toàn số).
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return True
    return False


# --------------------------------------------------------------------------- #
# Giao diện Discord: dropdown chọn mục + nút phân trang ◀ X/N ▶
# --------------------------------------------------------------------------- #
PAGE_SIZE = 20

# Khi chọn một mục, các trường này sẽ xếp lên đầu trang 1.
SECTION_PRIORITY = {
    "Thông tin cơ bản": [
        "UID tài khoản", "Tên người chơi", "Cấp độ",
        "Hạng (BR)", "Mã rank BR", "Hạng (CS)", "Mã rank CS",
        "Hạng cao nhất (BR)", "Hạng cao nhất (CS)",
        "Vùng", "Ngày tạo", "Đăng nhập cuối",
        "Lượt thích", "Số huy hiệu", "Danh hiệu", "Banner", "Ảnh đại diện", "Ghim",
    ],
    "Quân đoàn (Clan)": [
        "Tên quân đoàn", "Cấp quân đoàn", "Thành viên quân đoàn", "Sức chứa quân đoàn",
        "ID quân đoàn",
    ],
}


def _group_rows(rows):
    """Nhóm các dòng theo mục; trong mục sắp xếp theo SECTION_PRIORITY."""
    grouped: dict = {}
    for sec, label, val in rows:
        grouped.setdefault(sec, []).append((label, val))
    for sec, items in grouped.items():
        prio = SECTION_PRIORITY.get(sec)
        if prio:
            index = {lbl: i for i, lbl in enumerate(prio)}

            def _key(item, idx=index):
                lbl = item[0]
                return (0, idx[lbl]) if lbl in idx else (1, 0)
            items.sort(key=_key)
        grouped[sec] = items
    return grouped


def _page_count(n: int) -> int:
    return max(1, -(-n // PAGE_SIZE))  # ceil(n / PAGE_SIZE)


def make_view_embed(
    meta: dict, section: str, page: int, section_rows: list, total_rows: int
) -> discord.Embed:
    """Dựng embed cho trang hiện tại của mục được chọn."""
    nickname = meta.get("nickname", "Unknown Player")
    safe_uid = meta.get("uid", "?")
    safe_region = meta.get("region", "?")
    pages = _page_count(len(section_rows))
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_rows = section_rows[start:end]

    embed = discord.Embed(
        title=nickname,
        description=(
            f"Hồ sơ Free Fire • Vùng **{safe_region}** • UID **{safe_uid}**\n"
            f"📂 Mục: **{section}** • Trang **{page + 1}/{pages}** • "
            f"Tổng **{total_rows}** trường từ API"
        ),
        color=0xF59E0B,
    )
    for label, val in page_rows:
        embed.add_field(name=label[:256], value=val[:1024], inline=len(val) <= 40)

    # Giữ banner/avatar xuyên suốt các trang (URL gắn với file đính kèm).
    if meta.get("banner_url"):
        embed.set_image(url=meta["banner_url"])
    if meta.get("avatar_url"):
        embed.set_thumbnail(url=meta["avatar_url"])

    if end < len(section_rows):
        embed.set_footer(
            text=f"Còn {len(section_rows) - end} trường nữa ở trang sau — dùng ◀ ▶ để chuyển."
        )
    else:
        embed.set_footer(
            text="Công cụ Free Fire không chính thức • dữ liệu từ API Garena"
        )
    return embed


class PlayerView(discord.ui.View):
    """Dropdown chọn mục + nút phân trang."""

    def __init__(self, grouped: dict, meta: dict, author_id: int):
        super().__init__(timeout=300)
        self.grouped = grouped
        self.meta = meta
        self.author_id = author_id
        self.sections = list(grouped.keys())
        self.current_section = self.sections[0]
        self.page = 0
        self._rebuild_components()

    # ---- helpers ---------------------------------------------------------- #
    def _rebuild_components(self):
        self.clear_items()
        options = []
        for sec in self.sections:
            n = len(self.grouped[sec])
            options.append(
                discord.SelectOption(
                    label=f"{sec} ({n})",
                    description=("Đang xem" if sec == self.current_section else "Chuyển sang mục này")[:100],
                    value=sec,
                    default=(sec == self.current_section),
                )
            )
        sel = discord.ui.Select(
            placeholder="Chọn mục để xem…",
            min_values=1,
            max_values=1,
            options=options,
        )
        sel.callback = self._on_select
        self.add_item(sel)

        pages = _page_count(len(self.grouped[self.current_section]))
        prev_btn = discord.ui.Button(
            emoji="◀", style=discord.ButtonStyle.secondary, disabled=(self.page == 0)
        )
        prev_btn.callback = self._on_prev
        self.add_item(prev_btn)
        page_btn = discord.ui.Button(
            label=f"Trang {self.page + 1}/{pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )
        self.add_item(page_btn)
        next_btn = discord.ui.Button(
            emoji="▶", style=discord.ButtonStyle.secondary,
            disabled=(self.page >= pages - 1),
        )
        next_btn.callback = self._on_next
        self.add_item(next_btn)

    def _total_rows(self) -> int:
        return sum(len(v) for v in self.grouped.values())

    def _current_embed(self) -> discord.Embed:
        return make_view_embed(
            self.meta, self.current_section, self.page,
            self.grouped[self.current_section], total_rows=self._total_rows(),
        )

    async def _refresh(self, interaction: discord.Interaction):
        self._rebuild_components()
        try:
            await interaction.response.edit_message(
                embed=self._current_embed(), view=self
            )
        except discord.errors.NotFound:
            # Tin nhắn đã bị xoá -> bỏ qua.
            pass

    # ---- interaction guard ----------------------------------------------- #
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "Chỉ người đã gõ lệnh mới có thể dùng menu này.", ephemeral=True
        )
        return False

    # ---- callbacks ------------------------------------------------------- #
    async def _on_select(self, interaction: discord.Interaction):
        values = (interaction.data or {}).get("values") or []
        if values and values[0] in self.grouped:
            self.current_section = values[0]
            self.page = 0
        await self._refresh(interaction)

    async def _on_prev(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
        await self._refresh(interaction)

    async def _on_next(self, interaction: discord.Interaction):
        pages = _page_count(len(self.grouped[self.current_section]))
        if self.page < pages - 1:
            self.page += 1
        await self._refresh(interaction)

    async def on_timeout(self):
        # Khi hết 5 phút, vô hiệu hoá các thành phần.
        for child in self.children:
            child.disabled = True


# --------------------------------------------------------------------------- #
# Lệnh
# --------------------------------------------------------------------------- #
@bot.hybrid_command(
    name="player",
    description="Tra cứu hồ sơ người chơi Free Fire (banner + avatar + mọi thống kê).",
)
@app_commands.describe(
    uid="UID Free Fire (5-20 chữ số)",
    region="Mã vùng ví dụ BD, IND, BR (không bắt buộc — tự động nhận diện)",
)
async def player_cmd(ctx: commands.Context, uid: str, region: Optional[str] = None):
    # Phản hồi tương tác ngay để lệnh slash không hết hạn (cửa sổ 3 giây).
    try:
        await ctx.defer()
    except (discord.errors.NotFound, discord.errors.InteractionResponded):
        LOGGER.warning("Tương tác hết hạn trước khi defer (độ trễ gateway).")
        return

    data, err = await fetch_player(uid, region)
    if err:
        if err.startswith("BACKEND_DOWN"):
            await ctx.send(
                f"⚠️ Không thể kết nối đến backend Flask tại `{FF_API_BASE_URL}`.\n"
                f"→ Hãy chạy `python app.py` (hoặc `python run.py`) trước khi dùng bot."
            )
        else:
            status, _, msg = err.partition(":")
            if status == "400":
                await ctx.send(f"❌ {msg}")
            else:
                await ctx.send(f"⚠️ Lỗi từ backend ({status}): {msg}")
        return

    safe_uid = (data.get("basicInfo") or {}).get("accountId") or uid
    safe_region = (data.get("basicInfo") or {}).get("region") or region or "?"
    nickname = (data.get("basicInfo") or {}).get("nickname") or "Unknown Player"

    # Lấy banner/avatar để đính kèm; URL gắn với file đính kèm nên sẽ hiện
    # xuyên suốt mọi trang khi người dùng chuyển mục / phân trang.
    banner = await fetch_media("banner", safe_uid, region)
    avatar = await fetch_media("avatar", safe_uid, region)

    files = []
    if banner:
        files.append(discord.File(io.BytesIO(banner), filename=f"banner_{safe_uid}.webp"))
    if avatar:
        files.append(discord.File(io.BytesIO(avatar), filename=f"avatar_{safe_uid}.webp"))

    # Nhóm các dòng theo mục, dựng View (dropdown + nút phân trang).
    rows = flatten_player(data)
    grouped = _group_rows(rows)
    meta = {
        "nickname": nickname,
        "uid": safe_uid,
        "region": safe_region,
        "banner_url": f"attachment://banner_{safe_uid}.webp" if banner else None,
        "avatar_url": f"attachment://avatar_{safe_uid}.webp" if avatar else None,
    }
    view = PlayerView(grouped, meta, ctx.author.id)
    embed = view._current_embed()

    await ctx.send(embed=embed, files=files or None, view=view)


@bot.hybrid_command(name="regions", description="Liệt kê các mã vùng Free Fire được hỗ trợ.")
async def regions_cmd(ctx: commands.Context):
    try:
        resp = await _api_get("/api/regions")
        if resp.status_code == 200:
            j = resp.json()
            aliases = ", ".join(f"{k}→{v}" for k, v in (j.get("aliases") or {}).items())
            await ctx.send(
                f"**Vùng được hỗ trợ ({len(j.get('regions', []))}):** "
                f"{', '.join(j.get('regions', []))}\n"
                f"**Bí danh:** {aliases or '—'}\n"
                f"Để trống `region` ở `/player` để tự động nhận diện."
            )
            return
    except Exception:  # noqa: BLE001 - rơi xuống thông báo bên dưới
        pass
    await ctx.send(
        f"❌ Không thể lấy danh sách vùng từ backend `{FF_API_BASE_URL}`. "
        f"Hãy chạy `python app.py`."
    )


@bot.hybrid_command(name="ffping", description="Kiểm tra bot có đang hoạt động không.")
async def ping_cmd(ctx: commands.Context):
    ms = round(bot.latency * 1000)
    await ctx.send(f"🟢 Đang hoạt động với tên {bot.user} (độ trễ gateway {ms} ms)")


# --------------------------------------------------------------------------- #
# Vòng đời
# --------------------------------------------------------------------------- #
_sync_done = False


@bot.event
async def on_ready():
    global _sync_done
    if not _sync_done:
        try:
            await bot.tree.sync()
            LOGGER.info("Đã đồng bộ lệnh slash.")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Đồng bộ lệnh slash thất bại: %s", exc)
        _sync_done = True
    LOGGER.info("Bot sẵn sàng: %s  (backend: %s)", bot.user, FF_API_BASE_URL)


@bot.event
async def on_hybrid_command_error(ctx: commands.Context, error: commands.HybridCommandError):
    original = error.original if isinstance(error, commands.HybridCommandError) else error
    if isinstance(original, discord.errors.NotFound) and getattr(original, "code", None) == 10062:
        LOGGER.warning("Tương tác hết hạn (Unknown interaction / 10062) — độ trễ gateway. Bỏ qua.")
        return
    if isinstance(original, (httpx.ConnectError, OSError)):
        await ctx.send(
            f"⚠️ Không thể kết nối đến backend Flask tại `{FF_API_BASE_URL}`. "
            f"Hãy chạy `python app.py` (hoặc `python run.py`) trước."
        )
        return
    LOGGER.exception("Lỗi lệnh hybrid chưa xử lý: %s", original)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
