import json, random, threading
from pathlib import Path

BASE         = Path(__file__).parent
ENEMIES_FILE = BASE / "enemies.json"

_ctx = threading.local()

def set_room_code(rc):
    _ctx.room_code = (rc or "SOLO").upper()

def _rc():
    return getattr(_ctx, "room_code", "SOLO")

def _dungeon_file():
    return BASE / f"dungeon_map_{_rc()}.json"

# Legacy alias used by a few older call sites in app.py — points to the SOLO file
DUNGEON_MAP_FILE = BASE / "dungeon_map_SOLO.json"

_NPC_ROOM_MAP = {"f1_vault": ["gribb"], "f2_shrine": ["captain_vera"], "f3_forge": ["solus"]}

def _npcs_for_room(room_id):
    return _NPC_ROOM_MAP.get(room_id, [])

TRAP_TYPES = {
    "spike_trap":    {"name":"Spike Trap",    "save":"DEX","dc":13,"damage_dice":"2d6","damage_type":"piercing"},
    "fire_trap":     {"name":"Fire Trap",     "save":"DEX","dc":14,"damage_dice":"3d6","damage_type":"fire"},
    "poison_gas":    {"name":"Poison Gas",    "save":"CON","dc":12,"damage_dice":"2d6","damage_type":"poison","condition_on_fail":"Poisoned"},
    "lightning_rod": {"name":"Lightning Rod","save":"DEX","dc":15,"damage_dice":"3d6","damage_type":"lightning"},
}

PUZZLES = {
    "riddle_map": {
        "text": "I have cities but no houses, mountains but no trees, water but no fish, roads but no cars. What am I?",
        "answer": "map",
        "reward": {"gold": 20, "xp": 50}
    },
    "riddle_footsteps": {
        "text": "The more you take, the more you leave behind. What am I?",
        "answer": "footsteps",
        "reward": {"gold": 15, "xp": 50}
    },
    "riddle_echo": {
        "text": "I speak without a mouth and hear without ears. I have no body but come alive with wind. What am I?",
        "answer": "echo",
        "reward": {"gold": 25, "xp": 50}
    },
    "riddle_clock": {
        "text": "I have hands but cannot clap. I have a face but cannot smile. I count everything but value nothing. What am I?",
        "answer": "clock",
        "reward": {"gold": 30, "xp": 50}
    },
}

def _load_floor_enemies(floor_num):  # PHASE 3 added
    """Return the enemies list for a floor from enemies.json."""
    if not ENEMIES_FILE.exists():
        return []
    try:
        data = json.loads(ENEMIES_FILE.read_text())
        return data.get("floors", {}).get(str(floor_num), [])
    except Exception:
        return []


def _normalize_enemy(enemy_data):  # PHASE 3 added
    """Prepare an enemies.json entry for storage in dungeon_map and combat."""
    e = dict(enemy_data)
    e["id"] = e.pop("enemy_id", e.get("id", "enemy_unknown"))
    # Combine damage_dice + damage_bonus into one expression
    dmg_dice  = e.get("damage_dice", "1d6")
    dmg_bonus = int(e.pop("damage_bonus", 0))
    if dmg_bonus > 0:
        e["damage_dice"] = f"{dmg_dice}+{dmg_bonus}"
    elif dmg_bonus < 0:
        e["damage_dice"] = f"{dmg_dice}{dmg_bonus}"
    # Ensure all required combat fields are present
    e.setdefault("initiative_bonus", 0)
    e.setdefault("damage_type", "bludgeoning")
    e.setdefault("special_abilities", [])
    return e


MINOR_ENEMIES = {
    1: {"name":"Cave Rat Swarm",  "hp":8,  "max_hp":8,  "ac":10,"attack_bonus":2,"damage_dice":"1d4",   "damage_type":"piercing",    "xp":25},
    2: {"name":"Skeleton Archer", "hp":13, "max_hp":13, "ac":13,"attack_bonus":3,"damage_dice":"1d6+1", "damage_type":"piercing",    "xp":50},
    3: {"name":"Stone Sentinel",  "hp":18, "max_hp":18, "ac":14,"attack_bonus":4,"damage_dice":"1d8+2", "damage_type":"bludgeoning", "xp":75},
    4: {"name":"Bone Wyvern",     "hp":22, "max_hp":22, "ac":14,"attack_bonus":5,"damage_dice":"1d8+2", "damage_type":"piercing",    "xp":75},
}

TREASURE_LOOT = {
    1: [{"item_id":"health_potion","qty":2},          {"gold_range":[15,30]}],    # PHASE 4 updated
    2: [{"item_id":"health_potion","qty":1},{"item_id":"scale_mail","qty":1},{"gold_range":[35,60]}],
    3: [{"item_id":"greater_health_potion","qty":2},  {"gold_range":[70,100]}],
    4: [{"item_id":"greater_health_potion","qty":2},{"item_id":"ring_of_protection","qty":1},{"gold_range":[120,200]}],
}

FLOOR_THEMES = {
    1: {
        "name":           "Stone Depths",
        "atmosphere":     "Hewn from bedrock over centuries, these corridors weep cold mineral water.",
        "color_accent":   "#8b7355",
        "water_mechanic": False,
        "room_flavor": [
            "The torchlight catches moisture beading on ancient chisel marks.",
            "A low resonant groan moves through the stone — the mountain breathing.",
            "Dry dust and damp stone fight for dominance in the stagnant air.",
            "Scratches mark the wall at eye level: someone counted days here once.",
            "The echo of your footsteps returns a half-beat too late.",
        ],
    },
    2: {
        "name":           "Flooded Crypts",
        "atmosphere":     "Black water has swallowed the lower passages, cold and perfectly still.",
        "color_accent":   "#4a7fa5",
        "water_mechanic": True,
        "room_flavor": [
            "Dark water pools between the flagstones, ankle-deep and bone-cold.",
            "The reflections on the ceiling shift — something moves below the surface.",
            "Waterlogged wood has warped every door frame into ruin.",
            "Salt stains mark the walls in pale rings from floods long past.",
            "The silence here is wet and absolute.",
        ],
    },
    3: {
        "name":           "Ancient Library",
        "atmosphere":     "Collapsed shelves and rotting vellum fill every alcove.",
        "color_accent":   "#6b4f9e",
        "water_mechanic": False,
        "room_flavor": [
            "Shelves groan under the weight of water-bloated tomes.",
            "Ink has leached into the stone, staining the floor with fragments of dead script.",
            "The dust here smells of old thought — heavy, formal, faintly sweet.",
            "A lectern stands in the corner, still upright, its book long since devoured by mould.",
            "Pages drift in a draught with no discernible source.",
        ],
    },
    4: {
        "name":           "Dragon's Lair",
        "atmosphere":     "The heat is palpable. Scorched stone. The reek of sulphur.",
        "color_accent":   "#a33c2b",
        "water_mechanic": False,
        "room_flavor": [
            "The stone underfoot is warm — not from torches, from something far below.",
            "Scorch marks radiate from the ceiling in concentric rings.",
            "The air shimmers at the far end of the corridor.",
            "Gold coins, warped and fused, are embedded in the floor like cobblestones.",
            "Each breath carries the taste of smoke and old ash.",
        ],
    },
}

# atmospheric lore notes assigned randomly to rooms
LORE_NOTES = {
    1: [
        "Carved into the stone: 'Thirteen entered. One left carrying nothing but her name.'",
        "A water-stained parchment: 'The Troll does not pursue. It waits. Never stop moving.'",
        "Scratched letters at eye-level: 'The vault is a trap. The way out is through.'",
    ],
    2: [
        "Ink on vellum, pinned under a bone: 'The wraith fears silence more than steel. Speak boldly.'",
        "Etched in a coffin lid: 'We came for gold. The shadow kept our names instead.'",
        "A torn note: 'Three floors, three guardians. What waits below the third is worse.'",
    ],
    3: [
        "Chiselled into bedrock: 'The Golem was made to remember. It cannot forgive.'",
        "A logbook entry, last page: 'Even fire broke on its skin. Try the eyes.'",
        "Scratched beneath a torch bracket: 'Floor Four is not a floor. It is an ending.'",
    ],
    4: [
        "Blood-painted on stone: 'Its breath is the cold that outlasts empires.'",
        "Carved over the arch: 'Every soul the Dragon has taken stands behind you now.'",
        "A final journal entry: 'I hear it breathing below. I write so someone knows I was here.'",
    ],
}

ENEMY_LOOT_TABLES = {
    1: [("health_potion", 0.45), ("torch", 0.25)],
    2: [("health_potion", 0.40), ("greater_health_potion", 0.20)],
    3: [("greater_health_potion", 0.35), ("cloak_of_shadows", 0.08)],
    4: [("greater_health_potion", 0.45), ("ring_of_protection", 0.10)],
}

BOSS_LOOT_GUARANTEED = {
    1: [("health_potion", 2), ("scale_mail", 1)],
    2: [("greater_health_potion", 1), ("cloak_of_shadows", 1)],
    3: [("greater_health_potion", 2), ("ring_of_protection", 1)],
    4: [("greater_health_potion", 3)],
}

FLOOR_TEMPLATES = {
    1: [
        {"id":"f1_entrance",  "name":"Dungeon Gate",       "type":"Entrance","grid_col":0,"grid_row":1,
         "description_seed":"A rusted iron portcullis opens into cold stone corridors. Torchlight flickers ahead.",
         "exits":["f1_guard_post"],"requires_key":False},
        {"id":"f1_guard_post","name":"Guard Post",          "type":"Combat",  "grid_col":1,"grid_row":0,
         "description_seed":"A rotting guard post. Overturned cot, old blood on the floor. Something scuttles in the corner.",
         "exits":["f1_entrance","f1_vault","f1_hall"],"requires_key":False,"minor_enemy":1},
        {"id":"f1_vault",     "name":"Vault Chamber",       "type":"Treasure","grid_col":2,"grid_row":0,
         "description_seed":"A heavy iron door stands ajar. Collapsed shelves, but something glints in the rubble.",
         "exits":["f1_guard_post"],"requires_key":False},
        {"id":"f1_hall",      "name":"Pressure-Plate Hall", "type":"Trap",    "grid_col":1,"grid_row":2,
         "description_seed":"A long corridor. The stones underfoot feel loose — pressure plates barely concealed by centuries of grime.",
         "exits":["f1_guard_post","f1_troll_lair"],"requires_key":False,"trap":"spike_trap"},
        {"id":"f1_troll_lair","name":"Troll's Lair",        "type":"Boss",    "grid_col":2,"grid_row":2,
         "description_seed":"The stench of rot hits first. Bones crunch underfoot. A massive silhouette stirs in the dark.",
         "exits":["f1_hall"],"requires_key":False},
    ],
    2: [
        {"id":"f2_entrance",     "name":"Lower Stairwell", "type":"Entrance","grid_col":0,"grid_row":1,
         "description_seed":"The stairs creak under your weight. The air grows colder. Something whispers just out of hearing.",
         "exits":["f2_shrine"],"requires_key":False},
        {"id":"f2_shrine",       "name":"Ruined Shrine",   "type":"Rest",    "grid_col":1,"grid_row":0,
         "description_seed":"A crumbled altar to a forgotten god. Cold candles, but a faint warmth lingers in the stone.",
         "exits":["f2_entrance","f2_library","f2_crypt_hall"],"requires_key":False},
        {"id":"f2_library",      "name":"Forbidden Library","type":"Puzzle",  "grid_col":2,"grid_row":0,
         "description_seed":"Shelves of rotting tomes. On the central lectern, a carved stone tablet bears a riddle.",
         "exits":["f2_shrine"],"requires_key":False,"puzzle":"riddle_map"},
        {"id":"f2_crypt_hall",   "name":"Crypt Corridor",  "type":"Combat",  "grid_col":1,"grid_row":2,
         "description_seed":"Sealed coffins line the walls. One hangs open and empty. Then: the draw of a bowstring.",
         "exits":["f2_shrine","f2_wraith_sanctum"],"requires_key":False,"minor_enemy":2},
        {"id":"f2_wraith_sanctum","name":"Wraith Sanctum", "type":"Boss",    "grid_col":2,"grid_row":2,
         "description_seed":"Cold that has nothing to do with temperature. Shadows writhe along the walls.",
         "exits":["f2_crypt_hall"],"requires_key":False},
    ],
    3: [
        {"id":"f3_entrance",     "name":"Stone Landing",   "type":"Entrance","grid_col":0,"grid_row":1,
         "description_seed":"The floor transitions to solid bedrock. The walls are scored with enormous claw marks.",
         "exits":["f3_forge"],"requires_key":False},
        {"id":"f3_forge",        "name":"Ancient Forge",   "type":"Treasure","grid_col":1,"grid_row":0,
         "description_seed":"An enormous stone forge, cold for centuries. In the ash bin, someone recently left something behind.",
         "exits":["f3_entrance","f3_gauntlet","f3_workshop"],"requires_key":False},
        {"id":"f3_gauntlet",     "name":"Lightning Gauntlet","type":"Trap",  "grid_col":1,"grid_row":2,
         "description_seed":"Copper rods jut from the walls. Tarnished green. A faint electric hum fills the air.",
         "exits":["f3_forge","f3_golem_chamber"],"requires_key":False,"trap":"lightning_rod"},
        {"id":"f3_workshop",     "name":"Golem Workshop",  "type":"Combat",  "grid_col":2,"grid_row":0,
         "description_seed":"Half-assembled constructs on workbenches. One — smaller and cruder — twitches and rises.",
         "exits":["f3_forge","f3_golem_chamber"],"requires_key":False,"minor_enemy":3},
        {"id":"f3_golem_chamber","name":"Golem Chamber",   "type":"Boss",    "grid_col":2,"grid_row":2,
         "description_seed":"A vaulted room with cracked obsidian floor. At its centre: carved from solid granite, ten feet tall.",
         "exits":["f3_gauntlet","f3_workshop"],"requires_key":False},
    ],
    4: [
        {"id":"f4_entrance",      "name":"Dragon's Approach","type":"Entrance","grid_col":0,"grid_row":1,
         "description_seed":"The ceiling vaults impossibly high. Scorched stone. The heat is palpable before you see the source.",
         "exits":["f4_inferno_hall"],"requires_key":False},
        {"id":"f4_inferno_hall",  "name":"Inferno Hall",    "type":"Trap",    "grid_col":1,"grid_row":0,
         "description_seed":"Gouts of flame shoot from floor vents. The pattern is almost predictable.",
         "exits":["f4_entrance","f4_hoard","f4_riddle_vault"],"requires_key":False,"trap":"fire_trap"},
        {"id":"f4_hoard",         "name":"Dragon Hoard",    "type":"Treasure","grid_col":2,"grid_row":0,
         "description_seed":"Gold coins cover the floor ankle-deep. Gems catch the firelight. The smell of sulphur is overwhelming.",
         "exits":["f4_inferno_hall"],"requires_key":False},
        {"id":"f4_riddle_vault",  "name":"Riddle Vault",    "type":"Puzzle",  "grid_col":1,"grid_row":2,
         "description_seed":"A sealed door bearing a carved inscription. No lock. No hinges. Only the question it poses.",
         "exits":["f4_entrance","f4_dragon_throne"],"requires_key":False,"puzzle":"riddle_clock"},
        {"id":"f4_dragon_throne", "name":"Dragon's Throne", "type":"Boss",    "grid_col":2,"grid_row":2,
         "description_seed":"The Bone Dragon does not move when you enter. It was waiting. It has always been waiting.",
         "exits":["f4_riddle_vault"],"requires_key":False},
    ],
}

ROOM_ICONS = {
    "Entrance": "&#9654;",
    "Combat":   "&#9876;",
    "Trap":     "&#9888;",
    "Treasure": "&#9670;",
    "Rest":     "&#128159;",
    "Puzzle":   "&#10067;",
    "Boss":     "&#9760;",
}


def load_dungeon_map():
    f = _dungeon_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {}


def save_dungeon_map(data):
    _dungeon_file().write_text(json.dumps(data, indent=2))


def generate_all_floors():
    dungeon_map = {}
    for floor_num, templates in FLOOR_TEMPLATES.items():
        rooms = []
        for t in templates:
            room = {k: v for k, v in t.items() if k not in ("minor_enemy", "trap", "puzzle")}
            room["visited"]       = (room["type"] == "Entrance")
            room["cleared"]       = False
            if "minor_enemy" in t:  # PHASE 3 added — randomly pick from enemies.json
                floor_enemies = _load_floor_enemies(floor_num)
                if floor_enemies:
                    room["enemies"] = [_normalize_enemy(random.choice(floor_enemies))]
                else:
                    room["enemies"] = [t["minor_enemy"]]  # fallback to old int key
            else:
                room["enemies"] = []
            room["traps"]         = [t["trap"]]         if "trap"         in t else []
            room["puzzle_id"]     = t.get("puzzle")
            room["puzzle_solved"] = False
            room["items"]         = []
            room["npcs"]          = _npcs_for_room(room["id"])
            rooms.append(room)
        # PHASE 4 added — assign lore notes to 1-2 non-entrance non-boss rooms
        notes = LORE_NOTES.get(floor_num, [])
        if notes:
            eligible = [r for r in rooms if r["type"] not in ("Entrance", "Boss")]
            count    = min(random.randint(1, 2), len(eligible))
            chosen   = random.sample(eligible, count) if count else []
            shuffled = list(notes)
            random.shuffle(shuffled)
            for i, r in enumerate(chosen):
                r["lore_note"] = shuffled[i % len(shuffled)]
        # Assign atmosphere flavour text from floor theme
        theme   = FLOOR_THEMES.get(floor_num, {})
        flavors = list(theme.get("room_flavor", []))
        if flavors:
            random.shuffle(flavors)
            for i, r in enumerate(rooms):
                r["atmosphere_text"] = flavors[i % len(flavors)]

        # Floor 3: promote ~40 % of eligible rooms to Puzzle type for denser riddle density
        if floor_num == 3:
            _extra_puzzles = ["riddle_footsteps", "riddle_echo"]
            _eligible      = [r for r in rooms if r["type"] not in ("Entrance", "Boss", "Puzzle")]
            _count         = max(1, round(len(_eligible) * 0.4))
            _targets       = random.sample(_eligible, min(_count, len(_eligible)))
            _ppool         = list(_extra_puzzles)
            random.shuffle(_ppool)
            for j, r in enumerate(_targets):
                r["type"]          = "Puzzle"
                r["puzzle_id"]     = _ppool[j % len(_ppool)]
                r["puzzle_solved"] = False
                r["enemies"]       = []
                r["traps"]         = []

        dungeon_map[str(floor_num)] = rooms
    save_dungeon_map(dungeon_map)
    return dungeon_map


def get_floor_rooms(floor_num):
    return load_dungeon_map().get(str(floor_num), [])


def get_room(floor_num, room_id):
    for r in get_floor_rooms(floor_num):
        if r["id"] == room_id:
            return r
    return None


def get_current_room(floor_num=None, room_id=None):
    #Return full room JSON for the player's current position.
    #Reads floor and room from game_state.json when not supplied.
    if floor_num is None or room_id is None:
        game_state_file = BASE / "game_state.json"
        if game_state_file.exists():
            state = json.loads(game_state_file.read_text())
            floor_num = state.get("floor", 1)
            room_id   = state.get("current_room_id") or get_entrance_room_id(floor_num)
        else:
            floor_num = 1
            room_id   = get_entrance_room_id(1)
    room = get_room(floor_num, room_id)
    if room and room.get("puzzle_id") and not room.get("puzzle_solved"):
        room = dict(room)
        room["puzzle_text"] = PUZZLES.get(room["puzzle_id"], {}).get("text")
    return room


def get_entrance_room_id(floor_num):
    for r in get_floor_rooms(floor_num):
        if r["type"] == "Entrance":
            return r["id"]
    rooms = get_floor_rooms(floor_num)
    return rooms[0]["id"] if rooms else None


def get_boss_room_id(floor_num):
    for r in get_floor_rooms(floor_num):
        if r["type"] == "Boss":
            return r["id"]
    return None


def mark_room_cleared(room_id, floor_num):
    dungeon_map = load_dungeon_map()
    for r in dungeon_map.get(str(floor_num), []):
        if r["id"] == room_id:
            r["cleared"] = True
            break
    save_dungeon_map(dungeon_map)


def get_floor_theme(floor_num):
    """Return display metadata for the given floor's theme."""
    t = FLOOR_THEMES.get(floor_num, {})
    return {
        "name":         t.get("name", "Unknown"),
        "color_accent": t.get("color_accent", "#c9a227"),
        "atmosphere":   t.get("atmosphere", ""),
    }


def get_map_for_frontend(floor_num, current_room_id=None):
    result = []
    for r in get_floor_rooms(floor_num):
        puzzle_data = None
        pid = r.get("puzzle_id")
        if r.get("type") == "Puzzle" and pid and not r.get("puzzle_solved"):
            puzzle_data = {"prompt": PUZZLES.get(pid, {}).get("text", "Solve the puzzle:")}
        result.append({
            "id":             r["id"],
            "name":           r["name"],
            "type":           r["type"],
            "visited":        r.get("visited", False),
            "cleared":        r.get("cleared", False),
            "grid_col":       r.get("grid_col", 0),
            "grid_row":       r.get("grid_row", 0),
            "exits":          r.get("exits", []),
            "puzzle_solved":  r.get("puzzle_solved", False),
            "puzzle":         puzzle_data,
            "npcs":           r.get("npcs", []),
            "is_current":     (r["id"] == current_room_id),
            "icon":           ROOM_ICONS.get(r["type"], "?"),
            "atmosphere_text":r.get("atmosphere_text", ""),
        })
    return result


def get_puzzle_text(room_id, floor_num):
    room = get_room(floor_num, room_id)
    if not room or not room.get("puzzle_id"):
        return None
    return PUZZLES.get(room["puzzle_id"], {}).get("text")


def move_to_room(room_id, current_room_id, floor_num):
    if current_room_id:
        current = get_room(floor_num, current_room_id)
        if current and room_id not in current.get("exits", []):
            return {"success": False, "error": f"'{room_id}' is not adjacent to current room."}

    room = get_room(floor_num, room_id)
    if not room:
        return {"success": False, "error": f"Room '{room_id}' not found on floor {floor_num}."}

    dungeon_map = load_dungeon_map()
    floor_rooms = dungeon_map.get(str(floor_num), [])
    for r in floor_rooms:
        if r["id"] == room_id:
            r["visited"] = True
            break

    result = {
        "success":              True,
        "room_id":              room_id,
        "room_name":            room["name"],
        "room_type":            room["type"],
        "description_seed":     room["description_seed"],
        "exits":                room.get("exits", []),
        "cleared":              room.get("cleared", False),
        "puzzle_id":            room.get("puzzle_id"),
        "puzzle_solved":        room.get("puzzle_solved", False),
        "puzzle_text":          None,
        "trap_triggered":       None,
        "trap_result":          None,
        "enemy":                None,
        "loot":                 None,
        "gold_gained":          0,
        "rest_available":       room["type"] == "Rest",
        "xp_awarded":           None,
        "dice_rolls_this_turn": [],
    }

    if room["type"] == "Puzzle" and not room.get("puzzle_solved") and room.get("puzzle_id"):
        result["puzzle_text"] = PUZZLES.get(room["puzzle_id"], {}).get("text")

    if room["type"] == "Trap" and not room.get("cleared") and room.get("traps"):
        trap_def = TRAP_TYPES.get(room["traps"][0], {})
        trap_res = _resolve_trap(trap_def)
        result["trap_triggered"]       = trap_def.get("name", "Trap")
        result["trap_result"]          = trap_res
        result["dice_rolls_this_turn"] = trap_res.get("dice_rolls", [])
        if trap_res.get("survived"):
            import character_manager as chars
            result["xp_awarded"] = chars.award_xp(25, "trap_survived")
        for r in floor_rooms:
            if r["id"] == room_id:
                r["cleared"] = True
                result["cleared"] = True
                break

    elif room["type"] == "Treasure" and not room.get("cleared"):
        loot = TREASURE_LOOT.get(floor_num, [])
        gold, items_added = _apply_loot(loot)
        result["loot"]        = items_added
        result["gold_gained"] = gold
        for r in floor_rooms:
            if r["id"] == room_id:
                r["cleared"] = True
                r["items"]   = result["loot"]
                result["cleared"] = True
                break

    elif room["type"] == "Combat" and not room.get("cleared") and room.get("enemies"):
        first_enemy = room["enemies"][0]
        if isinstance(first_enemy, dict):  # PHASE 3 added — full enemy dict from enemies.json
            result["enemy"] = dict(first_enemy)
        else:
            result["enemy"] = dict(MINOR_ENEMIES.get(first_enemy, MINOR_ENEMIES[1]))

    save_dungeon_map(dungeon_map)
    return result


def check_puzzle(room_id, floor_num, answer):
    room = get_room(floor_num, room_id)
    if not room or room.get("type") != "Puzzle":
        return {"success": False, "error": "Not a puzzle room."}
    if room.get("puzzle_solved"):
        return {"correct": True, "already_solved": True, "message": "You have already solved this puzzle."}

    puzzle_id = room.get("puzzle_id")
    if not puzzle_id:
        return {"success": False, "error": "No puzzle data found."}

    puzzle = PUZZLES.get(puzzle_id, {})
    if answer.strip().lower() == puzzle.get("answer", "").lower():
        dungeon_map = load_dungeon_map()
        for r in dungeon_map.get(str(floor_num), []):
            if r["id"] == room_id:
                r["puzzle_solved"] = True
                r["cleared"]       = True
                break
        save_dungeon_map(dungeon_map)

        import character_manager as chars
        reward = puzzle.get("reward", {"xp": 50})
        xp_result = chars.award_xp(reward.get("xp", 50), "puzzle_solved") if reward.get("xp") else None
        if reward.get("gold"):
            _add_gold(reward["gold"])
        return {
            "correct":    True,
            "message":    "The puzzle yields. The inscription fades. The way forward opens.",
            "reward":     reward,
            "xp_awarded": xp_result,
        }

    return {"correct": False, "message": "That is not the answer. The stone inscription remains cold and silent."}


def _resolve_trap(trap_def):
    import combat_manager as combat
    import character_manager as chars

    save_ab  = trap_def.get("save", "DEX")
    dc       = trap_def.get("dc", 13)
    dice_str = trap_def.get("damage_dice", "2d6")
    dmg_type = trap_def.get("damage_type", "piercing")

    save_res   = combat.roll_saving_throw(save_ab, dc)
    num_d, sides = (int(x) for x in dice_str.split("d"))
    raw_dmg    = sum(random.randint(1, sides) for _ in range(num_d))
    actual_dmg = raw_dmg // 2 if save_res["success"] else raw_dmg

    dice_rolls = [
        {"die": "d20",    "result": save_res["roll"], "purpose": f"{save_ab} save vs {trap_def.get('name','trap')} DC {dc}"},
        {"die": dice_str, "result": raw_dmg,          "purpose": f"{trap_def.get('name','trap')} damage"},
    ]

    char      = chars.load_character()
    hp_result = combat.apply_damage_to_character(char, actual_dmg)

    condition_applied = None
    if not save_res["success"] and trap_def.get("condition_on_fail"):
        char = chars.load_character()
        char["combat"]["conditions"].append({
            "name": trap_def["condition_on_fail"], "source": trap_def.get("name","trap"),
            "duration_turns": 3, "effects": []
        })
        chars.CHARACTER_FILE.write_text(json.dumps(char, indent=2))
        condition_applied = trap_def["condition_on_fail"]

    return {
        "trap_name":         trap_def.get("name", "Trap"),
        "save_ability":      save_ab,
        "dc":                dc,
        "save_roll":         save_res["roll"],
        "save_total":        save_res["total"],
        "save_success":      save_res["success"],
        "damage_rolled":     raw_dmg,
        "damage_taken":      actual_dmg,
        "damage_type":       dmg_type,
        "hp_after":          hp_result["remaining_hp"],
        "condition_applied": condition_applied,
        "survived":          hp_result["remaining_hp"] > 0,
        "dice_rolls":        dice_rolls,
        "note": (
            f"{save_ab} save {save_res['total']} vs DC {dc} — "
            f"{'SUCCESS. Half' if save_res['success'] else 'FAIL. Full'} damage: {actual_dmg} {dmg_type}."
        ),
    }


def _apply_loot(loot_list):
    import character_manager as chars
    char = chars.load_character()
    gold_gained = 0
    items_added = []
    for entry in loot_list:
        if "gold_range" in entry:  # PHASE 4 added — random gold range by floor
            lo, hi = entry["gold_range"]
            gold_gained += random.randint(lo, hi)
            continue
        if "gold_value" in entry:
            gold_gained += entry["gold_value"]
            continue
        item_id = entry.get("item_id")
        qty     = entry.get("qty", entry.get("quantity", 1))
        if not item_id:
            continue
        cat = chars.ITEM_CATALOG.get(item_id, {})
        equipment = char.get("equipment", [])
        existing = next((e for e in equipment if e.get("item_id") == item_id), None)
        if existing:
            existing["quantity"] = existing.get("quantity", 0) + qty
        else:
            equipment.append({"item_id":item_id,"name":cat.get("name",item_id),
                               "weight":cat.get("weight",0),"type":cat.get("type",""),
                               "description":cat.get("description",""),
                               "equipped":False,"quantity":qty})
        char["equipment"] = equipment
        items_added.append({"item_id":item_id,"name":cat.get("name",item_id),"qty":qty})
    char["currency"]["gp"] = char.get("currency", {}).get("gp", 0) + gold_gained
    chars.CHARACTER_FILE.write_text(json.dumps(char, indent=2))
    return gold_gained, items_added


def roll_enemy_loot(floor_num, is_boss=False):
    import character_manager as chars
    items_dropped = []
    if is_boss:
        for item_id, qty in BOSS_LOOT_GUARANTEED.get(floor_num, []):
            chars.add_item_to_equipment(item_id, qty)
            items_dropped.append({"item_id": item_id, "qty": qty,
                                   "name": chars.ITEM_CATALOG.get(item_id, {}).get("name", item_id)})
    else:
        for item_id, chance in ENEMY_LOOT_TABLES.get(floor_num, []):
            if random.random() < chance:
                chars.add_item_to_equipment(item_id, 1)
                items_dropped.append({"item_id": item_id, "qty": 1,
                                       "name": chars.ITEM_CATALOG.get(item_id, {}).get("name", item_id)})
    return items_dropped


def _add_gold(amount):
    import character_manager as chars
    char = chars.load_character()
    char["currency"]["gp"] += amount
    chars.CHARACTER_FILE.write_text(json.dumps(char, indent=2))


HUB_LOCATIONS = [
    {
        "id":          "ironwood_inn",
        "name":        "Ironwood Inn",
        "icon":        "&#127867;",
        "description": "Warm firelight, the smell of stew. Mira tends the bar.",
        "npc":         "innkeeper_mira",
    },
    {
        "id":          "village_market",
        "name":        "Village Market",
        "icon":        "&#127981;",
        "description": "Stalls of supplies and sundries. Prices fair, stock uncertain.",
        "npc":         None,
    },
    {
        "id":          "notice_board",
        "name":        "Notice Board",
        "icon":        "&#128204;",
        "description": "Weathered parchment pinned over older parchment. Bounties and warnings.",
        "npc":         None,
    },
    {
        "id":          "ruined_shrine",
        "name":        "Ruined Shrine",
        "icon":        "&#128682;",
        "description": "A crumbled stone altar, still faintly warm. One blessing remains in it.",
        "npc":         None,
    },
    {
        "id":          "dungeon_entrance",
        "name":        "Dungeon Entrance",
        "icon":        "&#9660;",
        "description": "The iron gate to Ironwood Dungeon. Cold air rises from below.",
        "npc":         None,
    },
]


def generate_surface_hub():
    return HUB_LOCATIONS
