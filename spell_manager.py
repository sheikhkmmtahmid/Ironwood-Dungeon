import json
from pathlib import Path
from combat_manager import (
    roll_d20, roll_dice,
    get_active_enemy, apply_damage_to_enemy, _defeat_active_enemy, reset_combat_state,
    get_combat_public_state, get_available_combat_actions,
    load_combat_state, save_combat_state, advance_turn,
    sync_game_state_from_character, roll_saving_throw, resolve_hunters_mark_cast
)
import character_manager as chars

BASE = Path(__file__).parent

SPELL_REGISTRY = {
    # Wizard cantrips
    "Firebolt":         {"level":0,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"attack_roll","damage_dice":"1d10","damage_type":"fire"},
    "Ray of Frost":     {"level":0,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"attack_roll","damage_dice":"1d8","damage_type":"cold"},
    "Shocking Grasp":   {"level":0,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"attack_roll","damage_dice":"1d8","damage_type":"lightning"},
    "Mage Hand":        {"level":0,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"utility"},
    "Prestidigitation": {"level":0,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"utility"},
    "Minor Illusion":   {"level":0,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"utility"},
    # Cleric cantrips
    "Sacred Flame":     {"level":0,"casting_time":"action","concentration":False,"classes":["Cleric"],"type":"damage_save","damage_dice":"1d8","damage_type":"radiant","save":{"ability":"DEX","on_success":"negate"}},
    "Toll the Dead":    {"level":0,"casting_time":"action","concentration":False,"classes":["Cleric"],"type":"toll_the_dead"},
    "Guidance":         {"level":0,"casting_time":"action","concentration":True, "classes":["Cleric"],"type":"buff","effect":"guidance","concentration_duration_rounds":1},
    "Thaumaturgy":      {"level":0,"casting_time":"action","concentration":False,"classes":["Cleric"],"type":"utility"},
    "Spare the Dying":  {"level":0,"casting_time":"action","concentration":False,"classes":["Cleric"],"type":"spare_the_dying"},
    "Light":            {"level":0,"casting_time":"action","concentration":False,"classes":["Cleric","Wizard"],"type":"utility"},
    # Wizard level 1
    "Magic Missile":    {"level":1,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"magic_missile","damage_dice":"1d4+1","darts":3,"damage_type":"force"},
    "Burning Hands":    {"level":1,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"damage_save","damage_dice":"3d6","damage_type":"fire","save":{"ability":"DEX","on_success":"half"}},
    "Thunderwave":      {"level":1,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"damage_save","damage_dice":"2d8","damage_type":"thunder","save":{"ability":"CON","on_success":"half"},"push":True},
    "Sleep":            {"level":1,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"sleep","hp_pool_dice":"5d8"},
    "Shield":           {"level":1,"casting_time":"reaction","concentration":False,"classes":["Wizard"],"type":"shield","ac_bonus":5},
    "Mage Armor":       {"level":1,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"mage_armor"},
    "Charm Person":     {"level":1,"casting_time":"action","concentration":False,"classes":["Wizard"],"type":"condition_save","condition":"Charmed","save":{"ability":"WIS","on_success":"negate"}},
    "Detect Magic":     {"level":1,"casting_time":"action","concentration":True, "classes":["Wizard"],"type":"utility","concentration_duration_rounds":100},
    # Cleric level 1
    "Cure Wounds":      {"level":1,"casting_time":"action","concentration":False,"classes":["Cleric","Ranger"],"type":"heal","heal_dice":"1d8","heal_ability":"WIS"},
    "Guiding Bolt":     {"level":1,"casting_time":"action","concentration":False,"classes":["Cleric"],"type":"attack_roll","damage_dice":"4d6","damage_type":"radiant","effect":"guiding_bolt"},
    "Bless":            {"level":1,"casting_time":"action","concentration":True, "classes":["Cleric"],"type":"buff","effect":"bless","concentration_duration_rounds":10},
    "Inflict Wounds":   {"level":1,"casting_time":"action","concentration":False,"classes":["Cleric"],"type":"attack_roll","damage_dice":"3d10","damage_type":"necrotic"},
    "Healing Word":     {"level":1,"casting_time":"bonus_action","concentration":False,"classes":["Cleric"],"type":"heal","heal_dice":"1d4","heal_ability":"WIS"},
    "Command":          {"level":1,"casting_time":"action","concentration":False,"classes":["Cleric"],"type":"condition_save","condition":"Commanded","save":{"ability":"WIS","on_success":"negate"}},
    "Sanctuary":        {"level":1,"casting_time":"bonus_action","concentration":False,"classes":["Cleric"],"type":"sanctuary"},
    "Faerie Fire":      {"level":1,"casting_time":"action","concentration":True, "classes":["Cleric"],"type":"faerie_fire","save":{"ability":"DEX","on_success":"negate"},"concentration_duration_rounds":10},
    "Protection from Evil and Good": {"level":1,"casting_time":"action","concentration":True,"classes":["Cleric","Wizard"],"type":"protection","concentration_duration_rounds":100},
    # Ranger level 1
    "Hunter's Mark":    {"level":1,"casting_time":"bonus_action","concentration":True,"classes":["Ranger"],"type":"hunters_mark","concentration_duration_rounds":100},
    "Fog Cloud":        {"level":1,"casting_time":"action","concentration":True, "classes":["Ranger"],"type":"utility","effect":"fog_cloud","concentration_duration_rounds":100},
    "Goodberry":        {"level":1,"casting_time":"action","concentration":False,"classes":["Ranger"],"type":"goodberry"},
    "Ensnaring Strike": {"level":1,"casting_time":"bonus_action","concentration":True,"classes":["Ranger"],"type":"utility","effect":"ensnaring_strike","concentration_duration_rounds":10},
    # Level 2 spells - PHASE 2 added
    "Misty Step":        {"level":2,"casting_time":"bonus_action","concentration":False,"classes":["Wizard","Sorcerer"],"type":"misty_step"},
    "Shatter":           {"level":2,"casting_time":"action","concentration":False,"classes":["Wizard","Bard"],"type":"damage_save","damage_dice":"3d8","damage_type":"thunder","save":{"ability":"CON","on_success":"half"}},
    "Spiritual Weapon":  {"level":2,"casting_time":"bonus_action","concentration":False,"classes":["Cleric"],"type":"spiritual_weapon","damage_dice":"1d8"},
    "Invisibility":      {"level":2,"casting_time":"action","concentration":True,"classes":["Wizard","Bard","Ranger"],"type":"invisibility","concentration_duration_rounds":100},
    # Level 3 spells - PHASE 2 added
    "Fireball":          {"level":3,"casting_time":"action","concentration":False,"classes":["Wizard","Sorcerer"],"type":"damage_save","damage_dice":"8d6","damage_type":"fire","save":{"ability":"DEX","on_success":"half"}},
    "Counterspell":      {"level":3,"casting_time":"reaction","concentration":False,"classes":["Wizard","Sorcerer"],"type":"counterspell"},
    "Call Lightning":    {"level":3,"casting_time":"action","concentration":True,"classes":["Druid"],"type":"damage_save","damage_dice":"3d10","damage_type":"lightning","save":{"ability":"DEX","on_success":"half"},"concentration_duration_rounds":3},
    "Hypnotic Pattern":  {"level":3,"casting_time":"action","concentration":True,"classes":["Wizard","Bard"],"type":"hypnotic_pattern","save":{"ability":"WIS","on_success":"negate"},"concentration_duration_rounds":2},
    "Mass Cure Wounds":  {"level":3,"casting_time":"action","concentration":False,"classes":["Cleric","Bard","Druid"],"type":"mass_cure_wounds","heal_dice":"3d8","heal_ability":"WIS"},
}

SLOT_KEYS = {1:"1st", 2:"2nd", 3:"3rd", 4:"4th", 5:"5th"}  # PHASE 2 added 4th, 5th


def _slot_key(level):
    return SLOT_KEYS.get(level, f"{level}th")


def validate_cast(character, spell_name, slot_level=None):
    spell = SPELL_REGISTRY.get(spell_name)
    if not spell:
        return {"valid": False, "error": f"Unknown spell: {spell_name}"}

    cls = character["identity"]["class"]
    if cls not in spell["classes"]:
        return {"valid": False, "error": f"{cls} cannot cast {spell_name}"}

    sp = character.get("spellcasting", {})
    known = sp.get("spells_known", []) + sp.get("cantrips_known", [])
    if spell_name not in known:
        return {"valid": False, "error": f"{spell_name} not prepared"}

    if spell["level"] == 0:
        return {"valid": True, "slot_used": None}

    level = slot_level or spell["level"]
    sk = _slot_key(level)
    slots = sp.get("spell_slots", {})

    if sk not in slots or slots[sk].get("remaining", 0) <= 0:
        return {"valid": False, "error": f"No {sk}-level spell slots remaining"}

    return {"valid": True, "slot_used": sk}


def _spend_slot(character, slot_key):
    sp = character.get("spellcasting", {})
    sp["spell_slots"][slot_key]["remaining"] -= 1
    character["spellcasting"] = sp
    chars.save_character(character)
    return character


def _apply_concentration(combat_state, spell_name, caster_id="player"):
    # Drop old concentration before applying new one
    if combat_state.get("concentration"):
        old = combat_state["concentration"].get("spell", "")
        _clear_concentration_effects(combat_state, old)
    duration = SPELL_REGISTRY.get(spell_name, {}).get("concentration_duration_rounds", 10)
    combat_state["concentration"] = {
        "spell": spell_name,
        "caster_id": caster_id,
        "duration_turns_remaining": duration,
    }
    save_combat_state(combat_state)


def _clear_concentration_effects(combat_state, spell_name):
    #Remove any combat_state flags that were set by a concentration spell
    if spell_name == "Hunter's Mark":
        combat_state["hunters_mark_active"] = False
    elif spell_name == "Bless":
        combat_state["bless_active"] = False
    elif spell_name == "Fog Cloud":
        combat_state["fog_cloud_active"] = False
    elif spell_name == "Faerie Fire":
        combat_state["faerie_fire_active"] = False
    elif spell_name == "Guidance":
        combat_state["guidance_active"] = False
    elif spell_name == "Protection from Evil and Good":
        combat_state["protection_active"] = False
    elif spell_name == "Invisibility":  # PHASE 2 added
        combat_state["invisible"] = False
    elif spell_name == "Call Lightning":  # PHASE 2 added
        combat_state["call_lightning_turns"] = 0
    elif spell_name == "Hypnotic Pattern":  # PHASE 2 added
        combat_state["hypnotic_pattern_active"] = False


def _base_event(spell_name, character):
    return {
        "type": "cast_spell",
        "spell": spell_name,
        "caster": character["identity"]["character_name"],
        "success": True,
        "dice_rolls_this_turn": [],
        "conditions_applied": [],
        "xp_gained": 0,
    }


def _finish(event, enemy_result=None, combat_state=None, defeated=False):
    if defeated:
        reset_combat_state()
    elif combat_state is not None:
        advance_turn(load_combat_state())
    event["available_actions"] = get_available_combat_actions()
    event["combat_state"] = get_combat_public_state()
    if enemy_result:
        event["xp_awarded"] = enemy_result.get("xp_awarded")
    return event


def resolve_cast(spell_name, slot_level=None):
    character = chars.load_character()
    spell = SPELL_REGISTRY.get(spell_name)
    combat_state = load_combat_state()

    if not spell:
        return {"type":"cast_spell","success":False,"error":f"Unknown spell: {spell_name}",
                "available_actions":get_available_combat_actions(),"dice_rolls_this_turn":[],"combat_state":get_combat_public_state()}

    if spell["type"] == "hunters_mark":
        return resolve_hunters_mark_cast()

    v = validate_cast(character, spell_name, slot_level)
    if not v["valid"]:
        return {"type":"cast_spell","success":False,"error":v["error"],
                "available_actions":get_available_combat_actions(),"dice_rolls_this_turn":[],"combat_state":get_combat_public_state()}

    level = slot_level or spell["level"]
    if v["slot_used"]:
        character = _spend_slot(character, v["slot_used"])

    t = spell["type"]

    if t == "attack_roll":
        return _resolve_attack_roll(spell_name, spell, character, level, combat_state)
    if t == "magic_missile":
        return _resolve_magic_missile(spell_name, spell, character, level, combat_state)
    if t == "damage_save":
        return _resolve_damage_save(spell_name, spell, character, level, combat_state)
    if t == "heal":
        return _resolve_heal(spell_name, spell, character, level, combat_state)
    if t == "buff":
        return _resolve_buff(spell_name, spell, character, level, combat_state)
    if t == "shield":
        return _resolve_shield(spell_name, spell, character, level, combat_state)
    if t == "mage_armor":
        return _resolve_mage_armor(spell_name, spell, character, level, combat_state)
    if t == "sleep":
        return _resolve_sleep(spell_name, spell, character, level, combat_state)
    if t == "condition_save":
        return _resolve_condition_save(spell_name, spell, character, level, combat_state)
    if t == "goodberry":
        return _resolve_goodberry(spell_name, spell, character, level, combat_state)
    if t == "utility":
        return _resolve_utility(spell_name, spell, character, level, combat_state)
    if t == "toll_the_dead":
        return _resolve_toll_the_dead(spell_name, spell, character, level, combat_state)
    if t == "spare_the_dying":
        return _resolve_spare_the_dying(spell_name, spell, character, level, combat_state)
    if t == "faerie_fire":
        return _resolve_faerie_fire(spell_name, spell, character, level, combat_state)
    if t == "sanctuary":
        return _resolve_sanctuary(spell_name, spell, character, level, combat_state)
    if t == "protection":
        return _resolve_protection(spell_name, spell, character, level, combat_state)
    if t == "misty_step":  # PHASE 2 added
        return _resolve_misty_step(spell_name, spell, character, level, combat_state)
    if t == "spiritual_weapon":  # PHASE 2 added
        return _resolve_spiritual_weapon(spell_name, spell, character, level, combat_state)
    if t == "invisibility":  # PHASE 2 added
        return _resolve_invisibility(spell_name, spell, character, level, combat_state)
    if t == "counterspell":  # PHASE 2 added
        return _resolve_counterspell(spell_name, spell, character, level, combat_state)
    if t == "hypnotic_pattern":  # PHASE 2 added
        return _resolve_hypnotic_pattern(spell_name, spell, character, level, combat_state)
    if t == "mass_cure_wounds":  # PHASE 2 added
        return _resolve_mass_cure_wounds(spell_name, spell, character, level, combat_state)

    return {"type":"cast_spell","success":False,"error":f"Unhandled spell type: {t}",
            "available_actions":get_available_combat_actions(),"dice_rolls_this_turn":[],"combat_state":get_combat_public_state()}


def _resolve_attack_roll(spell_name, spell, character, level, combat_state):
    enemy = get_active_enemy()
    event = _base_event(spell_name, character)
    if not enemy:
        event["success"] = False
        event["summary"] = f"No target for {spell_name}."
        return _finish(event, combat_state=combat_state)

    sp = character.get("spellcasting", {})
    ab = sp.get("spell_attack_bonus", 0)
    roll = roll_d20()
    is_crit = roll["result"] == 20
    is_nat1 = roll["result"] == 1
    total = roll["result"] + ab
    hit = (not is_nat1) and (is_crit or total >= enemy["ac"])

    event["dice_rolls_this_turn"].append({"die":"d20","result":roll["result"],"purpose":f"{spell_name} spell attack"})

    damage = 0
    enemy_result = {"enemy_remaining_hp": enemy["hp"], "enemy_defeated": False, "xp_awarded": None}

    if hit:
        dmg = roll_dice(spell["damage_dice"], multiplier=2 if is_crit else 1)
        damage = max(0, dmg["result"])
        event["dice_rolls_this_turn"].append({"die":spell["damage_dice"],"result":damage,"purpose":f"{spell_name} damage"})
        enemy_result = apply_damage_to_enemy(enemy["id"], damage)

    if spell.get("effect") == "guiding_bolt" and hit:
        combat_state["guiding_bolt_active"] = True
        save_combat_state(combat_state)

    if spell.get("concentration") and hit:
        _apply_concentration(combat_state, spell_name)

    crit_txt = " Critical hit!" if is_crit else ""
    event.update({
        "target": enemy["name"], "attack_roll": roll["result"], "attack_total": total,
        "hit": hit, "critical": is_crit, "damage": damage, "damage_type": spell.get("damage_type",""),
        "enemy_hp_after": enemy_result["enemy_remaining_hp"], "enemy_defeated": enemy_result["enemy_defeated"],
        "summary": (
            f"{character['identity']['character_name']} casts {spell_name}.{crit_txt} "
            f"Spell attack {total} vs AC {enemy['ac']}: {'hit' if hit else 'miss'}."
            + (f" {damage} {spell.get('damage_type','')} damage. {enemy['name']} has {enemy_result['enemy_remaining_hp']} HP." if hit else "")
            + (" Next attack against this target has advantage." if spell.get("effect")=="guiding_bolt" and hit else "")
        )
    })
    return _finish(event, enemy_result, combat_state, enemy_result["enemy_defeated"])


def _resolve_magic_missile(spell_name, spell, character, level, combat_state):
    enemy = get_active_enemy()
    event = _base_event(spell_name, character)
    if not enemy:
        event["success"] = False
        event["summary"] = "No target for Magic Missile."
        return _finish(event, combat_state=combat_state)

    darts = spell["darts"] + (level - 1)
    total = 0
    for i in range(darts):
        r = roll_dice(spell["damage_dice"])
        total += r["result"]
        event["dice_rolls_this_turn"].append({"die":spell["damage_dice"],"result":r["result"],"purpose":f"Missile dart {i+1}"})

    enemy_result = apply_damage_to_enemy(enemy["id"], total)
    event.update({
        "target": enemy["name"], "darts": darts, "damage": total, "damage_type": "force",
        "enemy_hp_after": enemy_result["enemy_remaining_hp"], "enemy_defeated": enemy_result["enemy_defeated"],
        "summary": (
            f"{character['identity']['character_name']} fires {darts} Magic Missile darts at {enemy['name']}, "
            f"dealing {total} force damage (auto-hit). {enemy['name']} has {enemy_result['enemy_remaining_hp']} HP."
        )
    })
    return _finish(event, enemy_result, combat_state, enemy_result["enemy_defeated"])


def _resolve_damage_save(spell_name, spell, character, level, combat_state):
    enemy = get_active_enemy()
    event = _base_event(spell_name, character)
    if not enemy:
        event["success"] = False
        event["summary"] = f"No target for {spell_name}."
        return _finish(event, combat_state=combat_state)

    sp = character.get("spellcasting", {})
    dc = sp.get("spell_save_dc", 13)
    save_ab = spell["save"]["ability"]
    on_success = spell["save"]["on_success"]

    save_roll = roll_d20()
    saved = save_roll["result"] >= dc
    event["dice_rolls_this_turn"].append({"die":"d20","result":save_roll["result"],"purpose":f"{enemy['name']} {save_ab} save"})

    full_dmg_roll = roll_dice(spell["damage_dice"])
    full_dmg = max(0, full_dmg_roll["result"])
    event["dice_rolls_this_turn"].append({"die":spell["damage_dice"],"result":full_dmg,"purpose":f"{spell_name} damage"})

    damage = 0 if (saved and on_success=="negate") else (full_dmg//2 if saved else full_dmg)
    enemy_result = apply_damage_to_enemy(enemy["id"], damage)

    push_txt = " Shockwave pushes target 10 feet." if spell.get("push") and not saved else ""
    event.update({
        "target": enemy["name"], "save_ability": save_ab, "dc": dc,
        "save_roll": save_roll["result"], "saved": saved, "damage": damage,
        "enemy_hp_after": enemy_result["enemy_remaining_hp"], "enemy_defeated": enemy_result["enemy_defeated"],
        "summary": (
            f"{character['identity']['character_name']} casts {spell_name}. "
            f"{enemy['name']} {save_ab} save: {save_roll['result']} vs DC {dc}: {'success' if saved else 'failure'}. "
            f"{damage} {spell.get('damage_type','')} damage.{push_txt} "
            f"{enemy['name']} has {enemy_result['enemy_remaining_hp']} HP."
        )
    })
    return _finish(event, enemy_result, combat_state, enemy_result["enemy_defeated"])


def _resolve_heal(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    sp = character.get("spellcasting", {})
    ab = spell.get("heal_ability","WIS")
    score = character.get("ability_scores",{}).get(ab,{}).get("score",10)
    mod = (score - 10) // 2

    heal_roll = roll_dice(spell["heal_dice"])
    heal = max(1, heal_roll["result"] + mod)
    event["dice_rolls_this_turn"].append({"die":spell["heal_dice"],"result":heal,"purpose":f"{spell_name} healing"})

    char = chars.load_character()
    old = char["combat"]["current_hp"]
    char["combat"]["current_hp"] = min(char["combat"]["max_hp"], old + heal)
    chars.save_character(char)
    sync_game_state_from_character()

    event.update({
        "heal_amount": heal, "hp_before": old, "hp_after": char["combat"]["current_hp"],
        "summary": (
            f"{char['identity']['character_name']} casts {spell_name}, "
            f"rolling {spell['heal_dice']}+{mod} to recover {heal} HP. "
            f"HP: {old} -> {char['combat']['current_hp']}."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_buff(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    _apply_concentration(combat_state, spell_name)
    if spell.get("effect") == "bless":
        combat_state["bless_active"] = True
        save_combat_state(combat_state)
    event["summary"] = (
        f"{character['identity']['character_name']} casts {spell_name}. "
        f"Attack rolls and saving throws gain +1d4 while concentration holds."
    )
    return _finish(event, combat_state=combat_state)


def _resolve_shield(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    combat_state["shield_active"] = True
    combat_state["shield_ac_bonus"] = spell.get("ac_bonus", 5)
    save_combat_state(combat_state)
    event.update({
        "ac_bonus": spell.get("ac_bonus",5),
        "summary": (
            f"{character['identity']['character_name']} casts Shield as a reaction, "
            f"adding +{spell.get('ac_bonus',5)} AC until the start of their next turn."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_mage_armor(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    dex_mod = character["ability_scores"]["DEX"]["modifier"]
    new_ac = 13 + dex_mod
    char = chars.load_character()
    if char["combat"]["armor_class"] < new_ac:
        char["combat"]["armor_class"] = new_ac
        chars.save_character(char)
    event.update({
        "new_ac": new_ac,
        "summary": (
            f"{character['identity']['character_name']} casts Mage Armor. "
            f"AC becomes {new_ac} (13 + DEX {dex_mod:+d}) for 8 hours."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_sleep(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    enemy = get_active_enemy()
    pool_roll = roll_dice(spell["hp_pool_dice"])
    pool = pool_roll["result"]
    event["dice_rolls_this_turn"].append({"die":spell["hp_pool_dice"],"result":pool,"purpose":"Sleep HP pool"})

    if not enemy:
        event["summary"] = f"Sleep generates {pool} HP of sleep. No valid targets in range."
        return _finish(event, combat_state=combat_state)

    if enemy["hp"] <= pool:
        result = _defeat_active_enemy("sleep_success")
        event.update({
            "enemy_defeated": True, "enemy_hp_after": 0,
            "summary": (
                f"{character['identity']['character_name']} casts Sleep, generating {pool} HP. "
                f"{enemy['name']} (HP {enemy['hp']}) succumbs and falls unconscious."
            )
        })
        return _finish(event, result, None, True)
    else:
        event.update({
            "enemy_defeated": False,
            "summary": (
                f"{character['identity']['character_name']} casts Sleep, generating {pool} HP. "
                f"{enemy['name']} (HP {enemy['hp']}) is unaffected."
            )
        })
        return _finish(event, combat_state=combat_state)


def _resolve_condition_save(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    enemy = get_active_enemy()
    if not enemy:
        event["success"] = False
        event["summary"] = f"No target for {spell_name}."
        return _finish(event, combat_state=combat_state)

    sp = character.get("spellcasting", {})
    dc = sp.get("spell_save_dc", 13)
    save_ab = spell["save"]["ability"]
    save_roll = roll_d20()
    saved = save_roll["result"] >= dc
    event["dice_rolls_this_turn"].append({"die":"d20","result":save_roll["result"],"purpose":f"{enemy['name']} {save_ab} save"})

    if not saved:
        combat_state[f"{spell.get('condition','condition').lower()}_active"] = True
        save_combat_state(combat_state)

    event.update({
        "target": enemy["name"], "dc": dc, "save_roll": save_roll["result"], "saved": saved,
        "condition_applied": None if saved else spell.get("condition"),
        "summary": (
            f"{character['identity']['character_name']} casts {spell_name} on {enemy['name']}. "
            f"{save_ab} save: {save_roll['result']} vs DC {dc}: "
            + ("success — no effect." if saved else f"failure — {spell.get('condition','Affected')}.")
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_goodberry(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    char = chars.load_character()
    equipment = char.get("equipment", [])
    existing = next((i for i in equipment if i.get("item_id") == "goodberry"), None)
    if existing:
        existing["quantity"] = existing.get("quantity", 0) + 10
    else:
        equipment.append({
            "item_id": "goodberry", "name": "Goodberry", "quantity": 10,
            "type": "consumable", "description": "Each berry restores 1 HP when eaten.",
            "weight": 0, "equipped": False
        })
    char["equipment"] = equipment
    chars.save_character(char)
    event.update({
        "berries_created": 10,
        "summary": (
            f"{character['identity']['character_name']} casts Goodberry, conjuring 10 magical berries. "
            f"Each berry restores 1 HP when eaten."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_utility(spell_name, spell, character, level, combat_state):
    event = _base_event(spell_name, character)
    if spell.get("concentration"):
        _apply_concentration(combat_state, spell_name)
    effect = spell.get("effect", "")
    if effect == "fog_cloud":
        combat_state["fog_cloud_active"] = True
        save_combat_state(combat_state)
        msg = "A 20-foot sphere of thick fog fills the area. All attacks within are made with disadvantage."
    elif effect == "ensnaring_strike":
        combat_state["ensnaring_strike_ready"] = True
        save_combat_state(combat_state)
        msg = "Magical vines are ready. Your next hit may restrain the target (STR save)."
    else:
        msg = "The spell takes effect."
    event["summary"] = f"{character['identity']['character_name']} casts {spell_name}. {msg}"
    return _finish(event, combat_state=combat_state)


def _resolve_toll_the_dead(spell_name, spell, character, level, combat_state):
    #Toll the Dead: 1d8 if target is at full HP, 1d12 if wounded
    enemy = get_active_enemy()
    event = _base_event(spell_name, character)
    if not enemy:
        event["success"] = False
        event["summary"] = "No target for Toll the Dead."
        return _finish(event, combat_state=combat_state)

    sp = character.get("spellcasting", {})
    dc = sp.get("spell_save_dc", 13)

    from combat_manager import load_game_state
    state = load_game_state()
    game_enemy = state.get("enemy", {})
    wounded = game_enemy.get("hp", enemy["hp"]) < enemy.get("max_hp", enemy["hp"])
    dice_expr = "1d12" if wounded else "1d8"

    save_roll = roll_d20()
    saved = save_roll["result"] >= dc
    event["dice_rolls_this_turn"].append({"die":"d20","result":save_roll["result"],"purpose":f"{enemy['name']} WIS save"})

    damage = 0
    enemy_result = {"enemy_remaining_hp": enemy["hp"], "enemy_defeated": False, "xp_awarded": None}
    if not saved:
        dmg_roll = roll_dice(dice_expr)
        damage = max(0, dmg_roll["result"])
        event["dice_rolls_this_turn"].append({"die":dice_expr,"result":damage,"purpose":"Toll the Dead damage"})
        enemy_result = apply_damage_to_enemy(enemy["id"], damage)

    event.update({
        "target": enemy["name"], "dc": dc, "save_roll": save_roll["result"], "saved": saved,
        "damage": damage, "damage_type": "necrotic",
        "enemy_hp_after": enemy_result["enemy_remaining_hp"], "enemy_defeated": enemy_result["enemy_defeated"],
        "summary": (
            f"{character['identity']['character_name']} tolls the death knell for {enemy['name']}. "
            f"WIS save: {save_roll['result']} vs DC {dc}: {'success — no effect.' if saved else f'failure — {damage} necrotic damage ({dice_expr}).'} "
            + (f"{enemy['name']} has {enemy_result['enemy_remaining_hp']} HP." if not saved else "")
        )
    })
    return _finish(event, enemy_result, combat_state, enemy_result["enemy_defeated"])


def _resolve_spare_the_dying(spell_name, spell, character, level, combat_state):
    #Spare the Dying: stabilise a creature at 0 HP without a death save roll
    from combat_manager import _get_condition, _add_condition, save_character as _save_char
    event = _base_event(spell_name, character)
    char = chars.load_character()
    if char["combat"]["current_hp"] > 0:
        event["success"] = False
        event["summary"] = f"{char['identity']['character_name']} is conscious — Spare the Dying has no effect."
        return _finish(event, combat_state=combat_state)

    if _get_condition(char, "Stable") or _get_condition(char, "Dead"):
        event["success"] = False
        event["summary"] = "The target is already stable or dead."
        return _finish(event, combat_state=combat_state)

    char = _add_condition(char, "Stable", source="Spare the Dying",
                          effects=["Stable at 0 HP. No further death saves unless damaged."])
    char["combat"]["death_saves"] = {"successes": 0, "failures": 0}
    _save_char(char)
    event.update({
        "summary": (
            f"{character['identity']['character_name']} casts Spare the Dying. "
            f"{char['identity']['character_name']} is stabilised at 0 HP."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_faerie_fire(spell_name, spell, character, level, combat_state):
    #Faerie Fire: DEX save vs spell_save_dc; fail = target outlined, all attacks against it have advantage
    enemy = get_active_enemy()
    event = _base_event(spell_name, character)
    if not enemy:
        event["success"] = False
        event["summary"] = "No target for Faerie Fire."
        return _finish(event, combat_state=combat_state)

    sp = character.get("spellcasting", {})
    dc = sp.get("spell_save_dc", 13)
    save_roll = roll_d20()
    saved = save_roll["result"] >= dc
    event["dice_rolls_this_turn"].append({"die":"d20","result":save_roll["result"],"purpose":f"{enemy['name']} DEX save"})

    if not saved:
        _apply_concentration(combat_state, spell_name)
        combat_state["faerie_fire_active"] = True
        save_combat_state(combat_state)

    event.update({
        "target": enemy["name"], "dc": dc, "save_roll": save_roll["result"], "saved": saved,
        "condition_applied": None if saved else "Faerie Fire",
        "summary": (
            f"{character['identity']['character_name']} casts Faerie Fire on {enemy['name']}. "
            f"DEX save: {save_roll['result']} vs DC {dc}: "
            + ("success — no effect." if saved else "failure — target is outlined in light. All attacks against it have advantage.")
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_sanctuary(spell_name, spell, character, level, combat_state):
    #Sanctuary: next enemy attack against the player must succeed on WIS save or pick a different target
    event = _base_event(spell_name, character)
    combat_state["sanctuary_active"] = True
    save_combat_state(combat_state)
    event.update({
        "summary": (
            f"{character['identity']['character_name']} casts Sanctuary. "
            f"The next enemy attack must succeed on a WIS save or be redirected."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_protection(spell_name, spell, character, level, combat_state):
    #Protection from Evil and Good: concentration. Enemy attacks have disadvantage; player is immune to Frightened
    event = _base_event(spell_name, character)
    _apply_concentration(combat_state, spell_name)
    combat_state["protection_active"] = True
    save_combat_state(combat_state)
    event.update({
        "summary": (
            f"{character['identity']['character_name']} casts Protection from Evil and Good. "
            f"Enemy attacks against you are made with disadvantage and you cannot be Frightened while concentration holds."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_misty_step(spell_name, spell, character, level, combat_state):  # PHASE 2 added
    event = _base_event(spell_name, character)
    char = chars.load_character()
    conditions = char["combat"].get("conditions", [])
    freed = [c["name"] for c in conditions if c.get("name") in ("Restrained", "Grappled")]
    char["combat"]["conditions"] = [c for c in conditions if c.get("name") not in ("Restrained", "Grappled")]
    chars.save_character(char)
    combat_state["misty_step_used"] = True
    save_combat_state(combat_state)
    freed_txt = f" Breaking free of {', '.join(freed)}." if freed else ""
    event.update({
        "summary": (
            f"{character['identity']['character_name']} casts Misty Step, teleporting up to 30 feet in a silver flash.{freed_txt} "
            "You may move freely without triggering opportunity attacks this turn."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_spiritual_weapon(spell_name, spell, character, level, combat_state):  # PHASE 2 added
    event = _base_event(spell_name, character)
    enemy = get_active_enemy()
    if not enemy:
        event["success"] = False
        event["summary"] = "No target for Spiritual Weapon."
        return _finish(event, combat_state=combat_state)

    sp = character.get("spellcasting", {})
    wis_mod = character["ability_scores"]["WIS"]["modifier"]
    ab = sp.get("spell_attack_bonus", 0)
    roll = roll_d20()
    is_crit = roll["result"] == 20
    is_nat1 = roll["result"] == 1
    total = roll["result"] + ab
    hit = (not is_nat1) and (is_crit or total >= enemy["ac"])

    event["dice_rolls_this_turn"].append({"die": "d20", "result": roll["result"], "purpose": "Spiritual Weapon attack"})

    damage = 0
    enemy_result = {"enemy_remaining_hp": enemy["hp"], "enemy_defeated": False, "xp_awarded": None}
    if hit:
        dmg = roll_dice(spell["damage_dice"], multiplier=2 if is_crit else 1)
        damage = max(0, dmg["result"] + wis_mod)
        event["dice_rolls_this_turn"].append({"die": spell["damage_dice"], "result": damage, "purpose": "Spiritual Weapon damage"})
        enemy_result = apply_damage_to_enemy(enemy["id"], damage)

    combat_state["spiritual_weapon_turns"] = 2
    save_combat_state(combat_state)

    crit_txt = " Critical hit!" if is_crit else ""
    event.update({
        "target": enemy["name"], "attack_roll": roll["result"], "attack_total": total,
        "hit": hit, "damage": damage,
        "summary": (
            f"{character['identity']['character_name']} summons a Spiritual Weapon.{crit_txt} "
            f"Attack {total} vs AC {enemy['ac']}: {'hit' if hit else 'miss'}."
            + (f" {damage} force damage. {enemy['name']} has {enemy_result['enemy_remaining_hp']} HP." if hit else "")
            + " The weapon persists for 2 more turns."
        )
    })
    return _finish(event, enemy_result, combat_state, enemy_result["enemy_defeated"])


def _resolve_invisibility(spell_name, spell, character, level, combat_state):  # PHASE 2 added
    event = _base_event(spell_name, character)
    _apply_concentration(combat_state, spell_name)
    combat_state["invisible"] = True
    save_combat_state(combat_state)
    event.update({
        "summary": (
            f"{character['identity']['character_name']} casts Invisibility, fading from sight. "
            "Your attacks are made with advantage and enemies attack you with disadvantage while invisible. "
            "Concentration holds until you attack or cast another spell."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_counterspell(spell_name, spell, character, level, combat_state):  # PHASE 2 added
    event = _base_event(spell_name, character)
    combat_state["counterspell_ready"] = True
    save_combat_state(combat_state)
    event.update({
        "summary": (
            f"{character['identity']['character_name']} readies Counterspell as a reaction. "
            "The next magical attack or spell from an enemy will be cancelled."
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_hypnotic_pattern(spell_name, spell, character, level, combat_state):  # PHASE 2 added
    event = _base_event(spell_name, character)
    enemy = get_active_enemy()
    if not enemy:
        event["success"] = False
        event["summary"] = f"No target for {spell_name}."
        return _finish(event, combat_state=combat_state)

    sp = character.get("spellcasting", {})
    dc = sp.get("spell_save_dc", 13)
    save_roll = roll_d20()
    saved = save_roll["result"] >= dc
    event["dice_rolls_this_turn"].append({"die": "d20", "result": save_roll["result"], "purpose": f"{enemy['name']} WIS save"})

    if not saved:
        _apply_concentration(combat_state, spell_name)
        combat_state["hypnotic_pattern_active"] = True
        combat_state["hypnotic_pattern_turns"] = 2
        save_combat_state(combat_state)

    event.update({
        "target": enemy["name"], "dc": dc, "save_roll": save_roll["result"], "saved": saved,
        "condition_applied": None if saved else "Incapacitated",
        "summary": (
            f"{character['identity']['character_name']} weaves a Hypnotic Pattern. "
            f"{enemy['name']} WIS save: {save_roll['result']} vs DC {dc}: "
            + ("success — unaffected." if saved else
               f"failure — {enemy['name']} is incapacitated for up to 2 turns while concentration holds.")
        )
    })
    return _finish(event, combat_state=combat_state)


def _resolve_mass_cure_wounds(spell_name, spell, character, level, combat_state):  # PHASE 2 added
    event = _base_event(spell_name, character)
    sp = character.get("spellcasting", {})
    ab = spell.get("heal_ability", "WIS")
    score = character.get("ability_scores", {}).get(ab, {}).get("score", 10)
    mod = (score - 10) // 2

    heal_roll = roll_dice(spell["heal_dice"])
    heal = max(1, heal_roll["result"] + mod)
    event["dice_rolls_this_turn"].append({"die": spell["heal_dice"], "result": heal, "purpose": "Mass Cure Wounds healing"})

    char = chars.load_character()
    old = char["combat"]["current_hp"]
    char["combat"]["current_hp"] = min(char["combat"]["max_hp"], old + heal)
    chars.save_character(char)
    sync_game_state_from_character()

    event.update({
        "heal_amount": heal, "hp_before": old, "hp_after": char["combat"]["current_hp"],
        "summary": (
            f"{char['identity']['character_name']} casts Mass Cure Wounds, channelling divine energy. "
            f"Rolling {spell['heal_dice']}+{mod}: {heal} HP restored. "
            f"HP: {old} → {char['combat']['current_hp']}."
        )
    })
    return _finish(event, combat_state=combat_state)


def get_available_spells(character):
    cls = character["identity"]["class"]
    sp = character.get("spellcasting", {})
    slots = sp.get("spell_slots", {})
    cantrips = sp.get("cantrips_known", [])
    spells_known = sp.get("spells_known", [])
    has_slot = any(isinstance(v, dict) and v.get("remaining", 0) > 0 for v in slots.values())

    available = []
    for name in cantrips:
        if name in SPELL_REGISTRY and cls in SPELL_REGISTRY[name]["classes"]:
            available.append(name)
    if has_slot:
        for name in spells_known:
            if name not in SPELL_REGISTRY:
                continue
            spell = SPELL_REGISTRY[name]
            if cls not in spell["classes"]:
                continue
            if spell["level"] == 0:
                continue
            sk = _slot_key(spell["level"])
            if isinstance(slots.get(sk), dict) and slots[sk].get("remaining", 0) > 0:
                available.append(name)
    return available
