import json
import threading
import time
from pathlib import Path

BASE = Path(__file__).parent

_ctx = threading.local()

def set_room_code(rc):
    _ctx.room_code = (rc or "SOLO").upper()

def _rc():
    return getattr(_ctx, "room_code", "SOLO")

def _inv_file():
    return BASE / f"party_inventory_{_rc()}.json"

# Legacy alias kept so old /api/reset code still compiles
PARTY_INVENTORY_FILE = BASE / "party_inventory_SOLO.json"


def load():
    f = _inv_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {"items": []}


def save(data):
    _inv_file().write_text(json.dumps(data, indent=2))


def get_pool():
    return load().get("items", [])


def reset():
    save({"items": []})


def share_item(item_id, qty, donor_name):
    import character_manager as chars
    char = chars.load_character()
    if not char:
        return {"error": "No character loaded."}

    equip  = char.get("equipment", [])
    target = next((e for e in equip if e.get("item_id") == item_id), None)
    if not target:
        return {"error": f"Item '{item_id}' not found in your inventory."}

    available = target.get("quantity", 1)
    take      = min(qty, available)
    if take <= 0:
        return {"error": "Nothing to share."}

    target["quantity"] = available - take
    char["equipment"]  = [e for e in equip if e.get("quantity", 0) > 0]
    chars.CHARACTER_FILE.write_text(json.dumps(char, indent=2))

    data     = load()
    existing = next((i for i in data["items"] if i["item_id"] == item_id), None)
    if existing:
        existing["qty"] += take
    else:
        cat = chars.ITEM_CATALOG.get(item_id, {})
        data["items"].append({
            "item_id":   item_id,
            "name":      cat.get("name", item_id),
            "qty":       take,
            "donor":     donor_name,
            "shared":    True,
            "timestamp": int(time.time()),
        })
    save(data)
    return {"success": True, "qty_shared": take}


def take_item(item_id, qty, taker_name):
    import character_manager as chars
    data   = load()
    target = next((i for i in data["items"] if i["item_id"] == item_id), None)
    if not target:
        return {"error": f"Item '{item_id}' not found in shared pool."}

    available = target.get("qty", 0)
    take      = min(qty, available)
    if take <= 0:
        return {"error": "Item unavailable."}

    target["qty"]  -= take
    data["items"]   = [i for i in data["items"] if i.get("qty", 0) > 0]
    save(data)

    chars.add_item_to_equipment(item_id, take)
    return {"success": True, "qty_taken": take, "taker": taker_name}
