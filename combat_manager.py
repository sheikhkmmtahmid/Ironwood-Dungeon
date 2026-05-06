import json
import random
import re
import threading
from pathlib import Path
import character_manager as chars

BASE = Path(__file__).parent

CHARACTER_FILE    = BASE / "character.json"
COMBAT_STATE_FILE = BASE / "combat_state.json"

_ctx = threading.local()

def set_room_code(rc):
    _ctx.room_code = (rc or "SOLO").upper()

def _rc():
    return getattr(_ctx, "room_code", "SOLO")

def _state_file():
    return BASE / f"game_state_{_rc()}.json"

# Keep for any old references still lingering
GAME_STATE_FILE = BASE / "game_state_SOLO.json"


ENEMY_RULES = {
    "Dungeon Troll": {
        "id": "enemy_dungeon_troll",
        "name": "Dungeon Troll",
        "ac": 12,
        "initiative_bonus": 0,
        "attack_bonus": 3,
        "damage_dice": "1d8+2",
        "damage_type": "bludgeoning",
        "xp": 100,
        "max_hp": 22,
        "phase": 1,             # PHASE 3 added
        "phase_threshold": 0.5, # PHASE 3 added
        "num_attacks": 1,       # PHASE 3 added
        "regeneration": 3,      # PHASE 3 added — regain 3 HP at start of each turn
        "special_abilities": [], # PHASE 3 added
    },
    "Shadow Wraith": {
        "id": "enemy_shadow_wraith",
        "name": "Shadow Wraith",
        "ac": 13,
        "initiative_bonus": 2,
        "attack_bonus": 4,
        "damage_dice": "1d8+2",
        "damage_type": "necrotic",
        "xp": 200,
        "max_hp": 35,
        "phase": 1,             # PHASE 3 added
        "phase_threshold": 0.5, # PHASE 3 added
        "num_attacks": 1,       # PHASE 3 added
        "special_abilities": ["shadow_step"],  # PHASE 3 added
        "special_attack": {
            "trigger": "on_hit",
            "save_ability": "CON",
            "save_dc": 13,
            "condition": "Frightened",
            "duration_turns": 1,
            "description": "The wraith's necrotic touch fills the target with supernatural dread."
        }
    },
    "Stone Golem": {
        "id": "enemy_stone_golem",
        "name": "Stone Golem",
        "ac": 15,
        "initiative_bonus": -1,
        "attack_bonus": 5,
        "damage_dice": "1d10+3",
        "damage_type": "bludgeoning",
        "xp": 450,
        "max_hp": 52,
        "phase": 1,             # PHASE 3 added
        "phase_threshold": 0.5, # PHASE 3 added
        "num_attacks": 1,       # PHASE 3 added
        "special_abilities": ["slow"],  # PHASE 3 added — applies Slowed on hit
        "special_attack": {
            "trigger": "on_hit",
            "save_ability": "STR",
            "save_dc": 14,
            "condition": "Prone",
            "duration_turns": 1,
            "description": "The golem's crushing slam drives the target to the ground."
        }
    },
    "Bone Dragon": {
        "id": "enemy_bone_dragon",
        "name": "Bone Dragon",
        "ac": 16,
        "initiative_bonus": 2,
        "attack_bonus": 6,
        "damage_dice": "2d6+3",
        "damage_type": "piercing",
        "xp": 1100,
        "max_hp": 78,
        "phase": 1,             # PHASE 3 added
        "phase_threshold": 0.5, # PHASE 3 added
        "num_attacks": 1,       # PHASE 3 added
        "special_abilities": ["bone_shards"],  # PHASE 3 added — AoE on even rounds
        "special_attack": {
            "trigger": "on_hit",
            "save_ability": "CON",
            "save_dc": 15,
            "condition": "Poisoned",
            "duration_turns": 2,
            "description": "Necrotic venom from the dragon's fangs poisons the target."
        }
    }
}


def load_character():
    return json.loads(CHARACTER_FILE.read_text())


def save_character(character):
    CHARACTER_FILE.write_text(json.dumps(character, indent=2))


def load_game_state():
    return json.loads(_state_file().read_text())


def save_game_state(state):
    _state_file().write_text(json.dumps(state, indent=2))


def reset_combat_state():
    if COMBAT_STATE_FILE.exists():
        COMBAT_STATE_FILE.unlink()


def load_combat_state():
    if not COMBAT_STATE_FILE.exists():
        return {
            "active": False,
            "round": 0,
            "turn_index": 0,
            "turn_order": [],
            "concentration": {},
            "conditions": [],
            "last_event": None
        }

    try:
        return json.loads(COMBAT_STATE_FILE.read_text())
    except Exception:
        return {
            "active": False,
            "round": 0,
            "turn_index": 0,
            "turn_order": [],
            "concentration": {},
            "conditions": [],
            "last_event": None
        }


def save_combat_state(combat_state):
    COMBAT_STATE_FILE.write_text(json.dumps(combat_state, indent=2))


def sync_game_state_from_character():
    character = load_character()
    state = load_game_state()

    identity = character["identity"]
    state["player_name"] = identity["character_name"]
    effective_max = _effective_max_hp(character)
    if character["combat"]["current_hp"] > effective_max:
        character["combat"]["current_hp"] = effective_max
        save_character(character)

    state["hp"]          = character["combat"]["current_hp"]
    state["max_hp"]      = effective_max
    state["xp"]          = identity["xp"]
    state["level"]       = identity["level"]
    state["xp_to_next"]  = chars.XP_THRESHOLDS.get(identity["level"] + 1)  # PHASE 3 added — full table

    save_game_state(state)
    return state


def roll_d20(advantage=False, disadvantage=False):
    r1 = random.randint(1, 20)
    rolls = [r1]

    if advantage or disadvantage:
        r2 = random.randint(1, 20)
        rolls.append(r2)

        if advantage and not disadvantage:
            result = max(r1, r2)
        elif disadvantage and not advantage:
            result = min(r1, r2)
        else:
            result = r1
    else:
        result = r1

    return {
        "die": "d20",
        "rolls": rolls,
        "result": result,
        "advantage": advantage,
        "disadvantage": disadvantage
    }


# PHASE 1 added — central d20+modifier helper; all attack/check rolls should use this
def roll_with_advantage(modifier, advantage=False, disadvantage=False):
    """Roll d20 + modifier with advantage/disadvantage applied per 5e rules."""
    roll = roll_d20(advantage=advantage, disadvantage=disadvantage)
    return {
        "die": "d20",
        "rolls": roll["rolls"],
        "result": roll["result"],
        "modifier": modifier,
        "total": roll["result"] + modifier,
        "advantage": roll["advantage"],
        "disadvantage": roll["disadvantage"],
    }


def roll_dice(dice_expr, multiplier=1):
    """
    Supports:
    1d8
    2d6
    1d10+3
    2d8-1

    Critical hits pass multiplier=2 to double dice, not modifiers.
    """
    match = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", dice_expr.strip())
    if not match:
        raise ValueError(f"Invalid dice expression: {dice_expr}")

    count = int(match.group(1)) * multiplier
    sides = int(match.group(2))
    modifier = int(match.group(3) or 0)

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    return {
        "die": dice_expr,
        "rolls": rolls,
        "modifier": modifier,
        "result": total
    }


def _lucky_reroll(roll_result, character):
    """Halfling Lucky: reroll a natural 1 once (must keep new roll)."""
    if roll_result == 1 and character.get("identity", {}).get("race") == "Halfling":
        return random.randint(1, 20), True
    return roll_result, False


def _get_exhaustion_level(character):
    return character.get("combat", {}).get("exhaustion_level", 0)


def _effective_max_hp(character):
    """Return effective max HP: halved at exhaustion level 4+."""
    max_hp = character["combat"]["max_hp"]
    if _get_exhaustion_level(character) >= 4:
        return max(1, max_hp // 2)
    return max_hp


def get_enemy_rules(enemy_name):
    if enemy_name not in ENEMY_RULES:
        return {
            "id": "enemy_unknown",
            "name": enemy_name,
            "ac": 12,
            "initiative_bonus": 0,
            "attack_bonus": 4,
            "damage_dice": "1d6+2",
            "damage_type": "bludgeoning",
            "xp": 50
        }

    return ENEMY_RULES[enemy_name]


def get_active_enemy():
    state = load_game_state()
    enemy = state.get("enemy")

    if not enemy or enemy.get("hp", 0) <= 0:
        return None

    rules = get_enemy_rules(enemy["name"])

    # PHASE 3 fixed — rules provide defaults; game_state always wins (preserves phase, hp, etc.)
    merged = dict(rules)
    merged.update(enemy)
    return merged


def start_combat_if_needed(party_members=None):
    character = load_character()
    enemy = get_active_enemy()
    combat_state = load_combat_state()

    if not enemy:
        reset_combat_state()
        return load_combat_state()

    if combat_state.get("active") and combat_state.get("enemy_name") == enemy["name"]:
        return combat_state

    order = []

    if party_members:
        for pm in party_members:
            char = pm.get("character") or {}
            pname = pm.get("player_name", "")
            init_mod = char.get("combat", {}).get("initiative", 0)
            roll = roll_d20()
            total = roll["result"] + init_mod
            order.append({
                "id":               f"player_{pname}",
                "name":             char.get("identity", {}).get("character_name", pname),
                "player_name":      pname,
                "type":             "player",
                "initiative_roll":  roll["result"],
                "initiative_bonus": init_mod,
                "initiative_total": total,
            })
    else:
        roll = roll_d20()
        total = roll["result"] + character["combat"]["initiative"]
        order.append({
            "id":               "player",
            "name":             character["identity"]["character_name"],
            "player_name":      character["identity"].get("player_name",
                                character["identity"]["character_name"]),
            "type":             "player",
            "initiative_roll":  roll["result"],
            "initiative_bonus": character["combat"]["initiative"],
            "initiative_total": total,
        })

    enemy_roll  = roll_d20()
    enemy_total = enemy_roll["result"] + enemy["initiative_bonus"]
    order.append({
        "id":               enemy["id"],
        "name":             enemy["name"],
        "type":             "enemy",
        "initiative_roll":  enemy_roll["result"],
        "initiative_bonus": enemy["initiative_bonus"],
        "initiative_total": enemy_total,
    })

    order.sort(key=lambda x: x["initiative_total"], reverse=True)

    combat_state = {
        "active":        True,
        "round":         1,
        "turn_index":    0,
        "enemy_name":    enemy["name"],
        "turn_order":    order,
        "concentration": {},
        "conditions":    [],
        "last_event":    None,
    }
    save_combat_state(combat_state)
    return combat_state


def current_actor(combat_state):
    if not combat_state.get("turn_order"):
        return None

    return combat_state["turn_order"][combat_state["turn_index"]]


def advance_turn(combat_state):
    if not combat_state.get("active"):
        return combat_state

    combat_state["turn_index"] += 1

    if combat_state["turn_index"] >= len(combat_state["turn_order"]):
        combat_state["turn_index"] = 0
        combat_state["round"] += 1

    # Tick down timed combat conditions. remove those that have expired.
    still_active = []
    for cond in combat_state.get("conditions", []):
        dt = cond.get("duration_turns")
        if dt is None:
            still_active.append(cond)
        else:
            cond["duration_turns"] = dt - 1
            if cond["duration_turns"] > 0:
                still_active.append(cond)
    combat_state["conditions"] = still_active

    # Tick down concentration duration; clear the spell when it expires.
    conc = combat_state.get("concentration", {})
    if conc and "duration_turns_remaining" in conc:
        conc["duration_turns_remaining"] -= 1
        if conc["duration_turns_remaining"] <= 0:
            _CONC_FLAGS = {
                "Hunter's Mark":               "hunters_mark_active",
                "Bless":                        "bless_active",
                "Fog Cloud":                    "fog_cloud_active",
                "Faerie Fire":                  "faerie_fire_active",
                "Guidance":                     "guidance_active",
                "Protection from Evil and Good":"protection_active",
                "Invisibility":                 "invisible",              # PHASE 3 added
                "Call Lightning":               "call_lightning_turns",   # PHASE 3 added
                "Hypnotic Pattern":             "hypnotic_pattern_active", # PHASE 3 added
            }
            flag = _CONC_FLAGS.get(conc.get("spell", ""))
            if flag:
                combat_state[flag] = False
            combat_state["concentration"] = {}
        else:
            combat_state["concentration"] = conc

    save_combat_state(combat_state)
    return combat_state


def get_attack_by_name(character, weapon_name=None):
    attacks = character.get("attacks", [])

    if not attacks:
        raise ValueError("Character has no attacks.")

    if not weapon_name:
        return attacks[0]

    for attack in attacks:
        if attack["name"].lower() == weapon_name.lower():
            return attack

    raise ValueError(f"No attack named '{weapon_name}' found on character sheet.")


def get_damage_bonus(character, attack):
    """
    Phase 2 basic rule:
    weapon damage bonus = attack_bonus - proficiency bonus.
    This works because character_manager already calculated attack_bonus.
    """
    pb = character["identity"]["prof_bonus"]
    bonus = attack["attack_bonus"] - pb

    if character["identity"]["class"] == "Fighter":
        if character.get("fighting_style") == "Dueling":
            props = attack.get("properties", [])
            if "two-handed" not in props:
                bonus += 2

    return bonus


def _check_concentration_on_damage(damage):
    combat_state = load_combat_state()
    if not combat_state.get("concentration"):
        return None
    dc = max(10, damage // 2)
    result = roll_saving_throw("CON", dc)
    spell_name = combat_state["concentration"].get("spell", "spell")
    if not result["success"]:
        # Use spell_manager's helper if available to clear all spell effects cleanly.
        # Avoid circular import: clear known flags directly here.
        _CONCENTRATION_FLAGS = {
            "Hunter's Mark":               "hunters_mark_active",
            "Bless":                        "bless_active",
            "Fog Cloud":                    "fog_cloud_active",
            "Faerie Fire":                  "faerie_fire_active",
            "Guidance":                     "guidance_active",
            "Protection from Evil and Good":"protection_active",
            "Invisibility":                 "invisible",              # PHASE 3 added
            "Call Lightning":               "call_lightning_turns",   # PHASE 3 added
            "Hypnotic Pattern":             "hypnotic_pattern_active", # PHASE 3 added
        }
        flag = _CONCENTRATION_FLAGS.get(spell_name)
        if flag:
            combat_state[flag] = False
        combat_state["concentration"] = {}
        save_combat_state(combat_state)
        return {"broke": True, "dc": dc, "roll": result["roll"], "total": result["total"], "spell_lost": spell_name,
                "summary": f"Concentration check for {spell_name}: {result['total']} vs DC {dc} — failed. {spell_name} ends."}
    return {"broke": False, "dc": dc, "roll": result["roll"], "total": result["total"],
            "summary": f"Concentration check for {spell_name}: {result['total']} vs DC {dc} — maintained."}


def apply_damage_to_character(character, damage):
    combat = character["combat"]

    if _get_exhaustion_level(character) >= 6:
        combat["current_hp"] = 0
        character["combat"] = combat
        character = _add_condition(character, "Dead", source="exhaustion",
                                   effects=["Reached exhaustion level 6."])
        save_character(character)
        sync_game_state_from_character()
        return {
            "damage_taken": damage,
            "concentration_check": None,
            "remaining_hp": 0,
            "temp_hp": 0,
            "is_down": True,
        }

    temp_hp = combat.get("temp_hp", 0)
    remaining_damage = damage

    if temp_hp > 0:
        absorbed = min(temp_hp, remaining_damage)
        temp_hp -= absorbed
        remaining_damage -= absorbed
        combat["temp_hp"] = temp_hp

    if remaining_damage > 0:
        combat["current_hp"] = max(0, combat["current_hp"] - remaining_damage)

    # Half-Orc Relentless Endurance: once per long rest, drop to 1 HP instead of 0
    if combat["current_hp"] <= 0 and character.get("identity", {}).get("race") == "Half-Orc":
        for trait in character.get("racial_traits", []):
            if trait.get("name") == "Relentless Endurance" and trait.get("uses_remaining", 0) > 0:
                combat["current_hp"] = 1
                trait["uses_remaining"] = 0
                break

    if combat["current_hp"] > 0:
        combat["death_saves"] = {"successes": 0, "failures": 0}

    character["combat"] = combat
    save_character(character)
    sync_game_state_from_character()

    concentration_result = _check_concentration_on_damage(remaining_damage)

    return {
        "damage_taken": damage,
        "concentration_check": concentration_result,
        "remaining_hp": combat["current_hp"],
        "temp_hp": combat.get("temp_hp", 0),
        "is_down": combat["current_hp"] <= 0
    }


def apply_damage_to_enemy(enemy_id, damage, damage_type=None):  # PHASE 3 added damage_type param
    state = load_game_state()
    enemy = state.get("enemy")

    if not enemy or enemy.get("hp", 0) <= 0:
        return {"enemy_remaining_hp": 0, "enemy_defeated": True}

    # PHASE 3 added — damage resistance: halve damage if enemy resists this type
    if damage_type and damage_type in enemy.get("damage_resistances", []):
        damage = max(1, damage // 2)

    # PHASE 3 added — undead_fortitude: CON save vs (5 + damage) to survive at 1 HP
    abilities = enemy.get("special_abilities", [])
    undead_fortitude_triggered = False
    if "undead_fortitude" in abilities and (enemy["hp"] - damage) <= 0:
        fortitude_dc   = 5 + damage
        fortitude_roll = random.randint(1, 20) + 2  # +2 CON (undead baseline)
        if fortitude_roll >= fortitude_dc:
            enemy["hp"] = 1
            state["enemy"] = enemy
            save_game_state(state)
            return {
                "enemy_remaining_hp": 1,
                "enemy_defeated": False,
                "undead_fortitude_triggered": True,
                "fortitude_dc": fortitude_dc,
                "fortitude_roll": fortitude_roll,
            }

    enemy["hp"] = max(0, enemy["hp"] - damage)

    # PHASE 3 added — boss phase transition: triggers at 50% HP, phase 1 → 2
    phase_transition  = False
    phase_narrative   = None
    _BOSS_NAMES       = {"Dungeon Troll", "Shadow Wraith", "Stone Golem", "Bone Dragon"}
    if (enemy["name"] in _BOSS_NAMES
            and enemy.get("phase", 1) == 1
            and enemy["hp"] > 0
            and enemy.get("max_hp")
            and enemy["hp"] <= enemy["max_hp"] * 0.5):
        phase_narrative  = _apply_boss_phase_2(state, enemy["name"])
        phase_transition = True
        enemy = state["enemy"]  # re-read after in-place mutation

    state["enemy"] = enemy
    save_game_state(state)

    xp_result = None
    if enemy["hp"] <= 0:
        combat_state = load_combat_state()
        combat_state["active"] = False
        combat_state["last_event"] = "enemy_defeated"
        save_combat_state(combat_state)

        rules      = get_enemy_rules(enemy["name"])
        xp_amount  = enemy.get("xp_reward", rules.get("xp", 0))  # PHASE 3 fixed — xp_reward first
        xp_result  = chars.award_xp(xp_amount, f"enemy_defeated:{enemy['name']}")
        sync_game_state_from_character()

    return {
        "enemy_remaining_hp": enemy["hp"],
        "enemy_defeated":     enemy["hp"] <= 0,
        "xp_awarded":         xp_result,
        "phase_transition":   phase_transition,   # PHASE 3 added
        "phase_narrative":    phase_narrative,    # PHASE 3 added
    }


def _apply_boss_phase_2(state, boss_name):  # PHASE 3 added
    """Upgrade boss to phase 2 in game_state["enemy"] in-place. Returns phase narrative string."""
    enemy = state["enemy"]
    enemy["phase"] = 2
    if boss_name == "Dungeon Troll":
        enemy["ac"] = 13
        enemy["attack_bonus"] = 5
        enemy["damage_dice"] = "2d6+2"
        enemy["num_attacks"] = 2
        enemy["regeneration"] = 0  # stops regenerating
        return (
            "The Dungeon Troll ROARS as its own blood fuels a berserker frenzy! "
            "Regeneration ceases — the pain only feeds its fury. PHASE 2: Rampage!"
        )
    if boss_name == "Shadow Wraith":
        enemy["ac"] = 14
        enemy["attack_bonus"] = 6
        enemy["damage_dice"] = "2d6+2"
        enemy["num_attacks"] = 2
        return (
            "The Shadow Wraith lets out a shriek that exists outside of sound. "
            "It fractures into void and reforms: darker, faster, hungrier. PHASE 2: Void Shroud!"
        )
    if boss_name == "Stone Golem":
        enemy["ac"] = 16
        enemy["attack_bonus"] = 7
        enemy["damage_dice"] = "1d12+3"
        enemy["num_attacks"] = 2
        return (
            "Fissures crack across the Stone Golem's body — then it REBUILDS, "
            "shedding its outer casing to reveal a denser, deadlier core. PHASE 2: Overclock!"
        )
    if boss_name == "Bone Dragon":
        enemy["ac"] = 17
        enemy["attack_bonus"] = 8
        enemy["damage_dice"] = "2d8+3"
        enemy["num_attacks"] = 2
        enemy.setdefault("special_abilities", [])
        if "necrotic_breath" not in enemy["special_abilities"]:
            enemy["special_abilities"].append("necrotic_breath")
        return (
            "The Bone Dragon ROARS, its ribcage splitting open to reveal a pulsing necrotic core. "
            "Shards of bone orbit it like a deadly halo. PHASE 2: Undying Fury!"
        )
    return "The enemy transforms, becoming far more dangerous!"


def _apply_life_drain(enemy, character, damage, dice_rolls):  # PHASE 3 added
    """On hit: CON save DC 13 or lose max HP equal to half damage dealt."""
    save_dc     = 13
    save_result = roll_saving_throw("CON", save_dc)
    dice_rolls.extend(save_result.get("dice_rolls_this_turn", []))
    if save_result["success"]:
        return {"triggered": True, "save_success": True, "max_hp_lost": 0,
                "dc": save_dc, "roll": save_result["roll"], "total": save_result["total"]}
    max_hp_lost = max(1, damage // 2)
    char = load_character()
    char["combat"]["max_hp"] = max(1, char["combat"]["max_hp"] - max_hp_lost)
    if char["combat"]["current_hp"] > char["combat"]["max_hp"]:
        char["combat"]["current_hp"] = char["combat"]["max_hp"]
    save_character(char)
    sync_game_state_from_character()
    return {"triggered": True, "save_success": False, "max_hp_lost": max_hp_lost,
            "dc": save_dc, "roll": save_result["roll"], "total": save_result["total"]}


def _apply_blood_drain(enemy, character, damage, dice_rolls):  # PHASE 3 added
    """On hit: grapple + drain 2d6 HP as bonus damage."""
    drain_roll = roll_dice("2d6")
    dice_rolls.append({"die": "2d6", "result": drain_roll["result"], "purpose": "Blood Drain"})
    hp_result   = apply_damage_to_character(character, drain_roll["result"])
    combat_state = load_combat_state()
    _add_combat_condition(combat_state, "Grappled", source=enemy["name"], duration_turns=2,
                          effects=["Grappled by vampire. Speed 0. Blood Drain persists."])
    save_combat_state(combat_state)
    return {"triggered": True, "extra_damage": drain_roll["result"],
            "player_hp_after": hp_result["remaining_hp"]}


def _resolve_bone_shards(enemy, character, dice_rolls):  # PHASE 3 added
    """Bone Dragon AoE on even rounds: DEX save DC 14, 3d6 piercing (half on success)."""
    save_dc     = 14
    dmg_roll    = roll_dice("3d6")
    save_result = roll_saving_throw("DEX", save_dc)
    dice_rolls.append({"die": "3d6", "result": dmg_roll["result"], "purpose": "Bone Shards damage"})
    dice_rolls.extend(save_result.get("dice_rolls_this_turn", []))
    actual_dmg  = dmg_roll["result"] // 2 if save_result["success"] else dmg_roll["result"]
    hp_result   = apply_damage_to_character(character, actual_dmg)
    return {"triggered": True, "save_dc": save_dc, "save_total": save_result["total"],
            "save_success": save_result["success"], "damage_rolled": dmg_roll["result"],
            "damage_taken": actual_dmg, "player_hp_after": hp_result["remaining_hp"]}


def _resolve_necrotic_breath(enemy, character, dice_rolls):  # PHASE 3 added
    """Bone Dragon phase 2: CON save DC 15, 6d6 necrotic (half on success). Once per encounter."""
    save_dc     = 15
    dmg_roll    = roll_dice("6d6")
    save_result = roll_saving_throw("CON", save_dc)
    dice_rolls.append({"die": "6d6", "result": dmg_roll["result"], "purpose": "Necrotic Breath damage"})
    dice_rolls.extend(save_result.get("dice_rolls_this_turn", []))
    actual_dmg  = dmg_roll["result"] // 2 if save_result["success"] else dmg_roll["result"]
    hp_result   = apply_damage_to_character(character, actual_dmg)
    return {"triggered": True, "save_dc": save_dc, "save_total": save_result["total"],
            "save_success": save_result["success"], "damage_rolled": dmg_roll["result"],
            "damage_taken": actual_dmg, "player_hp_after": hp_result["remaining_hp"]}


def _resolve_hellfire_orb(enemy, character, dice_rolls):  # PHASE 3 added
    """Once-per-encounter ranged spell attack (+5 vs AC), 4d6 fire damage."""
    attack_bonus = 5
    attack_roll  = roll_d20()
    total_attack = attack_roll["result"] + attack_bonus
    player_ac    = character["combat"]["armor_class"]
    is_crit      = attack_roll["result"] == 20
    hit          = attack_roll["result"] != 1 and (is_crit or total_attack >= player_ac)
    dice_rolls.append({"die": "d20", "result": attack_roll["result"], "purpose": "Hellfire Orb attack"})
    damage = 0
    if hit:
        dmg_roll = roll_dice("4d6", multiplier=2 if is_crit else 1)
        damage   = dmg_roll["result"]
        dice_rolls.append({"die": "4d6", "result": damage, "purpose": "Hellfire Orb fire damage"})
        apply_damage_to_character(character, damage)
    return {"triggered": True, "attack_roll": attack_roll["result"], "attack_total": total_attack,
            "hit": hit, "damage": damage, "damage_type": "fire", "critical": is_crit}


def resolve_enemy_turn():
    character    = load_character()
    enemy        = get_active_enemy()
    combat_state = load_combat_state()

    if character["combat"]["current_hp"] <= 0:
        return {
            "type": "enemy_turn",
            "summary": (
                f"{character['identity']['character_name']} is down at 0 HP. "
                f"The enemy looms over them as death saves begin."
            ),
            "dice_rolls_this_turn": [],
            "enemy_attack": None,
            "available_actions": get_available_combat_actions()
        }

    if not enemy:
        return {
            "type": "enemy_turn",
            "summary": "There is no active enemy.",
            "dice_rolls_this_turn": [],
            "enemy_attack": None
        }

    abilities   = enemy.get("special_abilities", [])
    dice_rolls  = []

    # Pre-attack effect

    # Regeneration (Dungeon Troll)
    regen_amount = 0
    if enemy.get("regeneration", 0) > 0 and enemy.get("phase", 1) == 1:
        regen_hp = int(enemy["regeneration"])
        _gs = load_game_state()
        _e  = _gs.get("enemy", {})
        old_hp    = _e.get("hp", 0)
        _e["hp"]  = min(_e.get("max_hp", old_hp), old_hp + regen_hp)
        regen_amount = _e["hp"] - old_hp
        _gs["enemy"] = _e
        save_game_state(_gs)
        enemy = get_active_enemy()
        if regen_amount > 0:
            dice_rolls.append({"die": f"+{regen_hp}", "result": regen_amount,
                                "purpose": f"{enemy['name']} Regeneration"})

    # Necrotic Breath (Bone Dragon once per encounter)
    necrotic_breath_result = None
    if "necrotic_breath" in abilities:
        _gs = load_game_state()
        _e  = _gs.get("enemy", {})
        used = _e.get("abilities_used", [])
        if "necrotic_breath" not in used:
            character = load_character()
            necrotic_breath_result = _resolve_necrotic_breath(enemy, character, dice_rolls)
            _e["abilities_used"] = used + ["necrotic_breath"]
            _gs["enemy"] = _e
            save_game_state(_gs)
            character = load_character()

    # Hellfire Orb (once per encounter when below 60% HP)
    hellfire_result = None
    if "hellfire_orb" in abilities:
        _gs = load_game_state()
        _e  = _gs.get("enemy", {})
        used = _e.get("abilities_used", [])
        if "hellfire_orb" not in used and _e.get("hp", 0) < _e.get("max_hp", 9999) * 0.6:
            character = load_character()
            hellfire_result = _resolve_hellfire_orb(enemy, character, dice_rolls)
            _e["abilities_used"] = used + ["hellfire_orb"]
            _gs["enemy"] = _e
            save_game_state(_gs)
            character = load_character()

    # Bone Shards (Bone Dragon every even round)
    bone_shards_result = None
    if "bone_shards" in abilities and combat_state.get("round", 1) % 2 == 0:
        character = load_character()
        bone_shards_result = _resolve_bone_shards(enemy, character, dice_rolls)
        character = load_character()

    # Main attack roll

    character = load_character()
    roll_context = get_attack_roll_context("enemy", "player")

    # PHASE 3: ability-based advantage modifiers
    ability_adv = False
    if "pack_tactics" in abilities:
        ability_adv = True
        roll_context["reasons"].append("Pack Tactics: advantage on attack rolls")
    if "shadow_step" in abilities:
        ability_adv = True
        roll_context["reasons"].append("Shadow Step: attacks from shadow with advantage")
    if "nimble_escape" in abilities:
        ability_adv = True
        roll_context["reasons"].append("Nimble Escape: hid before attacking, advantage")
    if "false_appearance" in abilities:
        _gs = load_game_state()
        _e  = _gs.get("enemy", {})
        if not _e.get("false_appearance_revealed"):
            ability_adv = True
            roll_context["reasons"].append("False Appearance: surprise strike with advantage")
            _e["false_appearance_revealed"] = True
            _gs["enemy"] = _e
            save_game_state(_gs)
    if ability_adv:
        if roll_context["disadvantage"]:
            roll_context["advantage"]    = False
            roll_context["disadvantage"] = False
            roll_context["reasons"].append("Ability advantage cancelled by existing disadvantage")
        else:
            roll_context["advantage"] = True

    attack_roll = roll_d20(
        advantage=roll_context["advantage"],
        disadvantage=roll_context["disadvantage"]
    )

    if combat_state.get("player_dodging"):
        combat_state["player_dodging"] = False
        save_combat_state(combat_state)

    total_attack = attack_roll["result"] + enemy["attack_bonus"]
    player_ac    = character["combat"]["armor_class"]

    is_nat_1 = attack_roll["result"] == 1
    is_crit  = attack_roll["result"] == 20
    hit      = False if is_nat_1 else (is_crit or total_attack >= player_ac)

    # Paralyzed: any hit within 5 ft is a critical hit (PHB)
    if hit and "paralyzed" in get_combat_condition_names(combat_state):
        is_crit = True

    dice_rolls.append({"die": "d20", "result": attack_roll["result"],
                        "purpose": f"{enemy['name']} attack roll"})

    damage = 0
    if hit:
        damage_result = roll_dice(enemy["damage_dice"], multiplier=2 if is_crit else 1)
        damage        = max(0, damage_result["result"])
        dice_rolls.append({"die": enemy["damage_dice"], "result": damage,
                            "purpose": f"{enemy['name']} damage"})
        hp_result = apply_damage_to_character(character, damage)
    else:
        hp_result = {
            "damage_taken": 0,
            "remaining_hp": character["combat"]["current_hp"],
            "temp_hp":       character["combat"].get("temp_hp", 0),
            "is_down":       character["combat"]["current_hp"] <= 0
        }

    # Post-hit ability effects

    character = load_character()

    # Martial Advantage extra 2d6 damage on hit
    martial_advantage_damage = 0
    if hit and "martial_advantage" in abilities:
        ma_roll = roll_dice("2d6")
        martial_advantage_damage = ma_roll["result"]
        damage += martial_advantage_damage
        dice_rolls.append({"die": "2d6", "result": martial_advantage_damage,
                            "purpose": "Martial Advantage bonus damage"})
        apply_damage_to_character(character, martial_advantage_damage)
        character = load_character()

    # Berserk: extra 1d6 damage when below 50% HP
    berserk_damage = 0
    if hit and "berserk" in abilities:
        _gs = load_game_state()
        _e  = _gs.get("enemy", {})
        if _e.get("hp", 0) < _e.get("max_hp", 9999) * 0.5:
            bk_roll = roll_dice("1d6")
            berserk_damage = bk_roll["result"]
            damage += berserk_damage
            dice_rolls.append({"die": "1d6", "result": berserk_damage,
                                "purpose": "Berserk bonus damage"})
            apply_damage_to_character(character, berserk_damage)
            character = load_character()

    # Life Drain CON save DC 13 or lose max HP
    life_drain_result = None
    if hit and "life_drain" in abilities:
        life_drain_result = _apply_life_drain(enemy, character, damage, dice_rolls)
        character = load_character()

    # Blood Drain grapple + 2d6 bonus HP drain
    blood_drain_result = None
    if hit and "blood_drain" in abilities:
        blood_drain_result = _apply_blood_drain(enemy, character, damage, dice_rolls)
        character = load_character()

    # Stone Golem Slow apply Slowed condition on hit (phase 1 only)
    if hit and "slow" in abilities and enemy.get("phase", 1) == 1:
        _cbt = load_combat_state()
        _add_combat_condition(_cbt, "slowed", source=enemy["name"], duration_turns=2,
                              effects=["Speed halved, disadvantage on attacks and DEX saves"])
        save_combat_state(_cbt)

    # Special attack (existing system keept for bosses)

    special_attack_result = None
    if hit and not is_nat_1:
        special = enemy.get("special_attack")
        if special and special.get("trigger") == "on_hit":
            target_condition = special["condition"]
            cbt_check = load_combat_state()
            immune = target_condition == "Frightened" and cbt_check.get("protection_active")
            if immune:
                special_attack_result = {
                    "ability": special["save_ability"], "dc": special["save_dc"],
                    "roll": None, "modifier": None, "total": None, "success": True,
                    "condition_applied": None, "description": "Immune (Protection from Evil and Good)"
                }
            else:
                save_result = roll_saving_throw(special["save_ability"], special["save_dc"])
                dice_rolls.extend(save_result.get("dice_rolls_this_turn", []))
                condition_applied = None
                if not save_result["success"]:
                    cbt = load_combat_state()
                    _add_combat_condition(cbt, target_condition, source=enemy["name"],
                                          duration_turns=special.get("duration_turns"),
                                          effects=[special.get("description", "")])
                    save_combat_state(cbt)
                    condition_applied = target_condition
                special_attack_result = {
                    "ability": special["save_ability"], "dc": special["save_dc"],
                    "roll": save_result["roll"], "modifier": save_result["modifier"],
                    "total": save_result["total"], "success": save_result["success"],
                    "condition_applied": condition_applied,
                    "description": special.get("description", "")
                }

    # Second attack second phase bosses 

    second_attack_result = None
    if enemy.get("num_attacks", 1) >= 2 and not hp_result.get("is_down", False):
        character = load_character()
        if character["combat"]["current_hp"] > 0:
            s_roll  = roll_d20()
            s_total = s_roll["result"] + enemy["attack_bonus"]
            s_crit  = s_roll["result"] == 20
            s_hit   = s_roll["result"] != 1 and (s_crit or s_total >= player_ac)
            dice_rolls.append({"die": "d20", "result": s_roll["result"],
                                "purpose": f"{enemy['name']} second attack roll"})
            s_damage = 0
            if s_hit:
                s_dmg    = roll_dice(enemy["damage_dice"], multiplier=2 if s_crit else 1)
                s_damage = max(0, s_dmg["result"])
                dice_rolls.append({"die": enemy["damage_dice"], "result": s_damage,
                                    "purpose": f"{enemy['name']} second attack damage"})
                s_hp = apply_damage_to_character(character, s_damage)
                character = load_character()
            else:
                s_hp = {"remaining_hp": character["combat"]["current_hp"], "is_down": False}
            second_attack_result = {
                "attack_roll": s_roll["result"], "attack_total": s_total,
                "hit": s_hit, "critical": s_crit, "damage": s_damage,
                "player_hp_after": s_hp["remaining_hp"],
                "player_down": s_hp.get("is_down", False)
            }

    # Build event

    character = load_character()
    final_player_hp = character["combat"]["current_hp"]

    event = {
        "type":                 "enemy_turn",
        "actor":                enemy["name"],
        "target":               character["identity"]["character_name"],
        "player_ac":            player_ac,
        "attack_roll":          attack_roll["result"],
        "attack_bonus":         enemy["attack_bonus"],
        "attack_total":         total_attack,
        "hit":                  hit,
        "critical":             is_crit,
        "natural_1":            is_nat_1,
        "damage":               damage,
        "damage_type":          enemy["damage_type"],
        "player_hp_after":      final_player_hp,
        "player_down":          final_player_hp <= 0,
        "special_attack":       special_attack_result,
        "second_attack":        second_attack_result,       # PHASE 3 added
        "regen_amount":         regen_amount,               # PHASE 3 added
        "bone_shards":          bone_shards_result,         # PHASE 3 added
        "necrotic_breath":      necrotic_breath_result,     # PHASE 3 added
        "hellfire_orb":         hellfire_result,            # PHASE 3 added
        "life_drain":           life_drain_result,          # PHASE 3 added
        "blood_drain":          blood_drain_result,         # PHASE 3 added
        "martial_advantage_dmg": martial_advantage_damage,  # PHASE 3 added
        "berserk_damage":       berserk_damage,             # PHASE 3 added
        "dice_rolls_this_turn": dice_rolls,
        "advantage_context":    roll_context,
        "summary": build_enemy_summary(enemy, character, total_attack, hit, is_crit, damage,
                                       hp_result, roll_context, is_nat_1, special_attack_result)
    }

    return event

'''
def build_enemy_summary(enemy, character, total_attack, hit, critical, damage, hp_result):
    if hit:
        crit_text = " Critical hit." if critical else ""
        return (
            f"{enemy['name']} attacks {character['identity']['character_name']} "
            f"with a total attack roll of {total_attack}.{crit_text} "
            f"It hits for {damage} {enemy['damage_type']} damage. "
            f"{character['identity']['character_name']} now has {hp_result['remaining_hp']} HP."
        )

    return (
        f"{enemy['name']} attacks {character['identity']['character_name']} "
        f"with a total attack roll of {total_attack}, but misses against AC "
        f"{character['combat']['armor_class']}."
    )
'''
def build_enemy_summary(enemy, character, total_attack, hit, critical, damage, hp_result, roll_context=None, natural_1=False, special_attack=None):
    adv_text = describe_advantage_context(roll_context)

    if natural_1:
        return (
            f"{enemy['name']} attacks {character['identity']['character_name']}."
            f"{adv_text} "
            f"Natural 1: automatic miss."
        )

    if hit:
        crit_text = " Critical hit: damage dice are doubled." if critical else ""
        special_text = ""
        if special_attack:
            name = character["identity"]["character_name"]
            if special_attack.get("condition_applied"):
                special_text = (
                    f" {name} fails a DC {special_attack['dc']} "
                    f"{special_attack['ability']} saving throw "
                    f"({special_attack['total']}) and becomes {special_attack['condition_applied']}."
                )
            else:
                special_text = (
                    f" {name} succeeds on a DC {special_attack['dc']} "
                    f"{special_attack['ability']} saving throw "
                    f"({special_attack['total']}) and resists the effect."
                )
        return (
            f"{enemy['name']} attacks {character['identity']['character_name']}."
            f"{adv_text} "
            f"Attack total {total_attack}.{crit_text} "
            f"It hits for {damage} {enemy['damage_type']} damage. "
            f"{character['identity']['character_name']} now has {hp_result['remaining_hp']} HP."
            f"{special_text}"
        )

    return (
        f"{enemy['name']} attacks {character['identity']['character_name']}."
        f"{adv_text} "
        f"Attack total {total_attack}, but misses against AC "
        f"{character['combat']['armor_class']}."
    )

'''
def resolve_player_attack(weapon_name=None):
    sync_game_state_from_character()

    character = load_character()
    enemy = get_active_enemy()

    if not enemy:
        return {
            "type": "player_attack",
            "summary": "There is no active enemy to attack.",
            "available_actions": ["Search the room", "Descend to the next floor"],
            "dice_rolls_this_turn": []
        }

    combat_state = start_combat_if_needed()
    actor = current_actor(combat_state)

    # If enemy wins initiative, resolve enemy first.
    if actor and actor["type"] == "enemy":
        enemy_event = resolve_enemy_turn()
        combat_state = advance_turn(combat_state)

        enemy_event["available_actions"] = get_available_combat_actions()
        enemy_event["initiative"] = combat_state.get("turn_order", [])
        enemy_event["round"] = combat_state.get("round", 1)
        enemy_event["note"] = "Enemy won initiative and acted first."

        return enemy_event

    attack = get_attack_by_name(character, weapon_name)
    attack_roll = roll_d20()

    total_attack = attack_roll["result"] + attack["attack_bonus"]
    enemy_ac = enemy["ac"]

    is_crit = attack_roll["result"] == 20
    hit = is_crit or total_attack >= enemy_ac

    dice_rolls = [
        {
            "die": "d20",
            "result": attack_roll["result"],
            "purpose": f"{character['identity']['character_name']} attack roll with {attack['name']}"
        }
    ]

    damage = 0
    damage_result = None
    enemy_result = {
        "enemy_remaining_hp": enemy["hp"],
        "enemy_defeated": False
    }

    if hit:
        damage_bonus = get_damage_bonus(character, attack)
        dice_expr = attack["damage_dice"]

        damage_result = roll_dice(dice_expr, multiplier=2 if is_crit else 1)
        damage = max(0, damage_result["result"] + damage_bonus)

        dice_rolls.append({
            "die": dice_expr,
            "result": damage,
            "purpose": f"{attack['name']} damage"
        })

        enemy_result = apply_damage_to_enemy(enemy["id"], damage)

    event = {
        "type": "player_attack",
        "actor": character["identity"]["character_name"],
        "target": enemy["name"],
        "weapon": attack["name"],
        "enemy_ac": enemy_ac,
        "attack_roll": attack_roll["result"],
        "attack_bonus": attack["attack_bonus"],
        "attack_total": total_attack,
        "hit": hit,
        "critical": is_crit,
        "damage": damage,
        "damage_type": attack["damage_type"],
        "enemy_hp_after": enemy_result["enemy_remaining_hp"],
        "enemy_defeated": enemy_result["enemy_defeated"],
        "xp_awarded":     enemy_result.get("xp_awarded"),
        "player_hp_after": character["combat"]["current_hp"],
        "dice_rolls_this_turn": dice_rolls,
        "initiative": combat_state.get("turn_order", []),
        "round": combat_state.get("round", 1)
    }

    if hit:
        crit_text = " Critical hit." if is_crit else ""
        event["summary"] = (
            f"{character['identity']['character_name']} attacks {enemy['name']} with {attack['name']}. "
            f"Attack total {total_attack} versus AC {enemy_ac}: hit.{crit_text} "
            f"Damage dealt: {damage} {attack['damage_type']}. "
            f"{enemy['name']} now has {enemy_result['enemy_remaining_hp']} HP."
        )
    else:
        event["summary"] = (
            f"{character['identity']['character_name']} attacks {enemy['name']} with {attack['name']}. "
            f"Attack total {total_attack} versus AC {enemy_ac}: miss."
        )

    # Enemy counter-turn after player action if enemy survived.
    if not enemy_result["enemy_defeated"]:
        combat_state = advance_turn(combat_state)
        next_actor = current_actor(combat_state)

        if next_actor and next_actor["type"] == "enemy":
            enemy_event = resolve_enemy_turn()
            event["enemy_response"] = enemy_event
            event["dice_rolls_this_turn"].extend(enemy_event.get("dice_rolls_this_turn", []))
            event["summary"] += " " + enemy_event["summary"]
            combat_state = advance_turn(combat_state)
    else:
        reset_combat_state()

    event["available_actions"] = get_available_combat_actions()
    return event
'''

def resolve_player_attack(weapon_name=None):
    """
    Phase 2 Step 3:
    Player attack is only allowed on the player's initiative turn.
    Enemy no longer auto-counterattacks inside this function.
    """
    sync_game_state_from_character()

    character = load_character()
    enemy = get_active_enemy()
    if character["combat"]["current_hp"] <= 0:
        return {
            "type": "downed",
            "success": False,
            "summary": (
                f"{character['identity']['character_name']} is at 0 HP and cannot attack. "
                f"A death saving throw is required."
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    if not enemy:
        return {
            "type": "player_attack",
            "summary": "There is no active enemy to attack.",
            "available_actions": ["Search Room", "Descend"],
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    combat_state = start_combat_if_needed()
    actor = current_actor(combat_state)

    if actor and actor.get("type") != "player":
        return {
            "type": "not_player_turn",
            "success": False,
            "summary": f"It is currently {actor.get('name')}'s turn, not the player's turn.",
            "available_actions": ["Wait"],
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    attack = get_attack_by_name(character, weapon_name)
    # PHASE 1 added — pass attack properties so ranged-while-adjacent disadvantage is applied
    roll_context = get_attack_roll_context("player", "enemy", attack_props=attack.get("properties", []))

    attack_roll = roll_d20(
        advantage=roll_context["advantage"],
        disadvantage=roll_context["disadvantage"]
    )

    if combat_state.get("player_help_advantage_next_attack"):
        combat_state["player_help_advantage_next_attack"] = False
        save_combat_state(combat_state)


    raw_result = attack_roll["result"]
    lucky_result, was_lucky = _lucky_reroll(raw_result, character)
    if was_lucky:
        attack_roll["result"] = lucky_result
        attack_roll["lucky_reroll"] = True

    total_attack = attack_roll["result"] + attack["attack_bonus"]
    enemy_ac = enemy["ac"]

    is_nat_1 = attack_roll["result"] == 1
    is_crit = attack_roll["result"] == 20
    if is_nat_1:
        hit = False
    else:
        hit = is_crit or total_attack >= enemy_ac

    dice_rolls = [
        {
            "die": "d20",
            "result": attack_roll["result"],
            "purpose": f"{character['identity']['character_name']} attack roll with {attack['name']}"
        }
    ]

    damage = 0
    sneak_attack_damage = 0
    hunters_mark_damage = 0
    enemy_result = {
        "enemy_remaining_hp": enemy["hp"],
        "enemy_defeated": False
    }

    if hit:
        damage_bonus = get_damage_bonus(character, attack)
        dice_expr = attack["damage_dice"]

        damage_result = roll_dice(dice_expr, multiplier=2 if is_crit else 1)
        damage = max(0, damage_result["result"] + damage_bonus)

        dice_rolls.append({
            "die": dice_expr,
            "result": damage,
            "purpose": f"{attack['name']} damage"
        })

        cls = character["identity"]["class"]

        # Sneak Attack. Rogue, finesse or ranged weapon, must have advantage or Help active
        if cls == "Rogue":
            props_str = " ".join(attack.get("properties", []))
            if "finesse" in props_str or "ranged" in props_str:
                has_adv = (
                    roll_context.get("advantage") or
                    combat_state.get("player_help_advantage_next_attack")
                )
                if has_adv:
                    sneak_lvl = character["identity"]["level"]
                    sneak_count = max(1, (sneak_lvl + 1) // 2)
                    sneak_roll = roll_dice(f"{sneak_count}d6")
                    sneak_attack_damage = sneak_roll["result"]
                    damage += sneak_attack_damage
                    dice_rolls.append({
                        "die": f"{sneak_count}d6",
                        "result": sneak_attack_damage,
                        "purpose": "Sneak Attack bonus damage"
                    })

        # Hunter's Mark. Ranger, active concentration spell, adds 1d6 per hit
        if cls == "Ranger" and combat_state.get("hunters_mark_active"):
            hm_roll = roll_dice("1d6")
            hunters_mark_damage = hm_roll["result"]
            damage += hunters_mark_damage
            dice_rolls.append({
                "die": "1d6",
                "result": hunters_mark_damage,
                "purpose": "Hunter's Mark bonus damage"
            })

        # Half-Orc Savage Attacks on a crit with a melee weapon, roll one extra damage die
        if is_crit and character["identity"]["race"] == "Half-Orc":
            props_str = " ".join(attack.get("properties", []))
            if "ranged" not in props_str and "cantrip" not in props_str:
                import re as _re
                m = _re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", attack["damage_dice"].strip())
                if m:
                    sides = int(m.group(2))
                    savage_extra = random.randint(1, sides)
                    damage += savage_extra
                    dice_rolls.append({
                        "die": f"1d{sides}",
                        "result": savage_extra,
                        "purpose": "Savage Attacks (Half-Orc critical)"
                    })

        enemy_result = apply_damage_to_enemy(  # PHASE 3 added damage_type for resistances
            enemy["id"], damage, damage_type=attack.get("damage_type"))

    event = {
        "type": "player_attack",
        "actor": character["identity"]["character_name"],
        "target": enemy["name"],
        "weapon": attack["name"],
        "enemy_ac": enemy_ac,
        "attack_roll": attack_roll["result"],
        "attack_bonus": attack["attack_bonus"],
        "attack_total": total_attack,
        "hit": hit,
        "critical": is_crit,
        "natural_1": is_nat_1,
        "damage": damage,
        "damage_type": attack["damage_type"],
        "enemy_hp_after": enemy_result["enemy_remaining_hp"],
        "enemy_defeated": enemy_result["enemy_defeated"],
        "xp_awarded":     enemy_result.get("xp_awarded"),
        "phase_transition": enemy_result.get("phase_transition", False),  # PHASE 3 added
        "phase_narrative":  enemy_result.get("phase_narrative"),          # PHASE 3 added
        "player_hp_after": character["combat"]["current_hp"],
        "sneak_attack_damage": sneak_attack_damage,
        "hunters_mark_damage": hunters_mark_damage,
        "dice_rolls_this_turn": dice_rolls,
        "advantage_context": roll_context,
        "initiative": combat_state.get("turn_order", []),
        "round": combat_state.get("round", 1)
    }

    if hit:
        crit_text = " Critical hit: damage dice are doubled." if is_crit else ""
        sneak_text = f" Sneak Attack: +{sneak_attack_damage} damage." if sneak_attack_damage else ""
        hm_text = f" Hunter's Mark: +{hunters_mark_damage} damage." if hunters_mark_damage else ""
        event["summary"] = (
            f"{character['identity']['character_name']} attacks {enemy['name']} with {attack['name']}. "
            f"{describe_advantage_context(roll_context)} "
            f"Attack total {total_attack} versus AC {enemy_ac}: hit.{crit_text}{sneak_text}{hm_text} "
            f"Total damage: {damage} {attack['damage_type']}. "
            f"{enemy['name']} now has {enemy_result['enemy_remaining_hp']} HP."
        )
    else:
        if is_nat_1:
            event["summary"] = (
                f"{character['identity']['character_name']} attacks {enemy['name']} with {attack['name']}. "
                f"{describe_advantage_context(roll_context)} "
                f"Natural 1: automatic miss."
            )
        else:
            event["summary"] = (
                f"{character['identity']['character_name']} attacks {enemy['name']} with {attack['name']}. "
                f"{describe_advantage_context(roll_context)} "
                f"Attack total {total_attack} versus AC {enemy_ac}: miss."
            )

    if enemy_result["enemy_defeated"]:
        reset_combat_state()
    else:
        combat_state = advance_turn(combat_state)

    event["available_actions"] = get_available_combat_actions()
    event["combat_state"] = get_combat_public_state()

    return event

def get_available_combat_actions():
    character = load_character()

    if character["combat"]["current_hp"] <= 0:
        if _get_condition(character, "Dead"):
            return []

        if _get_condition(character, "Stable"):
            return ["Wait"]

        return ["Death Save"]

    # Conditions that prevent the player from taking any action
    combat_state = load_combat_state()
    combat_conditions = get_combat_condition_names(combat_state)
    if "stunned" in combat_conditions or "paralyzed" in combat_conditions:
        return ["Wait"]

    enemy = get_active_enemy()

    if enemy:
        cls = character["identity"]["class"]
        usable_items = [
            i for i in character.get("equipment", [])
            if (i.get("type") or chars.ITEM_CATALOG.get(i.get("item_id", ""), {}).get("type", "")) == "consumable"
            and i.get("quantity", 0) > 0
        ]
        actions = ["Attack", "Dodge", "Dash", "Attempt to Parley"]
        if usable_items:
            actions.insert(3, "Use Item")

        if cls == "Fighter":
            features = {f["name"]: f for f in character.get("class_features", [])}
            sw = features.get("Second Wind")
            if sw and sw.get("uses_remaining", 0) > 0:
                actions.append("Second Wind")

        if cls == "Rogue":
            actions.append("Cunning Action")

        if cls == "Ranger":
            combat_state = load_combat_state()
            if not combat_state.get("hunters_mark_active"):
                spellcasting = character.get("spellcasting", {})
                slots = spellcasting.get("spell_slots", {})
                if isinstance(slots.get("1st"), dict) and slots["1st"].get("remaining", 0) > 0:
                    actions.append("Cast Hunter's Mark")

        return actions

    state = load_game_state()
    actions = []

    if not state.get("room_searched"):
        actions.append("Search Room")

    if state.get("floor", 1) < 4:
        actions.append("Descend")

    actions.append("Short Rest")
    if not state.get("long_rest_used_this_floor"):  # PHASE 1 added — once per floor limit
        actions.append("Long Rest")

    return actions or ["Continue"]


def roll_saving_throw(ability, dc, player_id="player", advantage=False, disadvantage=False):
    character = load_character()

    ability = ability.upper()
    if ability not in character["saving_throws"]:
        raise ValueError(f"Invalid saving throw ability: {ability}")

    mod = character["saving_throws"][ability]["modifier"]

    exh = _get_exhaustion_level(character)
    if exh >= 3:
        disadvantage = True
    if exh >= 6:
        character = _add_condition(character, "Dead", source="exhaustion",
                                   effects=["Reached exhaustion level 6."])
        character["combat"]["current_hp"] = 0
        save_character(character)
        sync_game_state_from_character()

    roll = roll_d20(advantage=advantage, disadvantage=disadvantage)

    # Halfling Lucky: reroll natural 1s on saving throws
    lucky_result, was_lucky = _lucky_reroll(roll["result"], character)
    if was_lucky:
        roll["result"] = lucky_result
        roll["lucky_reroll"] = True

    total = roll["result"] + mod

    return {
        "player_id": player_id,
        "ability": ability,
        "dc": dc,
        "roll": roll["result"],
        "modifier": mod,
        "total": total,
        "success": total >= dc,
        "dice_rolls_this_turn": [
            {
                "die": "d20",
                "result": roll["result"],
                "purpose": f"{ability} saving throw"
            }
        ]
    }


def roll_skill_check(skill_name, dc, player_id="player", advantage=False, disadvantage=False):
    character = load_character()

    if skill_name not in character["skills"]:
        raise ValueError(f"Invalid skill: {skill_name}")

    skill = character["skills"][skill_name]
    mod = skill["modifier"]
    roll = roll_d20(advantage=advantage, disadvantage=disadvantage)

    # Halfling Lucky: reroll natural 1s on ability checks
    lucky_result, was_lucky = _lucky_reroll(roll["result"], character)
    if was_lucky:
        roll["result"] = lucky_result
        roll["lucky_reroll"] = True

    total = roll["result"] + mod

    return {
        "player_id": player_id,
        "skill": skill_name,
        "ability": skill["ability"],
        "dc": dc,
        "roll": roll["result"],
        "modifier": mod,
        "total": total,
        "success": total >= dc,
        "dice_rolls_this_turn": [
            {
                "die": "d20",
                "result": roll["result"],
                "purpose": f"{skill_name} skill check"
            }
        ]
    }

def _defeat_active_enemy(reason):
    state = load_game_state()
    enemy = state.get("enemy")
    xp_result = None

    if enemy and enemy.get("hp", 0) > 0:
        enemy["hp"] = 0
        state["enemy"] = enemy

        rules     = get_enemy_rules(enemy["name"])
        xp_amount = enemy.get("xp_reward", rules.get("xp", 0))  # PHASE 3 fixed
        xp_result = chars.award_xp(xp_amount, f"enemy_defeated:{enemy['name']}")
        sync_game_state_from_character()

    state["last_combat_resolution"] = reason
    save_game_state(state)
    reset_combat_state()

    return {
        "enemy_name": enemy["name"] if enemy else None,
        "enemy_defeated": True,
        "enemy_hp_after": 0,
        "xp_awarded": xp_result
    }


def resolve_sneak_attempt(player_id="player"):
    #Uses character Stealth modifier from character.json.
    #Success: enemy is bypassed/neutralized.
    #Failure: enemy gets an immediate server-rolled attack.
    sync_game_state_from_character()

    character = load_character()
    enemy = get_active_enemy()
    if character["combat"]["current_hp"] <= 0:
        return {
            "type": "downed",
            "success": False,
            "summary": (
                f"{character['identity']['character_name']} is at 0 HP and cannot sneak. "
                f"A death saving throw is required."
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    if not enemy:
        return {
            "type": "sneak",
            "summary": "There is no active enemy to sneak past.",
            "success": False,
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": []
        }

    dc = 12
    skill_context = get_skill_check_context("Stealth")

    check = roll_skill_check(
        "Stealth",
        dc,
        player_id=player_id,
        advantage=skill_context["advantage"],
        disadvantage=skill_context["disadvantage"]
    )

    dice_rolls = check.get("dice_rolls_this_turn", [])

    event = {
        "type": "sneak",
        "actor": character["identity"]["character_name"],
        "target": enemy["name"],
        "skill": "Stealth",
        "dc": dc,
        "roll": check["roll"],
        "modifier": check["modifier"],
        "total": check["total"],
        "success": check["success"],
        "dice_rolls_this_turn": dice_rolls,
        "conditions_applied": [],
        "xp_gained": 0,
        "advantage_context": skill_context
    }

    if check["success"]:
        defeated = _defeat_active_enemy("sneak_success")
        event.update(defeated)
        event["summary"] = (
            f"{character['identity']['character_name']} attempts to slip past {enemy['name']} unseen. "
            f"Stealth check total {check['total']} versus DC {dc}: success. "
            f"{enemy['name']} is bypassed and no longer blocks the room."
        )
    else:
        enemy_response = resolve_enemy_turn()

        event["enemy_response"] = enemy_response
        event["dice_rolls_this_turn"].extend(enemy_response.get("dice_rolls_this_turn", []))
        event["summary"] = (
            f"{character['identity']['character_name']} attempts to slip past {enemy['name']} unseen. "
            f"Stealth check total {check['total']} versus DC {dc}: failure. "
            f"{enemy_response.get('summary', '')}"
        )

    event["available_actions"] = get_available_combat_actions()
    return event


def resolve_parley_attempt(player_id="player"):
    #Phase 2 server-authoritative Parley.
    #Uses character Persuasion modifier from character.json.
    #Costs 5 gold from game_state.json.
    #Success: enemy stands down.
    #Failure: gold is spent and enemy gets an immediate server-rolled attack.
    
    sync_game_state_from_character()

    character = load_character()
    state = load_game_state()
    enemy = get_active_enemy()
    if character["combat"]["current_hp"] <= 0:
        return {
            "type": "downed",
            "success": False,
            "summary": (
                f"{character['identity']['character_name']} is at 0 HP and cannot parley. "
                f"A death saving throw is required."
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    if not enemy:
        return {
            "type": "parley",
            "summary": "There is no active enemy to parley with.",
            "success": False,
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": []
        }

    cost = 5

    if state.get("gold", 0) < cost:
        return {
            "type": "parley",
            "actor": character["identity"]["character_name"],
            "target": enemy["name"],
            "success": False,
            "error": f"Need {cost} gold to parley, but only have {state.get('gold', 0)}.",
            "summary": (
                f"{character['identity']['character_name']} attempts to bargain with {enemy['name']}, "
                f"but lacks the {cost} gold needed to make the offer."
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": []
        }

    state["gold"] = state.get("gold", 0) - cost
    save_game_state(state)

    dc = 14
    skill_context = get_skill_check_context("Persuasion")

    check = roll_skill_check(
        "Persuasion",
        dc,
        player_id=player_id,
        advantage=skill_context["advantage"],
        disadvantage=skill_context["disadvantage"]
    )

    dice_rolls = check.get("dice_rolls_this_turn", [])

    event = {
        "type": "parley",
        "actor": character["identity"]["character_name"],
        "target": enemy["name"],
        "skill": "Persuasion",
        "dc": dc,
        "roll": check["roll"],
        "modifier": check["modifier"],
        "total": check["total"],
        "success": check["success"],
        "gold_spent": cost,
        "gold_remaining": load_game_state().get("gold", 0),
        "dice_rolls_this_turn": dice_rolls,
        "conditions_applied": [],
        "xp_gained": 0,
        "advantage_context": skill_context
    }

    if check["success"]:
        defeated = _defeat_active_enemy("parley_success")
        event.update(defeated)
        event["summary"] = (
            f"{character['identity']['character_name']} attempts to parley with {enemy['name']}. "
            f"Persuasion check total {check['total']} versus DC {dc}: success. "
            f"{enemy['name']} stands down. {cost} gold is spent."
        )
    else:
        enemy_response = resolve_enemy_turn()

        event["enemy_response"] = enemy_response
        event["dice_rolls_this_turn"].extend(enemy_response.get("dice_rolls_this_turn", []))
        event["summary"] = (
            f"{character['identity']['character_name']} attempts to parley with {enemy['name']}. "
            f"Persuasion check total {check['total']} versus DC {dc}: failure. "
            f"{cost} gold is spent. {enemy_response.get('summary', '')}"
        )

    event["available_actions"] = get_available_combat_actions()
    return event

def get_combat_public_state():
    combat_state = load_combat_state()

    if not combat_state.get("active"):
        return {
            "active": False,
            "round": 0,
            "current_actor": None,
            "active_player_name": None,
            "turn_order": [],
            "initiative_order": [],  # PHASE 5 added
            "conditions": [],        # PHASE 5 added
        }

    actor = current_actor(combat_state)
    active_player = actor.get("player_name") if actor and actor.get("type") == "player" else None

    # enrich turn_order with live HP for initiative pills
    try:
        character  = load_character()
        player_hp  = character["combat"]["current_hp"]
        player_mhp = character["combat"]["max_hp"]
    except Exception:
        player_hp, player_mhp = 0, 0

    try:
        gs         = load_game_state()
        enemy_obj  = gs.get("enemy") or {}
        enemy_hp   = enemy_obj.get("hp", 0)
        enemy_mhp  = enemy_obj.get("max_hp", 1)
    except Exception:
        enemy_hp, enemy_mhp = 0, 1

    initiative_order = []
    for entry in combat_state.get("turn_order", []):
        is_player = entry.get("type") == "player"
        is_active = bool(actor and actor.get("id") == entry.get("id"))
        initiative_order.append({
            "id":               entry.get("id"),
            "name":             entry.get("name"),
            "type":             entry.get("type"),
            "initiative_total": entry.get("initiative_total"),
            "hp":               player_hp  if is_player else enemy_hp,
            "max_hp":           player_mhp if is_player else enemy_mhp,
            "is_active":        is_active,
            "is_player":        is_player,
        })

    return {
        "active": True,
        "round": combat_state.get("round", 1),
        "current_actor": actor,
        "active_player_name": active_player,
        "turn_order": combat_state.get("turn_order", []),
        "initiative_order": initiative_order,           # PHASE 5 added
        "conditions": combat_state.get("conditions", []),  # PHASE 5 added
    }


def is_player_turn():
    combat_state = load_combat_state()

    if not combat_state.get("active"):
        return True

    actor = current_actor(combat_state)

    return bool(actor and actor.get("type") == "player")


def resolve_enemy_turn_if_current():
    """
    If current actor is enemy, resolve exactly one enemy turn and advance turn.
    """
    combat_state = load_combat_state()

    if not combat_state.get("active"):
        return {
            "resolved": False,
            "event": None,
            "combat_state": get_combat_public_state()
        }

    actor = current_actor(combat_state)

    if not actor or actor.get("type") != "enemy":
        return {
            "resolved": False,
            "event": None,
            "combat_state": get_combat_public_state()
        }

    event = resolve_enemy_turn()
    combat_state = advance_turn(combat_state)

    event["available_actions"] = get_available_combat_actions()
    event["initiative"] = combat_state.get("turn_order", [])
    event["round"] = combat_state.get("round", 1)

    return {
        "resolved": True,
        "event": event,
        "combat_state": get_combat_public_state()
    }

def _require_player_turn_event(action_name):
    character = load_character()

    if character["combat"]["current_hp"] <= 0:
        return {
            "allowed": False,
            "event": {
                "type": "downed",
                "success": False,
                "summary": (
                    f"{character['identity']['character_name']} is at 0 HP and cannot take normal actions. "
                    f"A death saving throw is required."
                ),
                "available_actions": get_available_combat_actions(),
                "dice_rolls_this_turn": [],
                "combat_state": get_combat_public_state()
            }
        }
    enemy = get_active_enemy()

    if not enemy:
        return {
            "allowed": False,
            "event": {
                "type": action_name,
                "success": False,
                "summary": "There is no active enemy.",
                "available_actions": get_available_combat_actions(),
                "dice_rolls_this_turn": [],
                "combat_state": get_combat_public_state()
            }
        }

    combat_state = start_combat_if_needed()
    actor = current_actor(combat_state)

    if actor and actor.get("type") != "player":
        return {
            "allowed": False,
            "event": {
                "type": "not_player_turn",
                "success": False,
                "summary": f"It is currently {actor.get('name')}'s turn, not the player's turn.",
                "available_actions": ["Wait"],
                "dice_rolls_this_turn": [],
                "combat_state": get_combat_public_state()
            }
        }

    return {
        "allowed": True,
        "event": None
    }


def resolve_player_dodge():
    #Player takes the Dodge action.
    #Until the start of the player's next turn, enemy attack rolls have disadvantage.
    
    sync_game_state_from_character()

    character = load_character()
    check = _require_player_turn_event("dodge")

    if not check["allowed"]:
        return check["event"]

    combat_state = load_combat_state()
    combat_state["player_dodging"] = True
    save_combat_state(combat_state)

    combat_state = advance_turn(combat_state)

    event = {
        "type": "dodge",
        "actor": character["identity"]["character_name"],
        "success": True,
        "summary": (
            f"{character['identity']['character_name']} takes the Dodge action, "
            f"raising their guard and forcing the next enemy attack to roll with disadvantage."
        ),
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "conditions_applied": ["Dodging"],
        "combat_state": get_combat_public_state()
    }

    return event


def resolve_player_dash():
    sync_game_state_from_character()

    character = load_character()
    check = _require_player_turn_event("dash")

    if not check["allowed"]:
        return check["event"]

    combat_state = load_combat_state()
    combat_state = advance_turn(combat_state)

    event = {
        "type": "dash",
        "actor": character["identity"]["character_name"],
        "success": True,
        "summary": (
            f"{character['identity']['character_name']} takes the Dash action, "
            f"moving quickly through the battlefield and repositioning for the next exchange."
        ),
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "conditions_applied": [],
        "combat_state": get_combat_public_state()
    }

    return event


def resolve_player_help():
    #Player takes the Help action.
    #In solo mode, this grants advantage on the player's next attack.
    #In multiplayer later, this will help another party member.
    sync_game_state_from_character()

    character = load_character()
    check = _require_player_turn_event("help")

    if not check["allowed"]:
        return check["event"]

    combat_state = load_combat_state()
    combat_state["player_help_advantage_next_attack"] = True
    save_combat_state(combat_state)

    combat_state = advance_turn(combat_state)

    event = {
        "type": "help",
        "actor": character["identity"]["character_name"],
        "success": True,
        "summary": (
            f"{character['identity']['character_name']} takes the Help action, "
            f"creating an opening. Their next attack will have advantage."
        ),
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "conditions_applied": ["Help: advantage on next attack"],
        "combat_state": get_combat_public_state()
    }

    return event

def resolve_player_disengage():
    sync_game_state_from_character()

    character = load_character()
    check = _require_player_turn_event("disengage")

    if not check["allowed"]:
        return check["event"]

    combat_state = load_combat_state()
    # flag lets the enemy-turn resolver skip opportunity-attack damage
    combat_state["player_disengaging"] = True
    save_combat_state(combat_state)

    combat_state = advance_turn(combat_state)

    name = character["identity"]["character_name"]
    return {
        "type": "disengage",
        "actor": name,
        "success": True,
        "summary": (
            f"{name} takes the Disengage action, carefully stepping back "
            f"without giving the enemy an opening to strike."
        ),
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "conditions_applied": ["Disengaging"],
        "combat_state": get_combat_public_state(),
    }


def resolve_player_bonus_action():
    sync_game_state_from_character()

    character = load_character()
    check = _require_player_turn_event("bonus_action")

    if not check["allowed"]:
        return check["event"]

    char_class = character.get("identity", {}).get("class", "").lower()
    combat_state = load_combat_state()

    # Fighters use Second Wind to regain a small amount of HP
    if char_class == "fighter":
        import random
        level  = character.get("identity", {}).get("level", 1)
        healed = random.randint(1, 10) + level
        old_hp = character.get("combat", {}).get("current_hp", 0)
        max_hp = character.get("combat", {}).get("max_hp", old_hp)
        new_hp = min(max_hp, old_hp + healed)
        character["combat"]["current_hp"] = new_hp
        import character_manager as _chars
        _chars.save_character(character)
        state = load_game_state()
        state["hp"] = new_hp
        save_game_state(state)
        summary = (
            f"{character['identity']['character_name']} uses Second Wind, "
            f"rallying their reserves and recovering {new_hp - old_hp} HP."
        )
        conditions = ["Second Wind used"]
    else:
        # Generic: grant advantage on the next attack
        combat_state["player_help_advantage_next_attack"] = True
        summary = (
            f"{character['identity']['character_name']} uses a bonus action, "
            f"seizing a momentary opening to press their advantage."
        )
        conditions = ["Bonus action: advantage on next attack"]

    save_combat_state(combat_state)
    advance_turn(combat_state)

    return {
        "type": "bonus_action",
        "actor": character["identity"]["character_name"],
        "success": True,
        "summary": summary,
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "conditions_applied": conditions,
        "combat_state": get_combat_public_state(),
    }


def resolve_player_combat_action(action_name):
    action_name = action_name.lower().strip()

    if action_name == "dodge":
        return resolve_player_dodge()

    if action_name == "dash":
        return resolve_player_dash()

    if action_name == "help":
        return resolve_player_help()

    if action_name == "disengage":
        return resolve_player_disengage()

    if action_name == "bonus_action":
        return resolve_player_bonus_action()

    raise ValueError(f"Unsupported combat action: {action_name}")

def get_condition_names(character):
    return [
        c.get("name", "").lower()
        for c in character.get("combat", {}).get("conditions", [])
    ]


# Combat-state-level conditions (temporary, cleared on combat reset)

def _get_combat_condition(combat_state, name):
    name_lower = name.lower()
    for c in combat_state.get("conditions", []):
        if c.get("name", "").lower() == name_lower:
            return c
    return None


def _add_combat_condition(combat_state, name, source="enemy", duration_turns=None, effects=None):
    if _get_combat_condition(combat_state, name):
        return combat_state
    combat_state.setdefault("conditions", []).append({
        "name": name,
        "source": source,
        "duration_turns": duration_turns,
        "effects": effects or []
    })
    return combat_state


def _remove_combat_condition(combat_state, name):
    name_lower = name.lower()
    combat_state["conditions"] = [
        c for c in combat_state.get("conditions", [])
        if c.get("name", "").lower() != name_lower
    ]
    return combat_state


def get_combat_condition_names(combat_state):
    return [c.get("name", "").lower() for c in combat_state.get("conditions", [])]


def get_attack_roll_context(attacker_type, target_type, attack_props=None):  # PHASE 1 added attack_props param
    """
    Central advantage/disadvantage resolver.

    attacker_type: "player" or "enemy"
    target_type: "player" or "enemy"
    attack_props: list of attack property strings (optional); used to detect ranged attacks

    Returns:
    {
      "advantage": bool,
      "disadvantage": bool,
      "reasons": []
    }
    """
    character = load_character()
    combat_state = load_combat_state()
    conditions = get_combat_condition_names(combat_state)

    advantage = False
    disadvantage = False
    reasons = []

    # Player conditions affecting player attacks
    if attacker_type == "player":
        if "poisoned" in conditions:
            disadvantage = True
            reasons.append("Poisoned: disadvantage on attack rolls")

        if "blinded" in conditions:
            disadvantage = True
            reasons.append("Blinded: disadvantage on attack rolls")

        if "frightened" in conditions:
            disadvantage = True
            reasons.append("Frightened: disadvantage on attack rolls")

        # PHASE 1 added — Prone: disadvantage on melee attack rolls
        if "prone" in conditions:
            disadvantage = True
            reasons.append("Prone: disadvantage on melee attack rolls")

        # PHASE 1 added — Ranged attack while enemy is adjacent (all dungeon combat is close-quarters)
        if attack_props is not None:
            props_str = " ".join(str(p) for p in attack_props)
            if "ranged" in props_str:
                disadvantage = True
                reasons.append("Ranged attack while enemy is adjacent: disadvantage")

        if combat_state.get("player_help_advantage_next_attack"):
            advantage = True
            reasons.append("Help: advantage on next attack")

        if combat_state.get("guiding_bolt_active"):
            advantage = True
            combat_state["guiding_bolt_active"] = False
            save_combat_state(combat_state)
            reasons.append("Guiding Bolt: advantage on this attack")

        # Faerie Fire outlines the enemy — all attacks against it have advantage.
        if combat_state.get("faerie_fire_active"):
            advantage = True
            reasons.append("Faerie Fire: target outlined, advantage on attacks")

        if "slowed" in conditions:  # PHASE 3 added — Stone Golem slow ability
            disadvantage = True
            reasons.append("Slowed: disadvantage on attack rolls")

        exh = _get_exhaustion_level(character)
        if exh >= 3:
            disadvantage = True
            reasons.append(f"Exhaustion level {exh}: disadvantage on attack rolls")

    # Enemy attacks against player
    if attacker_type == "enemy" and target_type == "player":
        if combat_state.get("player_dodging"):
            disadvantage = True
            reasons.append("Dodge: enemy attacks with disadvantage")

        if combat_state.get("sanctuary_active"):
            # Enemy must succeed on WIS DC 14 save or the attack fails.
            sanctuary_save = random.randint(1, 20)
            if sanctuary_save < 14:
                combat_state["sanctuary_active"] = False
                save_combat_state(combat_state)
                disadvantage = True
                reasons.append(f"Sanctuary: enemy failed WIS save ({sanctuary_save} < 14), attacks with disadvantage")
            else:
                combat_state["sanctuary_active"] = False
                save_combat_state(combat_state)
                reasons.append(f"Sanctuary: enemy overcame the ward ({sanctuary_save} ≥ 14)")

        if combat_state.get("protection_active"):
            disadvantage = True
            reasons.append("Protection from Evil and Good: enemy attacks with disadvantage")

        if "blinded" in conditions:
            advantage = True
            reasons.append("Target blinded: attacks against target have advantage")

        if "stunned" in conditions:
            advantage = True
            reasons.append("Target stunned: attacks against target have advantage")

        if "paralyzed" in conditions:
            advantage = True
            reasons.append("Target paralyzed: attacks against target have advantage")

        if "prone" in conditions:
            advantage = True
            reasons.append("Target prone: melee attacks against target have advantage")

        if combat_state.get("invisible"):  # PHASE 3 added — player is invisible
            disadvantage = True
            reasons.append("Target invisible: enemy attacks with disadvantage")

    # 5e rule: advantage and disadvantage cancel out.
    if advantage and disadvantage:
        advantage = False
        disadvantage = False
        reasons.append("Advantage and disadvantage cancel out")

    return {
        "advantage": advantage,
        "disadvantage": disadvantage,
        "reasons": reasons
    }


def get_skill_check_context(skill_name):
    """
    Central advantage/disadvantage resolver for skill checks.
    """
    character = load_character()
    combat_state = load_combat_state()
    conditions = get_combat_condition_names(combat_state)

    advantage = False
    disadvantage = False
    reasons = []

    if "poisoned" in conditions:
        disadvantage = True
        reasons.append("Poisoned: disadvantage on ability checks")

    if character["combat"].get("exhaustion_level", 0) >= 1:
        disadvantage = True
        reasons.append("Exhaustion level 1+: disadvantage on ability checks")

    if skill_name == "Stealth" and "prone" in conditions:
        disadvantage = True
        reasons.append("Prone: difficult to move silently")

    # Guidance: +1d4 to the next ability check (treat as advantage for simplification).
    if combat_state.get("guidance_active"):
        advantage = True
        combat_state["guidance_active"] = False
        save_combat_state(combat_state)
        reasons.append("Guidance: +1d4 to this ability check")

    if advantage and disadvantage:
        advantage = False
        disadvantage = False
        reasons.append("Advantage and disadvantage cancel out")

    return {
        "advantage": advantage,
        "disadvantage": disadvantage,
        "reasons": reasons
    }
def describe_advantage_context(context):
    if not context:
        return ""

    reasons = context.get("reasons", [])

    if context.get("advantage"):
        return " The roll is made with advantage" + (f" ({'; '.join(reasons)})." if reasons else ".")

    if context.get("disadvantage"):
        return " The roll is made with disadvantage" + (f" ({'; '.join(reasons)})." if reasons else ".")

    if reasons:
        return " " + "; ".join(reasons) + "."

    return ""
def _get_condition(character, condition_name):
    condition_name = condition_name.lower()

    for condition in character.get("combat", {}).get("conditions", []):
        if condition.get("name", "").lower() == condition_name:
            return condition

    return None


def _remove_condition(character, condition_name):
    condition_name = condition_name.lower()

    character["combat"]["conditions"] = [
        c for c in character.get("combat", {}).get("conditions", [])
        if c.get("name", "").lower() != condition_name
    ]

    return character


def _add_condition(character, name, source="death_save", duration_turns=None, effects=None):
    effects = effects or []

    if _get_condition(character, name):
        return character

    character["combat"]["conditions"].append({
        "name": name,
        "source": source,
        "duration_turns": duration_turns,
        "effects": effects
    })

    return character


def is_player_downed():
    character = load_character()
    return character["combat"]["current_hp"] <= 0


def is_player_dead():
    character = load_character()
    return _get_condition(character, "Dead") is not None


def is_player_stable():
    character = load_character()
    return _get_condition(character, "Stable") is not None


def resolve_death_save(player_id="player"):
    """
    Server-authoritative death save.

    Rules:
    10+ = success
    1-9 = failure
    natural 20 = regain 1 HP
    natural 1 = two failures
    3 successes = stable
    3 failures = dead
    """
    character = load_character()
    combat = character["combat"]

    if combat["current_hp"] > 0:
        return {
            "type": "death_save",
            "success": False,
            "summary": f"{character['identity']['character_name']} is conscious and does not need a death save.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    if _get_condition(character, "Dead"):
        return {
            "type": "death_save",
            "success": False,
            "dead": True,
            "summary": f"{character['identity']['character_name']} is dead. No further death saves can be made.",
            "available_actions": [],
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    if _get_condition(character, "Stable"):
        return {
            "type": "death_save",
            "success": True,
            "stable": True,
            "summary": f"{character['identity']['character_name']} is stable at 0 HP.",
            "available_actions": ["Wait"],
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    roll = roll_d20()
    # Halfling Lucky reroll natural 1s on death saves
    lucky_result, was_lucky = _lucky_reroll(roll["result"], character)
    if was_lucky:
        roll["result"] = lucky_result
    value = roll["result"]

    death_saves = combat.get("death_saves", {"successes": 0, "failures": 0})
    successes = death_saves.get("successes", 0)
    failures = death_saves.get("failures", 0)

    outcome = ""

    if value == 20:
        combat["current_hp"] = 1
        combat["death_saves"] = {"successes": 0, "failures": 0}
        character["combat"] = combat
        character = _remove_condition(character, "Stable")
        save_character(character)
        sync_game_state_from_character()

        combat_state = load_combat_state()
        if combat_state.get("active"):
            advance_turn(combat_state)

        return {
            "type": "death_save",
            "success": True,
            "revived": True,
            "roll": value,
            "summary": (
                f"{character['identity']['character_name']} rolls a natural 20 on a death save "
                f"and regains 1 HP."
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [
                {"die": "d20", "result": value, "purpose": "Death saving throw"}
            ],
            "combat_state": get_combat_public_state()
        }

    if value == 1:
        failures += 2
        outcome = "natural 1: two failures"
    elif value >= 10:
        successes += 1
        outcome = "success"
    else:
        failures += 1
        outcome = "failure"

    combat["death_saves"] = {
        "successes": successes,
        "failures": failures
    }

    stable = False
    dead = False

    if successes >= 3:
        stable = True
        character = _add_condition(
            character,
            "Stable",
            source="death_save",
            effects=["Stable at 0 HP. No further death saves unless damaged."]
        )

    if failures >= 3:
        dead = True
        character = _add_condition(
            character,
            "Dead",
            source="death_save",
            effects=["Character has died after three failed death saves."]
        )

    character["combat"] = combat
    save_character(character)
    sync_game_state_from_character()

    combat_state = load_combat_state()
    if combat_state.get("active") and not dead and not stable:
        advance_turn(combat_state)

    if dead:
        summary = (
            f"{character['identity']['character_name']} rolls {value} on a death save: {outcome}. "
            f"Death saves are now {successes} successes and {failures} failures. "
            f"Three failures have been reached. {character['identity']['character_name']} dies."
        )
    elif stable:
        summary = (
            f"{character['identity']['character_name']} rolls {value} on a death save: {outcome}. "
            f"Death saves are now {successes} successes and {failures} failures. "
            f"Three successes have been reached. {character['identity']['character_name']} is stable."
        )
    else:
        summary = (
            f"{character['identity']['character_name']} rolls {value} on a death save: {outcome}. "
            f"Death saves are now {successes} successes and {failures} failures."
        )

    return {
        "type": "death_save",
        "success": value >= 10,
        "roll": value,
        "death_save_successes": successes,
        "death_save_failures": failures,
        "stable": stable,
        "dead": dead,
        "summary": summary,
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [
            {"die": "d20", "result": value, "purpose": "Death saving throw"}
        ],
        "combat_state": get_combat_public_state()
    }


def resolve_second_wind():
    sync_game_state_from_character()

    character = load_character()
    check = _require_player_turn_event("second_wind")

    if not check["allowed"]:
        return check["event"]

    features = {f["name"]: f for f in character.get("class_features", [])}
    sw = features.get("Second Wind")

    if not sw:
        return {
            "type": "second_wind",
            "success": False,
            "summary": "Second Wind is not available for this character.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    if sw.get("uses_remaining", 0) <= 0:
        return {
            "type": "second_wind",
            "success": False,
            "summary": "Second Wind has already been used. Recover it on a Short Rest.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    level = character["identity"]["level"]
    heal_roll = roll_dice(f"1d10+{level}")
    heal_amount = heal_roll["result"]

    combat = character["combat"]
    old_hp = combat["current_hp"]
    combat["current_hp"] = min(_effective_max_hp(character), old_hp + heal_amount)
    character["combat"] = combat

    for f in character["class_features"]:
        if f["name"] == "Second Wind":
            f["uses_remaining"] = f.get("uses_remaining", 1) - 1
            break

    save_character(character)
    sync_game_state_from_character()

    combat_state = load_combat_state()
    combat_state = advance_turn(combat_state)

    return {
        "type": "second_wind",
        "success": True,
        "heal_amount": heal_amount,
        "hp_before": old_hp,
        "hp_after": combat["current_hp"],
        "uses_remaining": sw.get("uses_remaining", 1) - 1,
        "summary": (
            f"{character['identity']['character_name']} uses Second Wind as a bonus action, "
            f"rolling 1d10+{level} and recovering {heal_amount} HP. "
            f"HP: {old_hp} -> {combat['current_hp']}."
        ),
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [
            {"die": f"1d10+{level}", "result": heal_amount, "purpose": "Second Wind healing"}
        ],
        "combat_state": get_combat_public_state()
    }


def resolve_hunters_mark_cast():
    sync_game_state_from_character()

    character = load_character()
    check = _require_player_turn_event("hunters_mark")

    if not check["allowed"]:
        return check["event"]

    spellcasting = character.get("spellcasting", {})
    slots = spellcasting.get("spell_slots", {})

    if not (isinstance(slots.get("1st"), dict) and slots["1st"].get("remaining", 0) > 0):
        return {
            "type": "hunters_mark",
            "success": False,
            "summary": "No 1st-level spell slots remaining to cast Hunter's Mark.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    combat_state = load_combat_state()

    if combat_state.get("hunters_mark_active"):
        return {
            "type": "hunters_mark",
            "success": False,
            "summary": "Hunter's Mark is already active.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    spellcasting["spell_slots"]["1st"]["remaining"] -= 1
    character["spellcasting"] = spellcasting
    save_character(character)

    combat_state["hunters_mark_active"] = True
    combat_state["concentration"] = {"spell": "Hunter's Mark", "source": "Ranger"}
    save_combat_state(combat_state)

    combat_state = advance_turn(load_combat_state())

    enemy = get_active_enemy()
    target_name = enemy["name"] if enemy else "the enemy"

    return {
        "type": "hunters_mark",
        "success": True,
        "target": target_name,
        "slots_remaining": spellcasting["spell_slots"]["1st"]["remaining"],
        "summary": (
            f"{character['identity']['character_name']} casts Hunter's Mark on {target_name}. "
            f"While concentration holds, each hit deals an extra 1d6 damage. "
            f"One 1st-level spell slot used."
        ),
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "combat_state": get_combat_public_state()
    }


def resolve_cunning_action(sub_action="dash"):
    sync_game_state_from_character()

    character = load_character()

    if character["identity"]["class"] != "Rogue":
        return {
            "type": "cunning_action",
            "success": False,
            "summary": "Cunning Action is only available to Rogues.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    check = _require_player_turn_event("cunning_action")

    if not check["allowed"]:
        return check["event"]

    sub = sub_action.lower().strip()
    combat_state = load_combat_state()

    if sub == "hide":
        hide_roll = roll_d20()
        stealth_mod = character["skills"].get("Stealth", {}).get("modifier", 0)
        hide_total = hide_roll["result"] + stealth_mod
        dc = 13
        success = hide_total >= dc

        if success:
            combat_state["player_help_advantage_next_attack"] = True
            save_combat_state(combat_state)

        combat_state = advance_turn(load_combat_state())

        return {
            "type": "cunning_action",
            "sub_action": "hide",
            "success": success,
            "roll": hide_roll["result"],
            "modifier": stealth_mod,
            "total": hide_total,
            "dc": dc,
            "summary": (
                f"{character['identity']['character_name']} uses Cunning Action: Hide. "
                f"Stealth check {hide_total} vs DC {dc}: {'success — next attack has advantage.' if success else 'failure.'}"
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [
                {"die": "d20", "result": hide_roll["result"], "purpose": "Cunning Action: Hide stealth check"}
            ],
            "combat_state": get_combat_public_state()
        }

    if sub == "disengage":
        combat_state["player_dodging"] = True
        save_combat_state(combat_state)
        combat_state = advance_turn(load_combat_state())

        return {
            "type": "cunning_action",
            "sub_action": "disengage",
            "success": True,
            "summary": (
                f"{character['identity']['character_name']} uses Cunning Action: Disengage, "
                f"slipping away safely. Enemy attacks have disadvantage this turn."
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    combat_state = advance_turn(combat_state)

    return {
        "type": "cunning_action",
        "sub_action": "dash",
        "success": True,
        "summary": (
            f"{character['identity']['character_name']} uses Cunning Action: Dash, "
            f"moving swiftly and repositioning with their bonus action."
        ),
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "combat_state": get_combat_public_state()
    }


def resolve_use_item_combat(item_id):
    sync_game_state_from_character()

    character = load_character()

    if character["combat"]["current_hp"] <= 0:
        return {
            "type": "use_item",
            "success": False,
            "summary": "Cannot use items while downed.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    inventory = character.get("equipment", [])
    item = None

    for i, entry in enumerate(inventory):
        if (entry.get("item_id") == item_id
                or entry.get("id") == item_id
                or entry.get("name", "").lower() == item_id.lower()):
            # Fall back to ITEM_CATALOG when the type field is absent (legacy character.json)
            entry_type = entry.get("type") or chars.ITEM_CATALOG.get(entry.get("item_id", ""), {}).get("type", "")
            if entry_type == "consumable":
                item = entry
                item_index = i
                break

    if not item:
        return {
            "type": "use_item",
            "success": False,
            "summary": f"Item '{item_id}' not found in inventory.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    if item.get("quantity", 1) <= 0:
        return {
            "type": "use_item",
            "success": False,
            "summary": f"You have no {item.get('name', item_id)} remaining.",
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": [],
            "combat_state": get_combat_public_state()
        }

    item_name = item.get("name", item_id)
    combat = character["combat"]
    dice_rolls = []
    heal_amount = 0

    if "health potion" in item_name.lower() or "potion of healing" in item_name.lower():
        heal_roll = roll_dice("2d4+2")
        heal_amount = heal_roll["result"]
        old_hp = combat["current_hp"]
        combat["current_hp"] = min(_effective_max_hp(character), old_hp + heal_amount)
        character["combat"] = combat

        qty = item.get("quantity", 1) - 1
        if qty <= 0:
            inventory.pop(item_index)
        else:
            inventory[item_index]["quantity"] = qty

        character["equipment"] = inventory
        save_character(character)
        sync_game_state_from_character()

        dice_rolls.append({"die": "2d4+2", "result": heal_amount, "purpose": "Potion of Healing"})

        combat_state = load_combat_state()
        combat_state = advance_turn(combat_state)

        return {
            "type": "use_item",
            "item": item_name,
            "success": True,
            "heal_amount": heal_amount,
            "hp_before": old_hp,
            "hp_after": combat["current_hp"],
            "summary": (
                f"{character['identity']['character_name']} drinks a {item_name}, "
                f"rolling 2d4+2 and recovering {heal_amount} HP. "
                f"HP: {old_hp} -> {combat['current_hp']}."
            ),
            "available_actions": get_available_combat_actions(),
            "dice_rolls_this_turn": dice_rolls,
            "combat_state": get_combat_public_state()
        }

    return {
        "type": "use_item",
        "item": item_name,
        "success": False,
        "summary": f"{item_name} cannot be used in combat.",
        "available_actions": get_available_combat_actions(),
        "dice_rolls_this_turn": [],
        "combat_state": get_combat_public_state()
    }


def apply_water_dampening(event, floor_num):
    """On floor 2 (Flooded Crypts), halve fire spell damage — standing water kills the heat.
    Refunds half the already-dealt damage back to the enemy in combat state."""
    DAMPENED_SPELLS = {"Fireball", "Burning Hands", "Firebolt", "Shatter"}
    if floor_num != 2 or event.get("spell") not in DAMPENED_SPELLS:
        return event

    raw_damage = event.get("damage", event.get("total_damage", 0))
    if not raw_damage:
        return event

    refund = raw_damage // 2
    if refund > 0:
        combat_state = load_combat_state()
        enemy = combat_state.get("enemy")
        if enemy and enemy.get("hp") is not None:
            enemy["hp"] = min(enemy.get("max_hp", enemy["hp"] + refund), enemy["hp"] + refund)
            save_combat_state(combat_state)
        if "damage" in event:
            event["damage"] = event["damage"] - refund
        if "total_damage" in event:
            event["total_damage"] = event["total_damage"] - refund

    event["water_dampened"] = True
    event["water_flavor"] = (
        "The standing water absorbs the spell's heat, stealing half its force."
    )
    return event