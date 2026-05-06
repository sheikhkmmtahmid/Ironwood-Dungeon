import json, random
from pathlib import Path
import character_manager as chars

BASE          = Path(__file__).parent
REGISTRY_FILE = BASE / "npc_registry.json"
QUESTS_FILE   = BASE / "active_quests.json"

QUEST_DEFINITIONS = {
    "q_lost_cargo": {
        "name":        "Gribb's Lost Cargo",
        "description": "Find Gribb's stolen shipment — reach Floor 2 and clear the path.",
        "giver_id":    "gribb",
        "objective":   {"type": "floor_reached", "floor": 2},
        "xp_reward":   100,   # PHASE 4 updated
        "gold_reward": 50,    # PHASE 4 updated
    },
    "q_missing_patrol": {
        "name":        "The Missing Patrol",
        "description": "Discover what happened to Captain Vera's lost patrol in the Crypt Corridor.",
        "giver_id":    "captain_vera",
        "objective":   {"type": "boss_floor", "floor": 2},
        "xp_reward":   200,
        "gold_reward": 100,   # PHASE 4 updated
    },
    "q_hermit_eye": {
        "name":        "Eye of Stone",
        "description": "Defeat the Golem on Floor 3 and return the Eye fragment to Solus.",
        "giver_id":    "solus",
        "objective":   {"type": "boss_floor", "floor": 3},
        "xp_reward":   300,
        "gold_reward": 150,   # PHASE 4 updated
    },
}

NPC_ROOM_MAP = {
    "f1_vault":  "gribb",
    "f2_shrine": "captain_vera",
    "f3_forge":  "solus",
}

# Surface hub NPCs — not in the dungeon registry file
SURFACE_NPCS = {
    "innkeeper_mira": {
        "id":             "innkeeper_mira",
        "name":           "Mira",
        "role":           "Innkeeper",
        "disposition":    10,
        "quest_id":       None,
        "shop_inventory": [],
        "dialogue_tree": {
            "greeting":  (
                "Mira sets down a pewter mug and meets your eyes. "
                "'Room and board for weary souls. Five gold for a full night's rest — "
                "hot meal, clean straw, and you wake whole again.'"
            ),
            "no_gold":   "'Five gold, no less. Charity's a luxury I can't afford either.'",
            "rested":    "'You rise steadier. The dungeon can wait a few more hours.'",
        },
        "services": {
            "long_rest": {"cost": 5, "description": "Full HP, all spell slots, all conditions cleared."}
        },
    },
}


# Registry

def load_registry():
    try:
        return json.loads(REGISTRY_FILE.read_text())
    except Exception:
        return []


def get_npc(npc_id):
    for npc in load_registry():
        if npc["id"] == npc_id:
            return npc
    return SURFACE_NPCS.get(npc_id)


def npc_for_room(room_id):
    npc_id = NPC_ROOM_MAP.get(room_id)
    return get_npc(npc_id) if npc_id else None


# Quest state

def load_quests():
    if QUESTS_FILE.exists():
        try:
            return json.loads(QUESTS_FILE.read_text())
        except Exception:
            pass
    return {"accepted": [], "completed": []}


def save_quests(q):
    QUESTS_FILE.write_text(json.dumps(q, indent=2))


def accept_quest(quest_id):
    if quest_id not in QUEST_DEFINITIONS:
        return {"error": "Unknown quest."}
    q = load_quests()
    if quest_id in q["completed"]:
        return {"error": "Quest already completed."}
    if quest_id not in q["accepted"]:
        q["accepted"].append(quest_id)
        save_quests(q)
    return {"success": True, "quest_id": quest_id,
            "name": QUEST_DEFINITIONS[quest_id]["name"],
            "description": QUEST_DEFINITIONS[quest_id]["description"]}


def _check_objective(obj, game_state):
    otype = obj.get("type")
    if otype == "floor_reached":
        return game_state.get("floor", 1) >= obj["floor"]
    if otype == "boss_floor":
        floors_cleared = game_state.get("floors_boss_cleared", [])
        return obj["floor"] in floors_cleared
    return False


def complete_quest(quest_id, player_id="player"):
    if quest_id not in QUEST_DEFINITIONS:
        return {"error": "Unknown quest."}
    q = load_quests()
    if quest_id in q["completed"]:
        return {"error": "Quest already completed."}
    if quest_id not in q["accepted"]:
        return {"error": "Quest not yet accepted."}
    defn = QUEST_DEFINITIONS[quest_id]

    # Read current game state to check objective
    import json as _json
    game_state_file = BASE / "game_state.json"
    game_state = {}
    if game_state_file.exists():
        try:
            game_state = _json.loads(game_state_file.read_text())
        except Exception:
            pass
    if not _check_objective(defn["objective"], game_state):
        return {"error": "Quest objective not yet met."}

    q["completed"].append(quest_id)
    q["accepted"] = [qid for qid in q["accepted"] if qid != quest_id]
    save_quests(q)

    # Award gold to character
    char = chars.load_character()
    if char:
        char["currency"]["gp"] = char.get("currency", {}).get("gp", 0) + defn["gold_reward"]
        chars.CHARACTER_FILE.write_text(_json.dumps(char, indent=2))

    # Award XP
    xp_result = chars.award_xp(defn["xp_reward"], f"quest_complete:{quest_id}", player_id)

    # Sync gold in game_state.json
    game_state["gold"] = game_state.get("gold", 0) + defn["gold_reward"]
    try:
        game_state_file.write_text(_json.dumps(game_state, indent=2))
    except Exception:
        pass

    return {
        "success":     True,
        "quest_id":    quest_id,
        "name":        defn["name"],
        "xp_reward":   defn["xp_reward"],
        "gold_reward": defn["gold_reward"],
        "xp_awarded":  xp_result,
    }


def get_quest_status(quest_id):
    q = load_quests()
    if quest_id in q["completed"]:
        return "completed"
    if quest_id in q["accepted"]:
        return "accepted"
    return "available"


# Persuasion

def _persuasion_modifier():
    """CHA modifier + proficiency bonus if proficient in Persuasion."""
    try:
        char = chars.load_character()
        if not char:
            return 0, 0
        cha_data = char.get("ability_scores", {}).get("CHA", {})
        cha_mod  = cha_data.get("modifier", 0) if isinstance(cha_data, dict) else (int(cha_data) - 10) // 2
        persuasion_skill = char.get("skills", {}).get("Persuasion", {})
        pb = char.get("identity", {}).get("prof_bonus", 2) if persuasion_skill.get("proficient") else 0
        return cha_mod, pb
    except Exception:
        return 0, 0


def persuasion_check(npc_id):
    npc = get_npc(npc_id)
    if not npc:
        return {"error": "NPC not found."}
    cha_mod, pb = _persuasion_modifier()
    roll        = random.randint(1, 20)
    total       = roll + cha_mod + pb
    dc          = npc["disposition"]
    success     = total >= dc
    key         = "persuade_success" if success else "persuade_fail"
    return {
        "npc_id":    npc_id,
        "npc_name":  npc["name"],
        "roll":      roll,
        "cha_mod":   cha_mod,
        "prof_bonus": pb,
        "total":     total,
        "dc":        dc,
        "success":   success,
        "dialogue":  npc["dialogue_tree"].get(key, ""),
    }


# Talk

def talk_to_npc(npc_id):
    npc = get_npc(npc_id)
    if not npc:
        return {"error": f"NPC '{npc_id}' not found."}
    qid    = npc.get("quest_id")
    qstatus = get_quest_status(qid) if qid else None
    result = {
        "npc_id":         npc["id"],
        "npc_name":       npc["name"],
        "role":           npc["role"],
        "greeting":       npc["dialogue_tree"].get("greeting", ""),
        "has_shop":       len(npc.get("shop_inventory", [])) > 0,
        "shop_inventory": npc.get("shop_inventory", []),
        "quest_id":       qid,
        "quest_status":   qstatus,
    }
    if qid and qstatus == "available":
        result["quest_offer"] = {
            "id":          qid,
            "name":        QUEST_DEFINITIONS[qid]["name"],
            "description": QUEST_DEFINITIONS[qid]["description"],
            "dialogue":    npc["dialogue_tree"].get("quest_given", ""),
        }
    elif qid and qstatus == "accepted":
        result["quest_progress"] = QUEST_DEFINITIONS[qid]["description"]
    elif qid and qstatus == "completed":
        result["quest_complete_dialogue"] = npc["dialogue_tree"].get("quest_complete", "")
    return result


# Buy

def buy_item(npc_id, item_id, quantity, player_id="player"):
    npc = get_npc(npc_id)
    if not npc:
        return {"error": "NPC not found."}
    shop = npc.get("shop_inventory", [])
    listing = next((x for x in shop if x["item_id"] == item_id), None)
    if not listing:
        return {"error": f"{npc['name']} does not sell '{item_id}'."}
    quantity = max(1, int(quantity))
    total_cost = listing["cost"] * quantity

    char = chars.load_character()
    if not char:
        return {"error": "No character loaded."}

    gold = char.get("currency", {}).get("gp", 0)
    if gold < total_cost:
        return {
            "error":      npc["dialogue_tree"].get("no_gold", "Not enough gold."),
            "gold_have":  gold,
            "gold_need":  total_cost,
        }

    item_def    = chars.ITEM_CATALOG.get(item_id, {})
    item_weight = item_def.get("weight", 0)
    add_weight  = item_weight * quantity
    if add_weight > 0:
        current_weight = char.get("current_weight", 0)
        carrying_cap   = char.get("carrying_capacity", 150)
        if current_weight + add_weight > carrying_cap:
            return {
                "error": (
                    f"Too heavy — adding {add_weight} lb would exceed your carrying limit "
                    f"of {carrying_cap} lb (currently carrying {current_weight} lb)."
                )
            }

    return {
        "success":        True,
        "item_id":        item_id,
        "item_name":      listing["name"],
        "quantity":       quantity,
        "cost_per":       listing["cost"],
        "total_cost":     total_cost,
        "gold_remaining": gold - total_cost,
        "player_id":      player_id,
    }


def rest_at_inn():
    """Pay Mira 5 gold for a full long rest: max HP, all spell slots, all conditions cleared."""
    import json as _json
    mira = SURFACE_NPCS["innkeeper_mira"]
    cost = mira["services"]["long_rest"]["cost"]

    char = chars.load_character()
    if not char:
        return {"success": False, "error": "No character found."}

    gold = char.get("currency", {}).get("gp", 0)
    if gold < cost:
        return {
            "success":   False,
            "error":     mira["dialogue_tree"]["no_gold"],
            "gold_have": gold,
            "gold_need": cost,
        }

    # Deduct gold
    char["currency"]["gp"] = gold - cost

    # Restore HP to maximum
    max_hp = char.get("combat", {}).get("max_hp", char.get("combat", {}).get("current_hp", 1))
    char["combat"]["current_hp"] = max_hp

    # Recover all spell slots
    sp = char.get("spellcasting", {})
    for slot_data in sp.get("spell_slots", {}).values():
        if isinstance(slot_data, dict):
            slot_data["used"] = 0

    # Clear all conditions
    char["combat"]["conditions"] = []

    # Restore hit dice
    hit_dice_total = char.get("combat", {}).get("hit_dice_total", 1)
    char["combat"]["hit_dice_remaining"] = hit_dice_total

    chars.save_character(char)

    # Sync game_state.json
    game_state_file = BASE / "game_state.json"
    if game_state_file.exists():
        try:
            state = _json.loads(game_state_file.read_text())
            state["hp"]   = max_hp
            state["gold"] = max(0, state.get("gold", 0) - cost)
            game_state_file.write_text(_json.dumps(state, indent=2))
        except Exception:
            pass

    return {
        "success":        True,
        "gold_spent":     cost,
        "gold_remaining": gold - cost,
        "hp_restored":    max_hp,
        "message":        mira["dialogue_tree"]["rested"],
    }
