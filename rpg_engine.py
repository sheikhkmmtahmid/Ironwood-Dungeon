import json, random, re, threading
from pathlib import Path
import npc_manager as npcs

BASE = Path(__file__).parent

# Some models wrap reasoning in <think>...</think> before the actual response.
# Strip it so it never leaks into narrative_text shown to the player.
def _strip_thinking(text):
    cleaned = re.sub(r'<think>.*?</think>', '', text or '', flags=re.DOTALL)
    return cleaned.strip()

# Thread-local room context — set at each request entry point via set_room_code()
_ctx = threading.local()

def set_room_code(rc):
    _ctx.room_code = (rc or "SOLO").upper()

def _rc():
    return getattr(_ctx, "room_code", "SOLO")

def _state_file():
    return BASE / f"game_state_{_rc()}.json"

def _hist_file():
    return BASE / f"history_{_rc()}.json"

# Legacy path kept so /api/reset can reference it; inventory now lives in character.json
INVENTORY_FILE = BASE / "inventory.json"

INITIAL_INVENTORY = {"items": [
    {"id":"health_potion","name":"Health Potion","type":"consumable","effect":"heal","value":30,"quantity":2,"description":"Restores 30 HP."},
    {"id":"iron_sword","name":"Iron Sword","type":"weapon","effect":"damage","value":15,"quantity":1,"description":"A nicked but reliable blade."},
    {"id":"wooden_shield","name":"Wooden Shield","type":"armor","effect":"block","value":10,"quantity":1,"description":"Scarred oak, still holds."},
    {"id":"smoke_bomb","name":"Smoke Bomb","type":"consumable","effect":"escape","value":0,"quantity":1,"description":"Vanish from combat instantly."},
]}

INITIAL_GAME_STATE = {
    "player_name":"Adventurer","hp":80,"max_hp":100,
    "location":"Ironwood Village — Ironwood Inn",
    "floor":1,"turn":1,"room_searched":False,"gold":15,"choices":[],
    "last_narrative":"",
    "enemy": None,
    "current_room_id": "f1_entrance",
    "boss_cleared": False,
    "xp": 0, "level": 1, "xp_to_next": 300,
    "long_rest_used_this_floor": False,
    "tutorial_shown": False,
    "enemies_defeated": 0,
    "on_surface": True,
    "hub_visited": False,
    "shrine_used": False,
}

FLOOR_ENEMIES = {
    1:{"name":"Dungeon Troll","hp":22,"max_hp":22,"damage":[4,10]},
    2:{"name":"Shadow Wraith","hp":35,"max_hp":35,"damage":[6,14]},
    3:{"name":"Stone Golem","hp":52,"max_hp":52,"damage":[9,20]},
    4:{"name":"Bone Dragon","hp":78,"max_hp":78,"damage":[12,30]},
}

LOOT_TABLE = [
    {"id":"health_potion","name":"Health Potion","type":"consumable","effect":"heal","value":30,"quantity":1,"description":"Restores 30 HP."},
    {"id":"elixir","name":"Elixir of Vigor","type":"consumable","effect":"heal","value":50,"quantity":1,"description":"Restores 50 HP."},
    {"id":"poison_dagger","name":"Poison Dagger","type":"weapon","effect":"damage","value":20,"quantity":1,"description":"Coated blade. 20 base damage."},
    {"id":"smoke_bomb","name":"Smoke Bomb","type":"consumable","effect":"escape","value":0,"quantity":1,"description":"Vanish from combat instantly."},
    {"id":"steel_shield","name":"Steel Shield","type":"armor","effect":"block","value":15,"quantity":1,"description":"Heavy but reliable."},
]

def get_inventory():
    import character_manager as _chars
    char = _chars.load_character()
    if not char:
        return {"items": []}
    items = []
    for e in char.get("equipment", []):
        iid = e.get("item_id") or e.get("id", "")
        cat = _chars.ITEM_CATALOG.get(iid, {})
        items.append({
            "id":          iid,
            "name":        e.get("name") or cat.get("name", iid),
            "type":        e.get("type") or cat.get("type", ""),
            "quantity":    e.get("quantity", 1),
            "description": e.get("description") or cat.get("description", ""),
            "equipped":    e.get("equipped", False),
            "weight":      e.get("weight") or cat.get("weight", 0),
        })
    return {"items": items}


def use_item(item_id, target):
    import character_manager as _chars
    char  = _chars.load_character()
    state = json.loads(_state_file().read_text())

    equipment  = char.get("equipment", [])
    item       = None
    item_index = -1
    for i, e in enumerate(equipment):
        iid = e.get("item_id") or e.get("id", "")
        if iid == item_id or e.get("name", "").lower() == item_id.lower():
            item       = e
            item_index = i
            break

    if item is None:
        return {"success": False, "error": f"No item '{item_id}' in inventory."}
    if item.get("quantity", 1) <= 0:
        return {"success": False, "error": f"No '{item.get('name', item_id)}' remaining."}

    item_name  = item.get("name", item_id)
    name_lower = item_name.lower()
    result     = {"success": True, "item_used": item_name, "target": target}

    if "potion" in name_lower or "elixir" in name_lower:
        heal_val = 50 if ("greater" in name_lower or "elixir" in name_lower) else 30
        old_hp   = state["hp"]
        state["hp"] = min(state["max_hp"], state["hp"] + heal_val)
        result["effect"]        = "heal"
        result["hp_restored"]   = state["hp"] - old_hp
        result["player_hp_now"] = state["hp"]
        item["quantity"] = item.get("quantity", 1) - 1

    elif "smoke" in name_lower:
        state["enemy"] = None
        result["effect"] = "escape"
        result["note"]   = "Smoke bomb detonated — enemy lost in haze."
        item["quantity"] = item.get("quantity", 1) - 1

    else:
        return {"success": False, "error": f"'{item_name}' cannot be used as a consumable."}

    if item.get("quantity", 0) <= 0:
        equipment.pop(item_index)
    else:
        equipment[item_index] = item

    char["equipment"]            = equipment
    char["combat"]["current_hp"] = state["hp"]
    _chars.save_character(char)
    _state_file().write_text(json.dumps(state, indent=2))
    return result


def search_room():
    import character_manager as _chars
    state = json.loads(_state_file().read_text())
    char  = _chars.load_character()

    enemy = state.get("enemy")
    if enemy and enemy.get("hp", 0) > 0:
        return {"success": False, "error": "Defeat the enemy before searching."}
    if state.get("room_searched"):
        return {"success": False, "note": "Already searched. Nothing more here."}

    found     = random.choice(LOOT_TABLE).copy()
    found_iid = found.get("id", "")
    equipment = char.get("equipment", [])

    existing = next(
        (e for e in equipment if (e.get("item_id") or e.get("id", "")) == found_iid),
        None
    )
    if existing:
        existing["quantity"] = existing.get("quantity", 1) + found.get("quantity", 1)
    else:
        cat = _chars.ITEM_CATALOG.get(found_iid, {})
        equipment.append({
            "item_id":     found_iid,
            "name":        found.get("name") or cat.get("name", found_iid),
            "weight":      cat.get("weight", 0),
            "type":        found.get("type") or cat.get("type", ""),
            "description": found.get("description") or cat.get("description", ""),
            "equipped":    False,
            "quantity":    found.get("quantity", 1),
        })

    char["equipment"]     = equipment
    char["current_weight"] = round(
        sum(e.get("weight", 0) * e.get("quantity", 1) for e in equipment), 1
    )
    _chars.save_character(char)

    state["room_searched"] = True
    _state_file().write_text(json.dumps(state, indent=2))
    return {"success": True, "found": found["name"], "description": found.get("description", "")}


def next_floor():
    state = json.loads(_state_file().read_text())
    enemy = state.get("enemy")
    if enemy and enemy.get("hp", 0) > 0:
        return {"success": False, "error": "Cannot descend while enemy is alive."}
    if not state.get("boss_cleared"):
        return {"success": False, "error": "Defeat the floor boss before descending."}
    next_f = state["floor"] + 1
    if next_f > len(FLOOR_ENEMIES):
        return {"success": True, "victory": True, "note": "All floors conquered."}
    entrance_id = f"f{next_f}_entrance"
    state.update({
        "floor":           next_f,
        "enemy":           None,
        "current_room_id": entrance_id,
        "boss_cleared":    False,
        "room_searched":   False,
        "location":        f"Ironwood Dungeon -- Floor {next_f}, Entrance",
        "long_rest_used_this_floor": False,
    })
    _state_file().write_text(json.dumps(state, indent=2))
    return {"success": True, "floor": next_f, "location": state["location"],
            "current_room_id": entrance_id}


def attempt_sneak():
    state   = json.loads(_state_file().read_text())
    roll    = random.randint(1, 20)
    dc      = 12
    success = roll >= dc
    result  = {"roll": roll, "dc": dc, "success": success}
    if success:
        state["enemy"]["hp"] = 0
        result["note"] = f"Roll {roll} vs DC {dc} -- SUCCESS. You slip through undetected."
    else:
        enemy = state.get("enemy")
        if enemy and enemy["hp"] > 0:
            surprise         = random.randint(*enemy["damage"])
            state["hp"]      = max(0, state["hp"] - surprise)
            result["note"]   = f"Roll {roll} vs DC {dc} -- FAIL. {enemy['name']} deals {surprise} surprise damage. Player HP now {state['hp']}."
            result["surprise_damage"]  = surprise
            result["player_hp_now"]    = state["hp"]
    _state_file().write_text(json.dumps(state, indent=2))
    return result


def attempt_talk():
    state = json.loads(_state_file().read_text())
    gold  = state.get("gold", 0)
    cost  = 5
    if gold < cost:
        return {"success": False, "error": f"Need {cost} gold to parley, have {gold}.", "gold_spent": 0}
    state["gold"] = gold - cost
    roll    = random.randint(1, 20)
    dc      = 14
    success = roll >= dc
    result  = {"roll": roll, "dc": dc, "gold_spent": cost, "success": success, "gold_remaining": state["gold"]}
    if success:
        state["enemy"]["hp"] = 0
        result["note"] = f"Roll {roll} vs DC {dc} -- SUCCESS. The creature stands down."
    else:
        result["note"] = f"Roll {roll} vs DC {dc} -- FAIL. Gold lost. Combat continues."
    _state_file().write_text(json.dumps(state, indent=2))
    return result


def get_ending_type(choices):
    if not choices:
        return "survivor"
    counts = {"fight": 0, "sneak": 0, "talk": 0}
    for c in choices:
        if c in counts:
            counts[c] += 1
    dominant = max(counts, key=counts.get)
    if counts[dominant] >= 3:
        return {"fight": "warrior", "sneak": "shadow", "talk": "kingmaker"}[dominant]
    return "survivor"


def save_history(history):
    _hist_file().write_text(json.dumps(history, indent=2))


def load_history():
    f = _hist_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return []
    return []


def descend_to_dungeon():
    state = json.loads(_state_file().read_text())
    if not state.get("on_surface", True):
        return {"success": False, "error": "Already inside the dungeon."}
    import dungeon_generator as dg
    if not dg._dungeon_file().exists():
        dg.generate_all_floors()
    entrance_id = dg.get_entrance_room_id(1)
    state.update({
        "on_surface":      False,
        "floor":           1,
        "current_room_id": entrance_id,
        "location":        "Ironwood Dungeon — Floor 1, Dungeon Gate",
    })
    _state_file().write_text(json.dumps(state, indent=2))
    return {
        "success":         True,
        "floor":           1,
        "location":        state["location"],
        "current_room_id": entrance_id,
    }


def pray_at_shrine():
    state = json.loads(_state_file().read_text())
    if not state.get("on_surface", False):
        return {"success": False, "error": "The shrine is on the surface. You are inside the dungeon."}
    if state.get("shrine_used", False):
        return {"success": False, "error": "You have already drawn on the shrine's blessing. The stone is cold now."}
    import character_manager as _chars
    char = _chars.load_character()
    if not char:
        return {"success": False, "error": "No character found."}
    sp    = char.get("spellcasting", {})
    slots = sp.get("spell_slots", {})
    restored_slot = None
    for k, v in slots.items():
        if isinstance(v, dict) and v.get("used", 0) > 0:
            v["used"] -= 1
            restored_slot = k
            break
    if not restored_slot:
        return {"success": False, "error": "No expended spell slots to restore."}
    _chars.save_character(char)
    state["shrine_used"] = True
    _state_file().write_text(json.dumps(state, indent=2))
    return {
        "success":       True,
        "slot_restored": restored_slot,
        "message":       "The cold altar stone warms briefly under your hands. One expended slot returns.",
    }


def dispatch(name, inputs):
    if name == "get_inventory": return json.dumps(get_inventory())
    if name == "use_item":      return json.dumps(use_item(inputs["item_id"], inputs["target"]))
    if name == "search_room":   return json.dumps(search_room())
    if name == "next_floor":    return json.dumps(next_floor())
    if name == "talk_to_npc":   return json.dumps(npcs.talk_to_npc(inputs["npc_id"]))
    if name == "persuade_npc":  return json.dumps(npcs.persuasion_check(inputs["npc_id"]))
    if name == "buy_from_npc":
        state = json.loads(_state_file().read_text())
        result = npcs.buy_item(inputs["npc_id"], inputs["item_id"], inputs.get("quantity", 1), state)
        if result.get("success"):
            state["gold"] = result["gold_remaining"]
            _state_file().write_text(json.dumps(state, indent=2))
            import character_manager as chars
            chars.add_item_to_equipment(inputs["item_id"], inputs.get("quantity", 1))
        return json.dumps(result)
    if name == "award_inspiration":
        import character_manager as _chars
        char = _chars.load_character()
        if char and not char["identity"].get("inspiration"):
            char["identity"]["inspiration"] = True
            _chars.CHARACTER_FILE.write_text(json.dumps(char, indent=2))
            return json.dumps({"success": True, "message": "Inspiration awarded! You hold a point of Inspiration."})
        return json.dumps({"success": False, "message": "Player already holds Inspiration — it does not stack."})
    if name == "use_inspiration":
        import character_manager as _chars
        char = _chars.load_character()
        if not char:
            return json.dumps({"error": "No character found."})
        if not char["identity"].get("inspiration"):
            return json.dumps({"error": "No Inspiration to spend."})
        char["identity"]["inspiration"] = False
        _chars.CHARACTER_FILE.write_text(json.dumps(char, indent=2))
        return json.dumps({"success": True, "advantage_on": inputs.get("purpose", "this roll"),
                           "message": "Inspiration spent — roll with advantage."})
    if name == "descend_to_dungeon": return json.dumps(descend_to_dungeon())
    if name == "pray_at_shrine":     return json.dumps(pray_at_shrine())
    if name == "rest_at_inn":        return json.dumps(npcs.rest_at_inn())
    if name == "accept_quest":
        return json.dumps(npcs.accept_quest(inputs["quest_id"]))
    if name == "complete_quest":
        state = json.loads(_state_file().read_text())
        result = npcs.complete_quest(inputs["quest_id"], state)
        if result.get("success"):
            state["gold"] = state.get("gold", 0) + result["gold_reward"]
            import character_manager as chars
            chars.award_xp(result["xp_reward"])
            _state_file().write_text(json.dumps(state, indent=2))
        return json.dumps(result)
    return json.dumps({"error": f"Unknown tool: {name}"})


def run_turn(client, history, player_input):
    state = json.loads(_state_file().read_text())
    enemy = state.get("enemy")

    parts = [
        f"Turn {state['turn']}",
        f"Player HP: {state['hp']}/{state['max_hp']}",
        f"Floor: {state['floor']}/4",
        f"Gold: {state.get('gold', 0)}",
    ]
    if enemy and enemy["hp"] > 0:
        parts.append(f"Enemy: {enemy['name']} HP {enemy['hp']}/{enemy['max_hp']}")
    else:
        searched = "yes" if state.get("room_searched") else "no"
        parts.append(f"Room cleared (loot searched: {searched})")

    history.append({
        "role": "user",
        "content": "[GAME STATE: " + " | ".join(parts) + "]\nPlayer action: " + player_input,
    })

    nudge_count = 0

    while True:
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b",
            messages=history,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1200,
            temperature=0.7,
        )

        msg    = response.choices[0].message
        reason = response.choices[0].finish_reason

        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        history.append(entry)

        game_resp = None
        results   = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                if name == "game_response":
                    game_resp = args
                    results.append({"role": "tool", "tool_call_id": tc.id, "content": "Delivered."})
                else:
                    results.append({"role": "tool", "tool_call_id": tc.id, "content": dispatch(name, args)})

        history.extend(results)

        if game_resp is not None:
            final_state = json.loads(_state_file().read_text())
            # Server always overrides HP — the LLM is not trusted for numbers
            game_resp["current_hp"] = final_state["hp"]
            game_resp["party_hp"]   = {final_state.get("player_name", "Player"): final_state["hp"]}
            game_resp.setdefault("dice_rolls_this_turn",  [])
            game_resp.setdefault("conditions_applied",    [])
            game_resp.setdefault("xp_gained",             0)
            game_resp.setdefault("spell_slots_remaining", {})
            final_state["turn"] += 1
            final_state["last_narrative"] = game_resp["narrative_text"]
            final_state["last_actions"]   = game_resp.get("available_actions", [])
            _state_file().write_text(json.dumps(final_state, indent=2))
            save_history(history)
            return game_resp

        if reason == "stop" and not msg.tool_calls and msg.content and msg.content.strip():
            final_state = json.loads(_state_file().read_text())
            game_resp = {
                "narrative_text": msg.content.strip(),
                "current_hp": final_state["hp"],
                "available_actions": [],
                "party_hp": {final_state.get("player_name", "Player"): final_state["hp"]},
                "dice_rolls_this_turn": [],
                "conditions_applied": [],
                "xp_gained": 0,
                "spell_slots_remaining": {},
            }
            final_state["turn"] += 1
            final_state["last_narrative"] = game_resp["narrative_text"]
            final_state["last_actions"]   = []
            _state_file().write_text(json.dumps(final_state, indent=2))
            save_history(history)
            return game_resp

        if reason == "stop" and not msg.tool_calls:
            nudge_count += 1
            if nudge_count >= 3:
                final_state = json.loads(_state_file().read_text())
                fallback = {
                    "narrative_text": "The dungeon holds its breath. Your action echoes in the darkness.",
                    "current_hp": final_state["hp"],
                    "available_actions": ["Attack the enemy", "Check your inventory", "Look around carefully"],
                }
                final_state["turn"] += 1
                final_state["last_narrative"] = fallback["narrative_text"]
                final_state["last_actions"]   = fallback["available_actions"]
                _state_file().write_text(json.dumps(final_state, indent=2))
                save_history(history)
                return fallback
            history.append({
                "role": "user",
                "content": "You must call game_response() now to complete this turn. Do not stop without calling it.",
            })


RESOLVED_GAME_RESPONSE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "game_response",
            "description": "Narrate a server-resolved game event. Do not invent mechanics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "narrative_text":       {"type": "string",  "description": "3-5 sentence narration of the exact server-resolved event."},
                    "current_hp":           {"type": "integer", "description": "Player HP from server state only."},
                    "party_hp":             {"type": "object",  "description": "Map of party member names to HP values."},
                    "available_actions":    {"type": "array",   "items": {"type": "string"}},
                    "dice_rolls_this_turn": {"type": "array",   "items": {"type": "object","properties": {"die":{"type":"string"},"result":{"type":"integer"},"purpose":{"type":"string"}}}},
                    "conditions_applied":   {"type": "array",   "items": {"type": "string"}},
                    "xp_gained":            {"type": "integer"},
                    "spell_slots_remaining":{"type": "object"},
                },
                "required": ["narrative_text", "current_hp", "available_actions"],
            },
        },
    }
]


def run_resolved_turn(client, history, resolved_event):
    """
    Narration-only LLM call. All mechanics are already resolved by Python before this runs.
    The LLM may only narrate the event given — it cannot change any numbers.
    """
    state = json.loads(_state_file().read_text())

    phase_prefix = ""
    if resolved_event.get("phase_transition") and resolved_event.get("phase_narrative"):
        phase_prefix = (
            "[BOSS PHASE TRANSITION]\n"
            + resolved_event["phase_narrative"]
            + "\n\n"
        )

    prompt = (
        phase_prefix
        + "You are the Dungeon Master. You CANNOT invent dice results, HP values, AC values, "
        "damage values, inventory items, XP awards, spell slots, or condition effects. "
        "All mechanical outcomes have already been determined by the Python game engine. "
        "Narrate ONLY the server-resolved event below. If the event says an attack missed, "
        "you must narrate a miss. If it says HP is a value, use that value only.\n\n"
        "[SERVER_RESOLVED_EVENT]\n"
        + json.dumps(resolved_event, indent=2)
    )

    history.append({"role": "user", "content": prompt})

    args = None
    nudge_count = 0

    try:
        while args is None:
            response = client.chat.completions.create(
                model="nvidia/nemotron-3-super-120b-a12b",
                messages=history,
                tools=RESOLVED_GAME_RESPONSE_TOOL,
                tool_choice="auto",
                max_tokens=900,
                temperature=0.45,
            )

            msg    = response.choices[0].message
            reason = response.choices[0].finish_reason

            entry = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]
            history.append(entry)

            if msg.tool_calls:
                tc = next((t for t in msg.tool_calls if t.function.name == "game_response"), None)
                if tc:
                    args = json.loads(tc.function.arguments or "{}")
                    break
                raise ValueError("No game_response tool call found.")

            # Model output text instead of calling game_response.
            # Strip <think>...</think> blocks that reasoning models emit before their answer.
            cleaned = _strip_thinking(msg.content or "")
            if reason == "stop" and cleaned:
                args = {"narrative_text": cleaned}
                break

            # Still no useful response — nudge once then give up
            nudge_count += 1
            if nudge_count >= 2:
                raise ValueError("LLM did not call game_response after nudge.")
            history.append({
                "role": "user",
                "content": "Call game_response() now with your narration. Do not write planning text.",
            })

    except Exception:
        args = {
            "narrative_text": resolved_event.get(
                "summary",
                "Steel flashes in the dark, and the dungeon answers with violence."
            ),
            "current_hp": state["hp"],
            "available_actions": resolved_event.get("available_actions", ["Attack", "Dodge", "Use Item"]),
            "party_hp": {state.get("player_name", "Player"): state["hp"]},
            "dice_rolls_this_turn": resolved_event.get("dice_rolls_this_turn", []),
            "conditions_applied": [],
            "xp_gained": 0,
            "spell_slots_remaining": {},
        }

    # Server override — never trust the LLM for HP, actions, or dice rolls
    state = json.loads(_state_file().read_text())
    args["current_hp"]            = state["hp"]
    args["party_hp"]              = {state.get("player_name", "Player"): state["hp"]}
    args["dice_rolls_this_turn"]  = resolved_event.get("dice_rolls_this_turn", [])
    args["available_actions"]     = resolved_event.get("available_actions", args.get("available_actions", []))

    state["turn"]           = state.get("turn", 1) + 1
    state["last_narrative"] = args["narrative_text"]
    state["last_actions"]   = args.get("available_actions", [])
    _state_file().write_text(json.dumps(state, indent=2))

    return args


TOOLS = [
    {"type":"function","function":{
        "name":"get_inventory",
        "description":"Returns the player current inventory from disk. Call this before mentioning or using any item. Never reference items you have not verified here.",
        "parameters":{"type":"object","properties":{},"required":[]},
    }},
    {"type":"function","function":{
        "name":"use_item",
        "description":"Use an item from inventory. Only call after get_inventory confirmed it exists with quantity > 0. Narrate the exact numbers returned.",
        "parameters":{"type":"object","properties":{
            "item_id":{"type":"string","description":"The id field from get_inventory."},
            "target":{"type":"string","description":"Who or what the item is used on."},
        },"required":["item_id","target"]},
    }},
    {"type":"function","function":{
        "name":"search_room",
        "description":"Search the cleared room for loot. Only valid after the enemy is defeated.",
        "parameters":{"type":"object","properties":{},"required":[]},
    }},
    {"type":"function","function":{
        "name":"next_floor",
        "description":"Descend to the next dungeon floor. Only valid when no enemy is alive and player explicitly wants to advance.",
        "parameters":{"type":"object","properties":{},"required":[]},
    }},
    {"type":"function","function":{
        "name":"talk_to_npc",
        "description":"Initiate conversation with an NPC in the current room. Returns their greeting, shop availability, and any quest offer. Always call this before buying from or accepting a quest from an NPC.",
        "parameters":{"type":"object","properties":{
            "npc_id":{"type":"string","description":"The NPC id (e.g. 'gribb', 'captain_vera', 'solus')."},
        },"required":["npc_id"]},
    }},
    {"type":"function","function":{
        "name":"persuade_npc",
        "description":"Attempt a CHA-based persuasion check against an NPC. Roll d20 + CHA modifier vs their disposition DC. Use this when the player tries to charm, haggle, or negotiate.",
        "parameters":{"type":"object","properties":{
            "npc_id":{"type":"string","description":"The NPC id to persuade."},
        },"required":["npc_id"]},
    }},
    {"type":"function","function":{
        "name":"buy_from_npc",
        "description":"Buy an item from an NPC merchant. Validates gold. Call talk_to_npc first to confirm the item is in their inventory.",
        "parameters":{"type":"object","properties":{
            "npc_id":  {"type":"string","description":"The NPC id."},
            "item_id": {"type":"string","description":"The item_id to buy."},
            "quantity":{"type":"integer","description":"How many to buy (default 1)."},
        },"required":["npc_id","item_id","quantity"]},
    }},
    {"type":"function","function":{
        "name":"accept_quest",
        "description":"Accept a quest offered by an NPC. Call after talk_to_npc confirmed a quest_offer is available.",
        "parameters":{"type":"object","properties":{
            "quest_id":{"type":"string","description":"The quest_id from the talk_to_npc result."},
        },"required":["quest_id"]},
    }},
    {"type":"function","function":{
        "name":"complete_quest",
        "description":"Attempt to complete an accepted quest. Server validates objectives server-side and awards XP + gold if met.",
        "parameters":{"type":"object","properties":{
            "quest_id":{"type":"string","description":"The quest_id to complete."},
        },"required":["quest_id"]},
    }},
    {"type":"function","function":{
        "name":"award_inspiration",
        "description":"Award the player one Inspiration point for an exceptionally creative, heroic, or in-character action. Inspiration does not stack. Call this at most once per meaningful story beat.",
        "parameters":{"type":"object","properties":{},"required":[]},
    }},
    {"type":"function","function":{
        "name":"use_inspiration",
        "description":"Spend the player's held Inspiration to grant advantage on one d20 roll (attack, save, or check). Only call this if the player asks to use it AND they currently hold Inspiration.",
        "parameters":{"type":"object","properties":{
            "purpose":{"type":"string","description":"Brief description of what the advantage is applied to, e.g. 'attack roll vs Dungeon Troll'."},
        },"required":["purpose"]},
    }},
    {"type":"function","function":{
        "name":"descend_to_dungeon",
        "description":"Travel from Ironwood Village into the dungeon. Sets location to Floor 1 Entrance. Only call when the player explicitly chooses to enter the dungeon from the village surface.",
        "parameters":{"type":"object","properties":{},"required":[]},
    }},
    {"type":"function","function":{
        "name":"pray_at_shrine",
        "description":"Pray at the Ruined Shrine in Ironwood Village to restore one expended spell slot. One use only per game. Only valid when the player is on the surface at the ruined_shrine location.",
        "parameters":{"type":"object","properties":{},"required":[]},
    }},
    {"type":"function","function":{
        "name":"rest_at_inn",
        "description":"Pay Innkeeper Mira 5 gold for a full night's rest: restores HP to maximum, recovers all spell slots, and clears all conditions. Only valid when on the surface at the Ironwood Inn.",
        "parameters":{"type":"object","properties":{},"required":[]},
    }},
    {"type":"function","function":{
        "name":"game_response",
        "description":"Deliver your structured response to the player. This MUST be the very last call you make every turn, no exceptions.",
        "parameters":{"type":"object","properties":{
            "narrative_text":       {"type":"string",  "description":"Vivid 3-5 sentence second-person narration. Reference only numbers and items from tool results."},
            "current_hp":           {"type":"integer", "description":"Player current HP taken directly from the latest tool result or game state. Never invent."},
            "party_hp":             {"type":"object",  "description":"Map of party member names to their current HP from tool results only."},
            "available_actions":    {"type":"array",   "items":{"type":"string"}, "description":"3-5 natural-language actions the player can take next turn."},
            "dice_rolls_this_turn": {"type":"array",   "items":{"type":"object","properties":{"die":{"type":"string"},"result":{"type":"integer"},"purpose":{"type":"string"}}}, "description":"All dice rolled this turn from tool results only."},
            "conditions_applied":   {"type":"array",   "items":{"type":"string"}, "description":"Conditions applied this turn as returned by tools."},
            "xp_gained":            {"type":"integer", "description":"XP awarded this turn from tool results only."},
            "spell_slots_remaining":{"type":"object",  "description":"Remaining spell slots by level from tool results only."},
        },"required":["narrative_text","current_hp","available_actions"]},
    }},
]
