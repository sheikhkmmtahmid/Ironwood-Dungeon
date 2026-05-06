import json
import random
import string
import time
from pathlib import Path

BASE       = Path(__file__).parent
PARTY_FILE = BASE / "party.json"

SESSIONS = {}


def _gen_code():
    chars = string.ascii_uppercase + string.digits
    for _ in range(200):
        code = "".join(random.choices(chars, k=4))
        if code not in SESSIONS:
            return code
    return "".join(random.choices(chars, k=6))


def _save_party(session):
    try:
        PARTY_FILE.write_text(json.dumps({
            "room_code":        session["room_code"],
            "state":            session["state"],
            "host_player_name": session["host_player_name"],
            "players": [
                {k: v for k, v in p.items() if k != "sid"}
                for p in session["players"]
            ],
        }, indent=2))
    except Exception:
        pass


def create_room(host_sid, host_player_name):
    code = _gen_code()
    SESSIONS[code] = {
        "room_code":        code,
        "host_sid":         host_sid,
        "host_player_name": host_player_name,
        "state":            "lobby",
        "players":          [],
        "combat_order":     [],
        "turn_index":       0,
        "paused":           False,
        "created_at":       time.time(),
    }
    _add_player(code, host_sid, host_player_name, is_host=True)
    return code


def _add_player(room_code, sid, player_name, is_host=False):
    s = SESSIONS.get(room_code)
    if not s:
        return False
    s["players"].append({
        "sid":         sid,
        "player_name": player_name,
        "character":   None,
        "ready":       False,
        "connected":   True,
        "is_host":     is_host,
    })
    return True


def join_room(room_code, sid, player_name):
    code = room_code.upper()
    s = SESSIONS.get(code)
    if not s:
        return {"error": "Room not found."}
    for p in s["players"]:
        if p["player_name"] == player_name:
            p["sid"]       = sid
            p["connected"] = True
            return {"success": True, "rejoined": True, "room_code": code,
                    "is_host": p["is_host"], "state": s["state"]}
    if s["state"] != "lobby":
        return {"error": "Game already in progress."}
    if len(s["players"]) >= 4:
        return {"error": "Room is full (max 4)."}
    _add_player(code, sid, player_name)
    return {"success": True, "rejoined": False, "room_code": code,
            "is_host": False, "state": s["state"]}


def get_session(room_code):
    return SESSIONS.get(room_code.upper()) if room_code else None


def get_session_by_sid(sid):
    for s in SESSIONS.values():
        for p in s["players"]:
            if p["sid"] == sid:
                return s
    return None


def set_character(room_code, player_name, character):
    s = SESSIONS.get(room_code)
    if not s:
        return False
    for p in s["players"]:
        if p["player_name"] == player_name:
            p["character"] = character
            p["ready"]     = True
            _save_party(s)
            return True
    return False


def all_ready(room_code):
    s = SESSIONS.get(room_code)
    if not s or not s["players"]:
        return False
    return all(p["ready"] for p in s["players"])


def start_game(room_code, requester_sid):
    s = SESSIONS.get(room_code)
    if not s:
        return {"error": "Room not found."}
    if s["host_sid"] != requester_sid:
        return {"error": "Only the host can start."}
    if not all_ready(room_code):
        return {"error": "Not all players are ready."}
    s["state"] = "playing"
    _save_party(s)
    return {"success": True}


def kick_player(room_code, host_sid, target_name):
    s = SESSIONS.get(room_code)
    if not s:
        return {"error": "Room not found."}
    if s["host_sid"] != host_sid:
        return {"error": "Only the host can kick players."}
    s["players"] = [p for p in s["players"] if p["player_name"] != target_name]
    _save_party(s)
    return {"success": True}


def on_disconnect(sid):
    s = get_session_by_sid(sid)
    if not s:
        return None, None
    for p in s["players"]:
        if p["sid"] == sid:
            p["connected"] = False
            return s["room_code"], p["player_name"]
    return None, None


def get_party_status(room_code):
    s = SESSIONS.get(room_code) if room_code else None
    if not s:
        return []
    actor = _current_actor(s)
    result = []
    for p in s["players"]:
        char   = p.get("character") or {}
        combat = char.get("combat", {})
        ident  = char.get("identity", {})
        is_cur = (actor is not None
                  and actor.get("type") == "player"
                  and actor.get("player_name") == p["player_name"])
        result.append({
            "player_name":    p["player_name"],
            "character_name": ident.get("character_name", p["player_name"]),
            "class":          ident.get("class", ""),
            "level":          ident.get("level", 1),
            "hp":             combat.get("current_hp", 0),
            "max_hp":         combat.get("max_hp", 0),
            "conditions":     combat.get("conditions", []),
            "connected":      p["connected"],
            "ready":          p["ready"],
            "is_host":        p["is_host"],
            "is_current_turn": is_cur,
        })
    return result


def init_combat_order(room_code, enemy):
    s = SESSIONS.get(room_code)
    if not s:
        return []
    order = []
    for p in s["players"]:
        char     = p.get("character") or {}
        init_mod = char.get("combat", {}).get("initiative", 0)
        roll     = random.randint(1, 20) + init_mod
        order.append({
            "type":        "player",
            "player_name": p["player_name"],
            "name":        char.get("identity", {}).get("character_name", p["player_name"]),
            "initiative":  roll,
            "sid":         p["sid"],
        })
    enemy_roll = random.randint(1, 20) + enemy.get("initiative_bonus", 0)
    order.append({
        "type":       "enemy",
        "name":       enemy.get("name", "Enemy"),
        "initiative": enemy_roll,
    })
    order.sort(key=lambda x: x["initiative"], reverse=True)
    s["combat_order"] = order
    s["turn_index"]   = 0
    return order


def _current_actor(session):
    order = session.get("combat_order", [])
    if not order:
        return None
    return order[session.get("turn_index", 0) % len(order)]


def get_current_actor(room_code):
    s = SESSIONS.get(room_code)
    return _current_actor(s) if s else None


def advance_turn(room_code):
    s = SESSIONS.get(room_code)
    if not s:
        return
    order = s.get("combat_order", [])
    if not order:
        return
    n = len(order)
    for _ in range(n):
        s["turn_index"] = (s["turn_index"] + 1) % n
        actor = _current_actor(s)
        if actor and actor.get("type") == "player":
            player = next(
                (p for p in s["players"] if p["player_name"] == actor.get("player_name")),
                None
            )
            if player and not player["connected"]:
                continue
        break


def clear_combat(room_code):
    s = SESSIONS.get(room_code)
    if s:
        s["combat_order"] = []
        s["turn_index"]   = 0


def is_player_turn(room_code, player_name):
    s = SESSIONS.get(room_code)
    if not s:
        return True
    order = s.get("combat_order", [])
    if not order:
        return True
    actor = _current_actor(s)
    if actor is None:
        return True
    return actor.get("type") == "player" and actor.get("player_name") == player_name


def is_enemy_turn(room_code):
    s = SESSIONS.get(room_code)
    if not s:
        return False
    actor = _current_actor(s)
    return actor is not None and actor.get("type") == "enemy"


def get_player(room_code, player_name):
    s = SESSIONS.get(room_code)
    if not s:
        return None
    return next((p for p in s["players"] if p["player_name"] == player_name), None)


def activate_player_character(room_code, player_name):
    import character_manager as chars
    chars.set_player_name(player_name)
    p = get_player(room_code, player_name)
    if p and p.get("character"):
        chars._char_file().write_text(json.dumps(p["character"], indent=2))
        return True
    return False


def save_active_character_to_party(room_code, player_name):
    import character_manager as chars
    char = chars.load_character()
    if char:
        p = get_player(room_code, player_name)
        if p:
            p["character"] = char
            _save_party(SESSIONS[room_code])


def get_or_create_solo(player_name, sid="solo"):
    code = "SOLO"
    if code not in SESSIONS:
        SESSIONS[code] = {
            "room_code":        code,
            "host_sid":         sid,
            "host_player_name": player_name,
            "state":            "playing",
            "players":          [{
                "sid":         sid,
                "player_name": player_name,
                "character":   None,
                "ready":       True,
                "connected":   True,
                "is_host":     True,
            }],
            "combat_order": [],
            "turn_index":   0,
            "paused":       False,
            "created_at":   time.time(),
        }
    else:
        s = SESSIONS[code]
        if not any(p["player_name"] == player_name for p in s["players"]):
            s["players"] = [{
                "sid":         sid,
                "player_name": player_name,
                "character":   None,
                "ready":       True,
                "connected":   True,
                "is_host":     True,
            }]
        else:
            for p in s["players"]:
                if p["player_name"] == player_name:
                    p["connected"] = True
                    p["sid"]       = sid
    return code
