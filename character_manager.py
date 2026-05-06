import json, random, threading
from pathlib import Path

BASE           = Path(__file__).parent
CHARACTER_FILE = BASE / "character.json"  # legacy alias — solo play / external references

_ctx = threading.local()

def set_player_name(name):
    _ctx.player_name = (name or "").strip()

def _pn():
    return getattr(_ctx, "player_name", "")

def _char_file():
    pn = _pn()
    if pn:
        return BASE / f"character_{pn}.json"
    return CHARACTER_FILE

ABILITIES       = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
STANDARD_ARRAY  = [15, 14, 13, 12, 10, 8]
XP_THRESHOLDS   = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000}  # PHASE 2 added levels 5-10
HIT_DICE        = {"Fighter": 10, "Rogue": 8, "Wizard": 6, "Cleric": 8, "Ranger": 10}

CLASS_SAVING_THROWS = {
    "Fighter": ["STR", "CON"],
    "Rogue":   ["DEX", "INT"],
    "Wizard":  ["INT", "WIS"],
    "Cleric":  ["WIS", "CHA"],
    "Ranger":  ["STR", "DEX"],
}

SKILLS = {
    "Acrobatics":      "DEX",
    "Animal Handling": "WIS",
    "Arcana":          "INT",
    "Athletics":       "STR",
    "Deception":       "CHA",
    "History":         "INT",
    "Insight":         "WIS",
    "Intimidation":    "CHA",
    "Investigation":   "INT",
    "Medicine":        "WIS",
    "Nature":          "INT",
    "Perception":      "WIS",
    "Performance":     "CHA",
    "Persuasion":      "CHA",
    "Religion":        "INT",
    "Sleight of Hand": "DEX",
    "Stealth":         "DEX",
    "Survival":        "WIS",
}

CLASS_SKILL_OPTIONS = {
    "Fighter": {"pick": 2, "options": ["Athletics","Acrobatics","History","Insight","Intimidation","Perception","Survival"]},
    "Rogue":   {"pick": 4, "options": ["Acrobatics","Athletics","Deception","Insight","Intimidation","Investigation","Perception","Performance","Persuasion","Sleight of Hand","Stealth"]},
    "Wizard":  {"pick": 2, "options": ["Arcana","History","Insight","Investigation","Medicine","Religion"]},
    "Cleric":  {"pick": 2, "options": ["History","Insight","Medicine","Persuasion","Religion"]},
    "Ranger":  {"pick": 3, "options": ["Animal Handling","Athletics","Insight","Investigation","Nature","Perception","Stealth","Survival"]},
}

BACKGROUND_SKILLS = {
    "Soldier":   ["Athletics", "Intimidation"],
    "Criminal":  ["Deception", "Stealth"],
    "Sage":      ["Arcana", "History"],
    "Acolyte":   ["Insight", "Religion"],
    "Outlander": ["Athletics", "Survival"],
}

BACKGROUND_FEATURES = {
    "Soldier":   "Military Rank: Soldiers loyal to your former organization still respect your rank and may offer aid.",
    "Criminal":  "Criminal Contact: A reliable contact links you to a network of criminals who can provide information and passage.",
    "Sage":      "Researcher: When you lack a piece of lore, you know where to find it, even if it takes time.",
    "Acolyte":   "Shelter of the Faithful: You and companions receive free healing and care at temples of your faith.",
    "Outlander": "Wanderer: You have an excellent memory for maps and terrain, recalling the general layout of lands you have visited.",
}

RACE_ASI = {
    "Human":    {"STR":1,"DEX":1,"CON":1,"INT":1,"WIS":1,"CHA":1},
    "Elf":      {"DEX":2,"INT":1},
    "Dwarf":    {"CON":2,"WIS":1},
    "Halfling": {"DEX":2,"CHA":1},
    "Half-Orc": {"STR":2,"CON":1},
}

RACE_SPEED = {"Human":30,"Elf":30,"Dwarf":25,"Halfling":25,"Half-Orc":30}

RACE_LANGUAGES = {
    "Human":    ["Common","one of your choice"],
    "Elf":      ["Common","Elvish"],
    "Dwarf":    ["Common","Dwarvish"],
    "Halfling": ["Common","Halfling"],
    "Half-Orc": ["Common","Orc"],
}

RACE_TRAITS = {
    "Human": [
        {"name":"Extra Skill","description":"Gain one additional skill proficiency of your choice."},
        {"name":"Extra Language","description":"You know one extra language of your choice."},
    ],
    "Elf": [
        {"name":"Darkvision","description":"See in dim light within 60 ft as if bright light, and in darkness as dim light."},
        {"name":"Fey Ancestry","description":"Advantage on saving throws against being charmed. Magic cannot put you to sleep."},
        {"name":"Trance","description":"You do not sleep. 4 hours of meditation equals a full long rest."},
        {"name":"Keen Senses","description":"Proficiency in the Perception skill."},
        {"name":"Elf Weapon Training","description":"Proficiency with longsword, shortsword, longbow, and shortbow."},
    ],
    "Dwarf": [
        {"name":"Darkvision","description":"See in dim light within 60 ft as if bright light, in darkness as dim light."},
        {"name":"Dwarven Resilience","description":"Advantage on saving throws against poison. Resistance to poison damage."},
        {"name":"Stonecunning","description":"Double proficiency bonus on History checks related to the origin of stonework."},
        {"name":"Dwarven Combat Training","description":"Proficiency with battleaxe, handaxe, light hammer, and warhammer."},
    ],
    "Halfling": [
        {"name":"Lucky","description":"When you roll a 1 on an attack roll, ability check, or saving throw, you can reroll and must use the new result."},
        {"name":"Brave","description":"Advantage on saving throws against being frightened."},
        {"name":"Halfling Nimbleness","description":"You can move through the space of any creature that is of a size larger than yours."},
        {"name":"Naturally Stealthy","description":"You can attempt to hide even when obscured only by a creature one size larger than you."},
    ],
    "Half-Orc": [
        {"name":"Darkvision","description":"See in dim light within 60 ft as if bright light, in darkness as dim light."},
        {"name":"Relentless Endurance","description":"Once per long rest, when reduced to 0 HP but not killed, drop to 1 HP instead.","uses_max":1,"uses_remaining":1,"recharge_on":"long_rest"},
        {"name":"Savage Attacks","description":"When you score a critical hit with a melee weapon, roll one of the damage dice one additional time and add it to the damage."},
        {"name":"Menacing","description":"You have proficiency in the Intimidation skill."},
    ],
}

ARMOR_PROFICIENCY = {
    "Fighter": ["Light","Medium","Heavy","Shields"],
    "Rogue":   ["Light"],
    "Wizard":  [],
    "Cleric":  ["Light","Medium","Shields"],
    "Ranger":  ["Light","Medium","Shields"],
}

WEAPON_PROFICIENCY = {
    "Fighter": ["Simple","Martial"],
    "Rogue":   ["Simple","Hand crossbows","Longswords","Rapiers","Shortswords"],
    "Wizard":  ["Daggers","Darts","Slings","Quarterstaffs","Light crossbows"],
    "Cleric":  ["Simple"],
    "Ranger":  ["Simple","Martial"],
}

CLASS_DESCRIPTIONS = {
    "Fighter": "Master of weapons and armor. High HP, multiple attacks, and the versatile Second Wind. Excellent for beginners.",
    "Rogue":   "Cunning trickster. Sneak Attack deals bonus damage, Expertise doubles proficiency on key skills. DEX-based striker.",
    "Wizard":  "Arcane spellcaster with powerful damaging and utility spells. Low HP, high impact. Mastery of the arcane arts.",
    "Cleric":  "Divine warrior and healer. Can mend wounds, buff allies, and smite enemies with radiant power.",
    "Ranger":  "Wilderness hunter with bow and blade. Tracks enemies, reads terrain, and thrives in the dungeon depths.",
}

RACE_DESCRIPTIONS = {
    "Human":    "Adaptable and ambitious. +1 to every ability score, one extra skill, and one extra language.",
    "Elf":      "Ancient and perceptive. +2 DEX +1 INT, Darkvision, immunity to magical sleep, and weapon training.",
    "Dwarf":    "Resilient and stalwart. +2 CON +1 WIS, Darkvision, poison resistance, and stonecunning.",
    "Halfling": "Small but tenacious. +2 DEX +1 CHA. Lucky rerolls 1s, Brave resists fear, Naturally Stealthy.",
    "Half-Orc": "Fierce and enduring. +2 STR +1 CON, Darkvision, Relentless Endurance, and brutal critical hits.",
}


def ability_modifier(score):
    return (score - 10) // 2

def prof_bonus_for_level(level):
    if level <= 4: return 2
    if level <= 8: return 3  # PHASE 2 added
    return 4  # PHASE 2 added (levels 9-10)

def level_from_xp(xp):
    result = 1
    for lv, threshold in sorted(XP_THRESHOLDS.items(), reverse=True):
        if xp >= threshold:
            result = lv
            break
    return result


ITEM_CATALOG = {
    "health_potion":         {"name":"Health Potion",          "type":"consumable","weight":0.5,"cost":50,  "description":"Restores 2d4+2 HP."},
    "greater_health_potion": {"name":"Greater Healing Potion", "type":"consumable","weight":0.5,"cost":150, "description":"Restores 4d4+4 HP."},
    "elixir_of_speed":       {"name":"Elixir of Speed",        "type":"consumable","weight":0.5,"cost":100, "description":"Grants +10 speed for 1 hour."},
    "longsword":             {"name":"Longsword",              "type":"weapon",   "weight":3,  "cost":15,  "description":"1d8 slashing. Versatile (1d10)."},
    "shortsword":            {"name":"Shortsword",             "type":"weapon",   "weight":2,  "cost":10,  "description":"1d6 piercing. Finesse, Light."},
    "dagger":                {"name":"Dagger",                 "type":"weapon",   "weight":1,  "cost":2,   "description":"1d4 piercing. Finesse, Thrown."},
    "quarterstaff":          {"name":"Quarterstaff",           "type":"weapon",   "weight":4,  "cost":2,   "description":"1d6 bludgeoning. Versatile (1d8)."},
    "mace":                  {"name":"Mace",                   "type":"weapon",   "weight":4,  "cost":5,   "description":"1d6 bludgeoning."},
    "longbow":               {"name":"Longbow",                "type":"weapon",   "weight":2,  "cost":50,  "description":"1d8 piercing. Range 150/600."},
    "chain_mail":            {"name":"Chain Mail",             "type":"armor",    "weight":55, "cost":75,  "description":"Heavy armor. AC 16. STR 13 required."},
    "scale_mail":            {"name":"Scale Mail",             "type":"armor",    "weight":45, "cost":50,  "description":"Medium armor. AC 14 + DEX (max +2)."},
    "leather_armor":         {"name":"Leather Armor",          "type":"armor",    "weight":10, "cost":10,  "description":"Light armor. AC 11 + DEX."},
    "shield":                {"name":"Shield",                 "type":"shield",   "weight":6,  "cost":10,  "description":"+2 AC while equipped."},
    "ring_of_protection":    {"name":"Ring of Protection",     "type":"ring",     "weight":0,  "cost":500, "description":"+1 AC and saving throws."},
    "cloak_of_shadows":      {"name":"Cloak of Shadows",       "type":"cloak",    "weight":1,  "cost":300, "description":"+2 to Stealth checks."},
    "arcane_focus":          {"name":"Arcane Focus",           "type":"focus",    "weight":1,  "cost":10,  "description":"Required for spellcasting."},
    "holy_symbol":           {"name":"Holy Symbol",            "type":"focus",    "weight":1,  "cost":5,   "description":"Required for cleric spellcasting."},
    "thieves_tools":         {"name":"Thieves Tools",          "type":"tool",     "weight":1,  "cost":25,  "description":"+2 to Stealth and trap disarming."},
    "spellbook":             {"name":"Spellbook",              "type":"book",     "weight":3,  "cost":50,  "description":"Holds your prepared wizard spells."},
    "arrows":                {"name":"Arrows (20)",            "type":"ammo",     "weight":1,  "cost":1,   "description":"Ammunition for the longbow."},
    "torch":                 {"name":"Torch",                  "type":"utility",  "weight":1,  "cost":1,   "description":"Bright light in 20ft radius."},
    "rope":                  {"name":"Rope (50ft)",            "type":"utility",  "weight":10, "cost":1,   "description":"Useful for climbing or binding."},
    "antitoxin":             {"name":"Antitoxin",              "type":"consumable","weight":0.5,"cost":50, "description":"Removes poison condition. Grants advantage vs poison for 1 hour."},
    "spell_scroll":          {"name":"Spell Scroll",           "type":"consumable","weight":0.5,"cost":75, "description":"Single-use scroll. Casts a random arcane spell."},
    "focus_crystal":         {"name":"Focus Crystal",          "type":"focus",    "weight":0.5,"cost":80,  "description":"+1 to spell attack rolls and spell save DC."},
}

SHOP_BY_FLOOR = {
    1: ["health_potion","torch","rope","shield"],
    2: ["health_potion","greater_health_potion","scale_mail","cloak_of_shadows"],
    3: ["health_potion","greater_health_potion","ring_of_protection","elixir_of_speed"],
    4: ["greater_health_potion","ring_of_protection","elixir_of_speed"],
}

NON_EQUIPPABLE_TYPES = {"consumable","utility","ammo","tool","book"}


def _compute_ac(scores, equipment):
    dex_mod     = ability_modifier(scores["DEX"])
    has_chain   = any(e.get("item_id") == "chain_mail"         and e.get("equipped") for e in equipment)
    has_scale   = any(e.get("item_id") == "scale_mail"         and e.get("equipped") for e in equipment)
    has_leather = any(e.get("item_id") == "leather_armor"      and e.get("equipped") for e in equipment)
    has_shield  = any(e.get("item_id") == "shield"             and e.get("equipped") for e in equipment)
    has_ring    = any(e.get("item_id") == "ring_of_protection"  and e.get("equipped") for e in equipment)
    shield_bonus = 2 if has_shield else 0
    ring_bonus   = 1 if has_ring   else 0
    if has_chain:
        return 16 + shield_bonus + ring_bonus
    if has_scale:
        return 14 + min(2, dex_mod) + shield_bonus + ring_bonus
    if has_leather:
        return 11 + dex_mod + shield_bonus + ring_bonus
    return 10 + dex_mod + shield_bonus + ring_bonus


def _build_equipment(cls):
    def item(iid, equipped, qty):
        cat = ITEM_CATALOG.get(iid, {})
        return {"item_id":iid,"name":cat.get("name",iid),"weight":cat.get("weight",0),
                "type":cat.get("type",""),"description":cat.get("description",""),
                "equipped":equipped,"quantity":qty}
    if cls == "Fighter":
        return [item("longsword",True,1),item("shield",True,1),item("chain_mail",True,1),item("health_potion",False,2)]
    if cls == "Rogue":
        return [item("shortsword",True,1),item("dagger",True,2),item("leather_armor",True,1),item("thieves_tools",False,1),item("health_potion",False,1)]
    if cls == "Wizard":
        return [item("quarterstaff",True,1),item("arcane_focus",True,1),item("spellbook",False,1),item("health_potion",False,1)]
    if cls == "Cleric":
        return [item("mace",True,1),item("shield",True,1),item("chain_mail",True,1),item("holy_symbol",True,1),item("health_potion",False,2)]
    if cls == "Ranger":
        return [item("shortsword",True,1),item("longbow",True,1),item("arrows",False,1),item("leather_armor",True,1),item("health_potion",False,2)]
    return []


def _build_attacks(cls, scores, pb):
    s = ability_modifier(scores["STR"])
    d = ability_modifier(scores["DEX"])
    i = ability_modifier(scores["INT"])
    w = ability_modifier(scores["WIS"])
    fin = max(s, d)
    attacks = []
    if cls == "Fighter":
        attacks.append({"name":"Longsword","attack_bonus":s+pb,"damage_dice":"1d8","damage_type":"slashing","range":"5ft","properties":["versatile 1d10"],"notes":""})
    elif cls == "Rogue":
        attacks.append({"name":"Shortsword","attack_bonus":fin+pb,"damage_dice":"1d6","damage_type":"piercing","range":"5ft","properties":["finesse","light"],"notes":"Sneak Attack eligible"})
        attacks.append({"name":"Dagger","attack_bonus":fin+pb,"damage_dice":"1d4","damage_type":"piercing","range":"5ft/20ft","properties":["finesse","thrown","light"],"notes":"Sneak Attack eligible"})
    elif cls == "Wizard":
        attacks.append({"name":"Quarterstaff","attack_bonus":s+pb,"damage_dice":"1d6","damage_type":"bludgeoning","range":"5ft","properties":["versatile 1d8"],"notes":""})
        attacks.append({"name":"Firebolt","attack_bonus":i+pb,"damage_dice":"1d10","damage_type":"fire","range":"120ft","properties":["ranged","spell","cantrip"],"notes":"No slot needed"})
    elif cls == "Cleric":
        attacks.append({"name":"Mace","attack_bonus":s+pb,"damage_dice":"1d6","damage_type":"bludgeoning","range":"5ft","properties":[],"notes":""})
        attacks.append({"name":"Sacred Flame","attack_bonus":0,"damage_dice":"1d8","damage_type":"radiant","range":"60ft","properties":["cantrip","dex save"],"notes":f"DC {8+pb+w} DEX save or take damage"})
    elif cls == "Ranger":
        attacks.append({"name":"Shortsword","attack_bonus":fin+pb,"damage_dice":"1d6","damage_type":"piercing","range":"5ft","properties":["finesse"],"notes":""})
        attacks.append({"name":"Longbow","attack_bonus":d+pb,"damage_dice":"1d8","damage_type":"piercing","range":"150/600ft","properties":["ranged","two-handed"],"notes":""})
    return attacks


def _build_spellcasting(cls, scores, level, pb):
    int_mod = ability_modifier(scores["INT"])
    wis_mod = ability_modifier(scores["WIS"])

    def slots(lv):
        if lv == 1: return {"1st":{"total":2,"remaining":2}}
        if lv == 2: return {"1st":{"total":3,"remaining":3}}
        if lv == 3: return {"1st":{"total":4,"remaining":4},"2nd":{"total":2,"remaining":2}}
        if lv == 4: return {"1st":{"total":4,"remaining":4},"2nd":{"total":3,"remaining":3}}
        if lv == 5: return {"1st":{"total":4,"remaining":4},"2nd":{"total":3,"remaining":3},"3rd":{"total":2,"remaining":2}}  # PHASE 2 added
        if lv == 6: return {"1st":{"total":4,"remaining":4},"2nd":{"total":3,"remaining":3},"3rd":{"total":3,"remaining":3}}  # PHASE 2 added
        if lv == 7: return {"1st":{"total":4,"remaining":4},"2nd":{"total":3,"remaining":3},"3rd":{"total":3,"remaining":3},"4th":{"total":1,"remaining":1}}  # PHASE 2 added
        if lv == 8: return {"1st":{"total":4,"remaining":4},"2nd":{"total":3,"remaining":3},"3rd":{"total":3,"remaining":3},"4th":{"total":2,"remaining":2}}  # PHASE 2 added
        return {"1st":{"total":4,"remaining":4},"2nd":{"total":3,"remaining":3},"3rd":{"total":3,"remaining":3},"4th":{"total":3,"remaining":3},"5th":{"total":1,"remaining":1}}  # PHASE 2 added (levels 9-10)

    if cls == "Wizard":
        return {"ability":"INT","spell_save_dc":8+pb+int_mod,"spell_attack_bonus":pb+int_mod,
                "spell_slots":slots(level),"cantrips_known":["Firebolt","Ray of Frost","Mage Hand"],
                "spells_known":["Magic Missile","Burning Hands","Mage Armor","Shield"]}
    if cls == "Cleric":
        return {"ability":"WIS","spell_save_dc":8+pb+wis_mod,"spell_attack_bonus":pb+wis_mod,
                "spell_slots":slots(level),"cantrips_known":["Sacred Flame","Guidance","Thaumaturgy"],
                "spells_known":["Cure Wounds","Guiding Bolt","Bless","Healing Word"]}
    if cls == "Ranger" and level >= 2:
        return {"ability":"WIS","spell_save_dc":8+pb+wis_mod,"spell_attack_bonus":pb+wis_mod,
                "spell_slots":{"1st":{"total":2,"remaining":2}},"cantrips_known":[],
                "spells_known":["Hunter's Mark","Cure Wounds"]}
    return {"ability":None,"spell_save_dc":0,"spell_attack_bonus":0,"spell_slots":{},"cantrips_known":[],"spells_known":[]}


def _build_class_features(cls, level, pb):
    f = []
    recovery = max(1, (level + 1) // 2)
    if cls == "Fighter":
        f += [
            {"name":"Second Wind","description":"Bonus action: heal 1d10+level HP once per short rest.","uses_max":1,"uses_remaining":1,"recharge_on":"short_rest"},
            {"name":"Fighting Style","description":"Choose one: Defence (+1 AC), Dueling (+2 damage), Archery (+2 ranged attack), Great Weapon Fighting (reroll 1-2 on damage dice).","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
        ]
    elif cls == "Rogue":
        f += [
            {"name":"Sneak Attack","description":"Once per turn, deal +1d6 bonus damage with finesse or ranged weapon if you have advantage or an ally is adjacent to the target.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
            {"name":"Thieves Cant","description":"You know the secret language of the criminal underworld.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
            {"name":"Expertise","description":"Double proficiency bonus on two chosen skills.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
        ]
    elif cls == "Wizard":
        f += [
            {"name":"Arcane Recovery","description":f"Once per day on a short rest, recover spell slots totaling up to {recovery} levels.","uses_max":1,"uses_remaining":1,"recharge_on":"long_rest"},
            {"name":"Ritual Casting","description":"Cast ritual spells in 10 extra minutes without expending a spell slot.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
            {"name":"Spellbook","description":"Your spellbook holds your prepared spells. You may copy new spells into it.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
        ]
    elif cls == "Cleric":
        f += [
            {"name":"Divine Domain","description":"Your chosen domain grants bonus spells always prepared and domain-specific abilities.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
            {"name":"Spellcasting","description":"Cast cleric spells using Wisdom as your spellcasting ability.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
        ]
    elif cls == "Ranger":
        f += [
            {"name":"Favored Enemy","description":"Advantage on Survival checks to track and History checks to recall lore about your chosen enemy type.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
            {"name":"Natural Explorer","description":"Gain exploration benefits in your chosen favored terrain type.","uses_max":0,"uses_remaining":0,"recharge_on":"none"},
        ]
    return f

'''
def _build_skills(cls, background, scores, chosen, race, pb):
    proficient = set(chosen) | set(BACKGROUND_SKILLS.get(background, []))
    if race == "Elf":      proficient.add("Perception")
    if race == "Half-Orc": proficient.add("Intimidation")
    result = {}
    for skill, ability in SKILLS.items():
        ab_mod = ability_modifier(scores[ability])
        prof   = skill in proficient
        total  = ab_mod + (pb if prof else 0)
        #result[skill] = {"ability":ability,"proficient":prof,"expertise":False,"modifier":total}
        result[skill] = {"ability":ability,"proficient":prof,"expertise":False,"modifier":total} #Fix
    return result
'''
# Fix
def _build_skills(cls, background, scores, chosen, race, pb, expertise_choices=None, human_extra_skill=None):
    expertise_choices = expertise_choices or []

    proficient = set(chosen) | set(BACKGROUND_SKILLS.get(background, []))

    if race == "Elf":
        proficient.add("Perception")

    if race == "Half-Orc":
        proficient.add("Intimidation")

    if race == "Human" and human_extra_skill and human_extra_skill in SKILLS:
        proficient.add(human_extra_skill)

    result = {}

    for skill, ability in SKILLS.items():
        ab_mod = ability_modifier(scores[ability])
        prof = skill in proficient
        expertise = skill in expertise_choices and prof

        total = ab_mod

        if prof:
            total += pb

        if expertise:
            total += pb

        result[skill] = {
            "ability": ability,
            "proficient": prof,
            "expertise": expertise,
            "modifier": total
        }

    return result
# Fix End

def _build_saving_throws(cls, scores, pb):
    prof_set = set(CLASS_SAVING_THROWS.get(cls, []))
    result   = {}
    for ab in ABILITIES:
        mod  = ability_modifier(scores[ab])
        prof = ab in prof_set
        result[ab] = {"modifier": mod + (pb if prof else 0), "proficient": prof}
    return result

# Fix
ALIGNMENTS = [
    "Lawful Good", "Neutral Good", "Chaotic Good",
    "Lawful Neutral", "True Neutral", "Chaotic Neutral",
    "Lawful Evil", "Neutral Evil", "Chaotic Evil"
]

WIZARD_CANTRIPS = [
    "Firebolt", "Ray of Frost", "Mage Hand",
    "Prestidigitation", "Minor Illusion", "Shocking Grasp"
]

CLERIC_CANTRIPS = [
    "Sacred Flame", "Guidance", "Thaumaturgy",
    "Spare the Dying", "Toll the Dead", "Light"
]

WIZARD_SPELLS = [
    "Magic Missile", "Burning Hands", "Sleep", "Shield",
    "Mage Armor", "Thunderwave", "Charm Person", "Detect Magic"
]

CLERIC_SPELLS = [
    "Cure Wounds", "Guiding Bolt", "Bless", "Inflict Wounds",
    "Healing Word", "Command", "Sanctuary", "Protection from Evil and Good"
]

FIGHTING_STYLES = ["Defence", "Dueling", "Archery", "Great Weapon Fighting"]
CLERIC_DOMAINS = ["Life", "Light"]
RANGER_FAVORED_ENEMIES = ["undead", "beasts", "humanoids"]
RANGER_FAVORED_TERRAINS = ["dungeon", "forest", "arctic"]

CLERIC_DOMAIN_BONUS_SPELLS = {
    "Life":  ["Bless", "Cure Wounds"],
    "Light": ["Burning Hands", "Faerie Fire"],
}

DWARF_TOOLS = ["Smith's Tools", "Brewer's Supplies", "Mason's Tools"]

ALL_SKILLS = list(SKILLS.keys())


def validate_character_input(data):
    errors = []

    required = ["character_name", "player_name", "class", "race", "background", "alignment", "ability_scores"]
    for key in required:
        if key not in data or data[key] in ("", None):
            errors.append(f"Missing required field: {key}")

    cls = data.get("class")
    race = data.get("race")
    background = data.get("background")
    alignment = data.get("alignment")

    if cls not in HIT_DICE:
        errors.append("Invalid class.")

    if race not in RACE_ASI:
        errors.append("Invalid race.")

    if background not in BACKGROUND_SKILLS:
        errors.append("Invalid background.")

    if alignment not in ALIGNMENTS:
        errors.append("Invalid alignment.")

    scores = data.get("ability_scores", {})
    if set(scores.keys()) != set(ABILITIES):
        errors.append("Ability scores must include STR, DEX, CON, INT, WIS, CHA.")
    else:
        values = sorted([int(scores[ab]) for ab in ABILITIES], reverse=True)
        if values != sorted(STANDARD_ARRAY, reverse=True):
            errors.append("Ability scores must use the standard array exactly: 15, 14, 13, 12, 10, 8.")

    chosen = data.get("chosen_class_skills", [])
    if cls in CLASS_SKILL_OPTIONS:
        allowed = CLASS_SKILL_OPTIONS[cls]["options"]
        required_count = CLASS_SKILL_OPTIONS[cls]["pick"]

        if len(chosen) != required_count:
            errors.append(f"{cls} must choose exactly {required_count} class skills.")

        for skill in chosen:
            if skill not in allowed:
                errors.append(f"{skill} is not valid for {cls}.")

    expertise = data.get("expertise", [])
    if cls == "Rogue":
        if len(expertise) != 2:
            errors.append("Rogue must choose exactly 2 expertise skills.")
    else:
        if expertise:
            errors.append("Only Rogue can choose expertise at level 1.")

    if cls == "Fighter":
        if data.get("fighting_style") not in FIGHTING_STYLES:
            errors.append("Fighter must choose a valid fighting style.")

    if cls == "Cleric":
        if data.get("domain") not in CLERIC_DOMAINS:
            errors.append("Cleric must choose Life or Light domain.")

    if cls == "Ranger":
        if data.get("favored_enemy") not in RANGER_FAVORED_ENEMIES:
            errors.append("Ranger must choose a favored enemy.")
        if data.get("favored_terrain") not in RANGER_FAVORED_TERRAINS:
            errors.append("Ranger must choose a favored terrain.")

    if race == "Human":
        extra_skill = data.get("human_extra_skill", "")
        if not extra_skill or extra_skill not in SKILLS:
            errors.append("Human must choose one extra skill proficiency from the full skill list.")

    if race == "Dwarf":
        dwarf_tool = data.get("dwarf_tool", "")
        if not dwarf_tool or dwarf_tool not in DWARF_TOOLS:
            errors.append("Dwarf must choose a tool proficiency: Smith's Tools, Brewer's Supplies, or Mason's Tools.")

    if cls == "Wizard":
        cantrips = data.get("cantrips_known", [])
        spells = data.get("spells_known", [])
        int_score = int(scores.get("INT", 10))
        prepared_count = max(1, ability_modifier(int_score) + 1)

        if len(cantrips) != 3 or any(c not in WIZARD_CANTRIPS for c in cantrips):
            errors.append("Wizard must choose exactly 3 valid cantrips.")

        if len(spells) != prepared_count or any(s not in WIZARD_SPELLS for s in spells):
            errors.append(f"Wizard must choose exactly {prepared_count} valid prepared spells.")

    if cls == "Cleric":
        cantrips = data.get("cantrips_known", [])
        spells = data.get("spells_known", [])
        wis_score = int(scores.get("WIS", 10))
        prepared_count = max(1, ability_modifier(wis_score) + 1)

        if len(cantrips) != 3 or any(c not in CLERIC_CANTRIPS for c in cantrips):
            errors.append("Cleric must choose exactly 3 valid cantrips.")

        if len(spells) != prepared_count or any(s not in CLERIC_SPELLS for s in spells):
            errors.append(f"Cleric must choose exactly {prepared_count} valid prepared spells.")

    return errors
# Fix Ends


def create_character(data):
    errors = validate_character_input(data)
    if errors:
        return {"success": False, "errors": errors}
    cls        = data["class"]
    race       = data["race"]
    background = data["background"]
    raw        = {ab: int(data["ability_scores"][ab]) for ab in ABILITIES}

    for ab, bonus in RACE_ASI.get(race, {}).items():
        raw[ab] = raw.get(ab, 10) + bonus
    scores = {ab: min(20, max(1, v)) for ab, v in raw.items()}

    level   = 1
    pb      = prof_bonus_for_level(level)
    dex_mod = ability_modifier(scores["DEX"])
    wis_mod = ability_modifier(scores["WIS"])
    con_mod = ability_modifier(scores["CON"])
    hit_die = HIT_DICE[cls]
    max_hp  = max(1, hit_die + con_mod)
    equipment = _build_equipment(cls)
    ac        = _compute_ac(scores, equipment)
    chosen    = data.get("chosen_class_skills", [])

    perc_prof = ("Perception" in chosen or race == "Elf"
                 or "Perception" in BACKGROUND_SKILLS.get(background, [])
                 or (race == "Human" and data.get("human_extra_skill") == "Perception"))
    passive_perc = 10 + wis_mod + (pb if perc_prof else 0)

    human_extra_skill = data.get("human_extra_skill") if race == "Human" else None

    char = {
        "identity": {
            "character_name":       data.get("character_name","Adventurer"),
            "player_name":          data.get("player_name","Player"),
            "class":                cls,
            "race":                 race,
            "background":           background,
            "alignment":            data.get("alignment","True Neutral"),
            "level":                level,
            "xp":                   0,
            "inspiration":          False,
            "prof_bonus":           pb,
            "age":                  data.get("age",""),
            "height":               data.get("height",""),
            "weight":               data.get("weight",""),
            "eyes":                 data.get("eyes",""),
            "skin":                 data.get("skin",""),
            "hair":                 data.get("hair",""),
            "personality_trait":    data.get("personality_trait",""),
            "ideal":                data.get("ideal",""),
            "bond":                 data.get("bond",""),
            "flaw":                 data.get("flaw",""),
            "backstory":            data.get("backstory",""),
            "allies_organisations": data.get("allies_organisations",""),
            "background_feature":   BACKGROUND_FEATURES.get(background,""),
        },
        "ability_scores": {
            ab: {"score": scores[ab], "modifier": ability_modifier(scores[ab])} for ab in ABILITIES
        },
        "combat": {
            "max_hp":             max_hp,
            "current_hp":         max_hp,
            "temp_hp":            0,
            "hit_dice_total":     f"1d{hit_die}",
            "hit_dice_remaining": level,
            "armor_class":        ac,
            "initiative":         dex_mod,
            "speed":              RACE_SPEED.get(race, 30),
            "passive_perception": passive_perc,
            "exhaustion_level":   0,
            "death_saves":        {"successes":0,"failures":0},
            "conditions":         [],
        },
        "saving_throws":  _build_saving_throws(cls, scores, pb),
        "skills":         _build_skills(cls, background, scores, chosen, race, pb, data.get("expertise", []), human_extra_skill),
        "attacks":        _build_attacks(cls, scores, pb),
        "spellcasting":   _build_spellcasting(cls, scores, level, pb),
        "class_features": _build_class_features(cls, level, pb),
        "racial_traits":  RACE_TRAITS.get(race, []),
        "proficiencies": {
            "armor":     ARMOR_PROFICIENCY.get(cls, []),
            "weapons":   WEAPON_PROFICIENCY.get(cls, []),
            "tools":     (["Thieves Tools"] if cls == "Rogue" else []) + ([data.get("dwarf_tool", "")] if race == "Dwarf" and data.get("dwarf_tool") else []),
            "languages": RACE_LANGUAGES.get(race, ["Common"]),
        },
        "equipment":         equipment,
        "currency":          {"pp":0,"gp":15,"sp":0,"cp":0},
        "carrying_capacity": scores["STR"] * 15,
        "current_weight":    round(sum(e["weight"] * e["quantity"] for e in equipment), 1),
        "favored_enemy":     data.get("favored_enemy"),
        "favored_terrain":   data.get("favored_terrain"),
        "domain":            data.get("domain"),
    }

    # Apply chosen cantrips and prepared spells for spellcasters.
    if cls in ("Wizard", "Cleric"):
        char["spellcasting"]["cantrips_known"] = data.get("cantrips_known", [])
        char["spellcasting"]["spells_known"] = data.get("spells_known", [])

    # Cleric domain bonus spells are always prepared — merge into spells_known.
    if cls == "Cleric":
        domain = data.get("domain", "")
        bonus = CLERIC_DOMAIN_BONUS_SPELLS.get(domain, [])
        known = char["spellcasting"]["spells_known"]
        for sp in bonus:
            if sp not in known:
                known.append(sp)
        char["spellcasting"]["spells_known"] = known

    # Apply chosen Fighter style.
    if cls == "Fighter":
        char["fighting_style"] = data.get("fighting_style")

        if char["fighting_style"] == "Defence":
            char["combat"]["armor_class"] += 1

    # Apply Cleric domain.
    if cls == "Cleric":
        char["domain"] = data.get("domain")

    # Apply Ranger choices.
    if cls == "Ranger":
        char["favored_enemy"] = data.get("favored_enemy")
        char["favored_terrain"] = data.get("favored_terrain")
    # Fix end

    _char_file().write_text(json.dumps(char, indent=2))
    return char


def load_character():
    if _char_file().exists():
        try:
            return json.loads(_char_file().read_text())
        except Exception:
            return None
    return None


def save_character(character):
    _char_file().write_text(json.dumps(character, indent=2))


def character_exists():
    char = load_character()
    return bool(char and char.get("identity", {}).get("character_name"))


def reset_for_new_game():
    """Reset character to level-1 starting state for a fresh run.
    Preserves identity, ability scores, skills, and chosen spells/cantrips.
    Resets HP, equipment, gold, XP, level, spell slots, and class feature uses."""
    if not character_exists():
        return
    char    = load_character()
    cls     = char["identity"]["class"]
    scores  = {ab: char["ability_scores"][ab]["score"] for ab in ABILITIES}
    pb      = prof_bonus_for_level(1)
    con_mod = ability_modifier(scores["CON"])
    hit_die = HIT_DICE.get(cls, 8)
    max_hp  = max(1, hit_die + con_mod)

    # Identity
    char["identity"]["xp"]         = 0
    char["identity"]["level"]       = 1
    char["identity"]["prof_bonus"]  = pb

    # Combat stats
    char["combat"]["max_hp"]             = max_hp
    char["combat"]["current_hp"]         = max_hp
    char["combat"]["temp_hp"]            = 0
    char["combat"]["hit_dice_remaining"] = 1
    char["combat"]["exhaustion_level"]   = 0
    char["combat"]["conditions"]         = []
    char["combat"]["death_saves"]        = {"successes": 0, "failures": 0}

    # Equipment and gold
    char["equipment"] = _build_equipment(cls)
    char["currency"]  = {"pp": 0, "gp": 15, "sp": 0, "cp": 0}
    char["current_weight"] = round(
        sum(e.get("weight", 0) * e.get("quantity", 1) for e in char["equipment"]), 1
    )

    # Spell slots: restore to full (keep cantrips/spells_known from character creation)
    fresh_sc = _build_spellcasting(cls, scores, 1, pb)
    sc = char.get("spellcasting", {})
    sc["spell_slots"] = fresh_sc.get("spell_slots", {})
    char["spellcasting"] = sc

    # Class features: restore uses_remaining
    fresh_feats = {f["name"]: f for f in _build_class_features(cls, 1, pb)}
    for feat in char.get("class_features", []):
        if feat["name"] in fresh_feats and feat.get("uses_max", 0) > 0:
            feat["uses_remaining"] = fresh_feats[feat["name"]]["uses_max"]

    # Racial traits: restore limited-use traits
    for trait in char.get("racial_traits", []):
        if "uses_max" in trait:
            trait["uses_remaining"] = trait.get("uses_max", 1)

    save_character(char)


def get_sheet_summary(char):
    i  = char["identity"]
    c  = char["combat"]
    ab = char["ability_scores"]
    sp = char.get("spellcasting", {})
    slots_str = ""
    if sp.get("spell_slots"):
        parts = [f"{k}: {v['remaining']}/{v['total']}" for k, v in sp["spell_slots"].items()]
        slots_str = " | Slots: " + ", ".join(parts)
    return (
        f"Character: {i['character_name']} ({i['race']} {i['class']}, Level {i['level']}, {i['background']}) | "
        f"XP: {i['xp']} | Prof Bonus: +{i['prof_bonus']} | "
        f"HP: {c['current_hp']}/{c['max_hp']} | AC: {c['armor_class']} | "
        f"Initiative: {c['initiative']:+d} | Speed: {c['speed']}ft | "
        f"STR {ab['STR']['score']}({ab['STR']['modifier']:+d}) "
        f"DEX {ab['DEX']['score']}({ab['DEX']['modifier']:+d}) "
        f"CON {ab['CON']['score']}({ab['CON']['modifier']:+d}) "
        f"INT {ab['INT']['score']}({ab['INT']['modifier']:+d}) "
        f"WIS {ab['WIS']['score']}({ab['WIS']['modifier']:+d}) "
        f"CHA {ab['CHA']['score']}({ab['CHA']['modifier']:+d})"
        f"{slots_str}"
    )


def award_xp(amount, reason="", player_id="player"):
    char = load_character()
    if not char:
        return {"error": "No character found."}

    old_xp    = char["identity"]["xp"]
    new_xp    = old_xp + amount
    old_level = char["identity"]["level"]
    new_level = level_from_xp(new_xp)
    leveled_up   = new_level > old_level
    new_features = []

    char["identity"]["xp"]        = new_xp
    char["identity"]["level"]      = new_level
    new_pb = prof_bonus_for_level(new_level)
    char["identity"]["prof_bonus"] = new_pb

    if leveled_up:
        cls     = char["identity"]["class"]
        scores  = {ab: char["ability_scores"][ab]["score"] for ab in ABILITIES}
        con_mod = ability_modifier(scores["CON"])
        hit_die = HIT_DICE[cls]
        hp_gain = max(1, random.randint(1, hit_die) + con_mod)
        char["combat"]["max_hp"]            += hp_gain
        char["combat"]["current_hp"]         = min(char["combat"]["current_hp"] + hp_gain, char["combat"]["max_hp"])
        char["combat"]["hit_dice_remaining"] = new_level
        new_features.append(f"Level {new_level} reached! +{hp_gain} max HP.")

        sp    = char.get("spellcasting", {})
        slots = sp.get("spell_slots", {})

        if cls in ("Wizard", "Cleric"):
            if new_level == 2 and "1st" in slots:
                gain = 3 - slots["1st"]["total"]
                slots["1st"]["total"] = 3
                slots["1st"]["remaining"] = min(slots["1st"]["remaining"] + gain, 3)
                new_features.append("Spell slots: 3 × 1st-level")
            elif new_level == 3:
                slots["1st"]["total"] = 4
                if "2nd" not in slots:
                    slots["2nd"] = {"total": 2, "remaining": 2}
                    new_features.append("Unlocked: 2nd-level spell slots (2 × 2nd)")
            elif new_level == 4:
                if "2nd" in slots and slots["2nd"]["total"] < 3:
                    gain = 3 - slots["2nd"]["total"]
                    slots["2nd"]["total"] = 3
                    slots["2nd"]["remaining"] = min(slots["2nd"]["remaining"] + gain, 3)
                    new_features.append("Spell slots: 3 × 2nd-level")
                elif "2nd" not in slots:
                    slots["2nd"] = {"total": 3, "remaining": 3}
                    new_features.append("Unlocked: 3 × 2nd-level spell slots")
            elif new_level == 5:  # PHASE 2 added
                if "3rd" not in slots:
                    slots["3rd"] = {"total": 2, "remaining": 2}
                    new_features.append("Unlocked: 3rd-level spell slots (2 × 3rd)")
            elif new_level == 6:  # PHASE 2 added
                if "3rd" in slots and slots["3rd"]["total"] < 3:
                    gain = 3 - slots["3rd"]["total"]
                    slots["3rd"]["total"] = 3
                    slots["3rd"]["remaining"] = min(slots["3rd"]["remaining"] + gain, 3)
                    new_features.append("Spell slots: 3 × 3rd-level")
                elif "3rd" not in slots:
                    slots["3rd"] = {"total": 3, "remaining": 3}
                    new_features.append("Unlocked: 3 × 3rd-level spell slots")
            elif new_level == 7:  # PHASE 2 added
                if "4th" not in slots:
                    slots["4th"] = {"total": 1, "remaining": 1}
                    new_features.append("Unlocked: 4th-level spell slots (1 × 4th)")
            elif new_level == 8:  # PHASE 2 added
                if "4th" in slots and slots["4th"]["total"] < 2:
                    gain = 2 - slots["4th"]["total"]
                    slots["4th"]["total"] = 2
                    slots["4th"]["remaining"] = min(slots["4th"]["remaining"] + gain, 2)
                    new_features.append("Spell slots: 2 × 4th-level")
            elif new_level == 9:  # PHASE 2 added
                if "4th" in slots and slots["4th"]["total"] < 3:
                    gain = 3 - slots["4th"]["total"]
                    slots["4th"]["total"] = 3
                    slots["4th"]["remaining"] = min(slots["4th"]["remaining"] + gain, 3)
                    new_features.append("Spell slots: 3 × 4th-level")
                if "5th" not in slots:
                    slots["5th"] = {"total": 1, "remaining": 1}
                    new_features.append("Unlocked: 5th-level spell slots (1 × 5th)")
            elif new_level == 10:  # PHASE 2 added
                if "5th" in slots and slots["5th"]["total"] < 2:
                    gain = 2 - slots["5th"]["total"]
                    slots["5th"]["total"] = 2
                    slots["5th"]["remaining"] = min(slots["5th"]["remaining"] + gain, 2)
                    new_features.append("Spell slots: 2 × 5th-level")
            sp["spell_slots"] = slots
            char["spellcasting"] = sp

        if cls == "Ranger":
            if new_level == 2 and "1st" not in slots:
                slots["1st"] = {"total": 2, "remaining": 2}
                sp["spell_slots"] = slots
                char["spellcasting"] = sp
                new_features.append("Unlocked: 2 × 1st-level spell slots")
            elif new_level == 3 and "1st" in slots and slots["1st"]["total"] < 3:
                gain = 3 - slots["1st"]["total"]
                slots["1st"]["total"] = 3
                slots["1st"]["remaining"] = min(slots["1st"]["remaining"] + gain, 3)
                sp["spell_slots"] = slots
                char["spellcasting"] = sp
                new_features.append("Spell slots: 3 × 1st-level")
            elif new_level == 5 and "2nd" not in slots:  # PHASE 2 added
                slots["2nd"] = {"total": 2, "remaining": 2}
                sp["spell_slots"] = slots
                char["spellcasting"] = sp
                new_features.append("Unlocked: 2nd-level spell slots (2 × 2nd)")
            elif new_level == 7 and "2nd" in slots and slots["2nd"]["total"] < 3:  # PHASE 2 added
                gain = 3 - slots["2nd"]["total"]
                slots["2nd"]["total"] = 3
                slots["2nd"]["remaining"] = min(slots["2nd"]["remaining"] + gain, 3)
                sp["spell_slots"] = slots
                char["spellcasting"] = sp
                new_features.append("Spell slots: 3 × 2nd-level")
            elif new_level == 9 and "3rd" not in slots:  # PHASE 2 added
                slots["3rd"] = {"total": 1, "remaining": 1}
                sp["spell_slots"] = slots
                char["spellcasting"] = sp
                new_features.append("Unlocked: 3rd-level spell slots (1 × 3rd)")

        existing = {f["name"] for f in char.get("class_features", [])}

        if new_level == 2:
            if cls == "Fighter" and "Action Surge" not in existing:
                char["class_features"].append({"name": "Action Surge", "description": "Take one additional action this turn.", "uses_max": 1, "uses_remaining": 1, "recharge_on": "short_rest"})
                new_features.append("Unlocked: Action Surge")
            elif cls == "Rogue" and "Cunning Action" not in existing:
                char["class_features"].append({"name": "Cunning Action", "description": "Bonus action to Dash, Disengage, or Hide.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Cunning Action")
            elif cls == "Cleric" and "Channel Divinity" not in existing:
                char["class_features"].append({"name": "Channel Divinity", "description": "Channel divine energy for your domain effect.", "uses_max": 1, "uses_remaining": 1, "recharge_on": "short_rest"})
                new_features.append("Unlocked: Channel Divinity")
            elif cls == "Wizard" and "Arcane Tradition" not in existing:
                char["class_features"].append({"name": "Arcane Tradition", "description": "You commit to a school of magic. Your chosen tradition grants features at levels 2, 6, and 10.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Arcane Tradition")
            elif cls == "Ranger" and "Ranger Fighting Style" not in existing:
                char["class_features"].append({"name": "Ranger Fighting Style", "description": "Adopt a fighting style specialisation: Archery, Defense, or Dueling.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Ranger Fighting Style")

        elif new_level == 3:
            if cls == "Rogue" and "Uncanny Dodge" not in existing:
                char["class_features"].append({"name": "Uncanny Dodge", "description": "Use your reaction to halve one attack's damage against you.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Uncanny Dodge")
            elif cls == "Ranger" and "Primeval Awareness" not in existing:
                char["class_features"].append({"name": "Primeval Awareness", "description": "Expend a spell slot to sense favored enemies within 1 mile.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Primeval Awareness")
            elif cls == "Fighter" and "Improved Critical" not in existing:
                char["class_features"].append({"name": "Improved Critical", "description": "Your weapon attacks score a critical hit on a roll of 19 or 20.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Improved Critical")

        elif new_level == 4:
            if "Ability Score Improvement" not in existing:
                char["class_features"].append({"name": "Ability Score Improvement", "description": "Increase one ability score by 2, or two scores by 1 each (max 20).", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Ability Score Improvement")

        elif new_level == 5:  # PHASE 2 added
            if cls in ("Fighter", "Ranger") and "Extra Attack" not in existing:
                char["class_features"].append({"name": "Extra Attack", "description": "You can attack twice whenever you take the Attack action.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Extra Attack")
            if cls == "Cleric" and "Destroy Undead" not in existing:
                char["class_features"].append({"name": "Destroy Undead", "description": "Undead that fail their saving throw against Turn Undead are instantly destroyed if their CR is 1/2 or lower.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Destroy Undead")

        elif new_level == 6:  # PHASE 2 added
            if "Ability Score Improvement (6)" not in existing:
                char["class_features"].append({"name": "Ability Score Improvement (6)", "description": "Increase one ability score by 2, or two scores by 1 each (max 20).", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Ability Score Improvement (Level 6)")

        elif new_level == 7:  # PHASE 2 added
            if cls == "Rogue" and "Evasion" not in existing:
                char["class_features"].append({"name": "Evasion", "description": "When subjected to DEX save for half damage: success = no damage, failure = half damage.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Evasion")
            elif cls == "Fighter":
                surge = next((f for f in char.get("class_features", []) if f["name"] == "Action Surge"), None)
                if surge and surge.get("uses_max", 0) < 2:
                    surge["uses_max"] = 2
                    surge["uses_remaining"] = min(surge.get("uses_remaining", 1) + 1, 2)
                    surge["description"] = "Take one additional action this turn. (2 uses per short rest.)"
                    new_features.append("Action Surge: now 2 uses per short rest")

        elif new_level == 8:  # PHASE 2 added
            if "Ability Score Improvement (8)" not in existing:
                char["class_features"].append({"name": "Ability Score Improvement (8)", "description": "Increase one ability score by 2, or two scores by 1 each (max 20).", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                new_features.append("Unlocked: Ability Score Improvement (Level 8)")

        elif new_level == 10:  # PHASE 2 added
            if "Capstone Resilience" not in existing:
                char["class_features"].append({"name": "Capstone Resilience", "description": "+1 to all saving throws. You have proven yourself worthy in the deepest halls of Ironwood Dungeon.", "uses_max": 0, "uses_remaining": 0, "recharge_on": "none"})
                for ab_key in char.get("saving_throws", {}):
                    char["saving_throws"][ab_key]["modifier"] += 1
                new_features.append("Unlocked: Capstone Resilience (+1 all saving throws)")

        if new_pb != prof_bonus_for_level(old_level):
            char["saving_throws"] = _build_saving_throws(cls, scores, new_pb)
            char["skills"] = _build_skills(
                cls, char["identity"]["background"], scores,
                [s for s, v in char.get("skills", {}).items() if v.get("proficient")],
                char["identity"]["race"], new_pb,
                [s for s, v in char.get("skills", {}).items() if v.get("expertise")]
            )
            char["attacks"] = _build_attacks(cls, scores, new_pb)
            sp = char.get("spellcasting", {})
            if sp.get("ability"):
                ab_key = sp["ability"]
                ab_mod = ability_modifier(scores[ab_key])
                sp["spell_save_dc"] = 8 + new_pb + ab_mod
                sp["spell_attack_bonus"] = new_pb + ab_mod
                char["spellcasting"] = sp
            perc_prof = char.get("skills", {}).get("Perception", {}).get("proficient", False)
            wis_mod = ability_modifier(scores["WIS"])
            char["combat"]["passive_perception"] = 10 + wis_mod + (new_pb if perc_prof else 0)

    thresholds = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000}  # PHASE 2 added
    next_threshold = thresholds.get(new_level + 1)

    _char_file().write_text(json.dumps(char, indent=2))
    return {
        "xp_gained": amount,
        "new_total": new_xp,
        "leveled_up": leveled_up,
        "new_level": new_level,
        "new_features": new_features,
        "xp_to_next": next_threshold,
        "reason": reason
    }


def take_short_rest(hit_dice_to_spend=1, player_id="player"):
    char = load_character()
    cls = char["identity"]["class"]
    scores = {ab: char["ability_scores"][ab]["score"] for ab in ABILITIES}
    con_mod = ability_modifier(scores["CON"])
    hit_die = HIT_DICE[cls]

    dice_available = char["combat"]["hit_dice_remaining"]
    dice_to_spend = min(hit_dice_to_spend, dice_available)
    total_heal = 0

    for _ in range(dice_to_spend):
        roll = random.randint(1, hit_die)
        total_heal += max(1, roll + con_mod)

    old_hp = char["combat"]["current_hp"]
    char["combat"]["current_hp"] = min(char["combat"]["max_hp"], old_hp + total_heal)
    char["combat"]["hit_dice_remaining"] = max(0, dice_available - dice_to_spend)

    recharged = []
    for f in char.get("class_features", []):
        if f.get("recharge_on") == "short_rest" and f.get("uses_remaining", 0) < f.get("uses_max", 0):
            f["uses_remaining"] = f["uses_max"]
            recharged.append(f["name"])

    if cls == "Wizard":
        for f in char.get("class_features", []):
            if f["name"] == "Arcane Recovery" and f.get("uses_remaining", 0) > 0:
                level = char["identity"]["level"]
                recovery_total = max(1, (level + 1) // 2)
                sp = char.get("spellcasting", {})
                slots = sp.get("spell_slots", {})
                recovered = 0
                for sk in ["1st", "2nd", "3rd", "4th", "5th"]:  # PHASE 2 added 3rd-5th
                    if sk in slots and isinstance(slots[sk], dict):
                        missing = slots[sk]["total"] - slots[sk]["remaining"]
                        gain = min(missing, recovery_total - recovered)
                        slots[sk]["remaining"] += gain
                        recovered += gain
                        if recovered >= recovery_total:
                            break
                sp["spell_slots"] = slots
                char["spellcasting"] = sp
                f["uses_remaining"] = 0
                if recovered:
                    recharged.append(f"Arcane Recovery ({recovered} slot levels)")
                break

    _char_file().write_text(json.dumps(char, indent=2))
    return {
        "hp_before": old_hp, "hp_gained": char["combat"]["current_hp"] - old_hp,
        "hp_after": char["combat"]["current_hp"], "hit_dice_spent": dice_to_spend,
        "hit_dice_remaining": char["combat"]["hit_dice_remaining"],
        "features_recharged": recharged
    }


def take_long_rest(player_id="player"):
    char = load_character()
    old_hp = char["combat"]["current_hp"]

    char["combat"]["current_hp"] = char["combat"]["max_hp"]
    char["combat"]["hit_dice_remaining"] = char["identity"]["level"]
    char["combat"]["death_saves"] = {"successes": 0, "failures": 0}
    char["combat"]["conditions"] = []
    exh = char["combat"].get("exhaustion_level", 0)
    if exh > 0:
        char["combat"]["exhaustion_level"] = exh - 1

    slots_restored = {}
    sp = char.get("spellcasting", {})
    for sk, slot in sp.get("spell_slots", {}).items():
        if isinstance(slot, dict):
            gained = slot["total"] - slot["remaining"]
            slot["remaining"] = slot["total"]
            if gained:
                slots_restored[sk] = gained
    char["spellcasting"] = sp

    recharged = []
    for f in char.get("class_features", []):
        if f.get("recharge_on") in ("short_rest", "long_rest") and f.get("uses_remaining", 0) < f.get("uses_max", 0):
            f["uses_remaining"] = f["uses_max"]
            recharged.append(f["name"])
        if f["name"] == "Arcane Recovery":
            f["uses_remaining"] = f.get("uses_max", 1)

    # Recharge racial traits that recover on a long rest (e.g. Half-Orc Relentless Endurance).
    for t in char.get("racial_traits", []):
        if t.get("recharge_on") == "long_rest" and t.get("uses_remaining", 0) < t.get("uses_max", 0):
            t["uses_remaining"] = t["uses_max"]
            recharged.append(t["name"])

    _char_file().write_text(json.dumps(char, indent=2))
    return {
        "hp_before": old_hp, "hp_after": char["combat"]["max_hp"],
        "slots_restored": slots_restored, "features_recharged": recharged
    }


def equip_item(item_id, equip):
    char = load_character()
    if not char:
        return {"error": "No character found."}
    equipment = char.get("equipment", [])
    target = next((e for e in equipment if e.get("item_id") == item_id), None)
    if not target:
        return {"error": "Item not in inventory."}
    item_type = target.get("type") or ITEM_CATALOG.get(item_id, {}).get("type", "")
    if item_type in NON_EQUIPPABLE_TYPES:
        return {"error": f"{target['name']} cannot be equipped."}
    if equip and item_id == "chain_mail":
        str_score = char["ability_scores"]["STR"]["score"]
        if str_score < 13:
            return {"error": f"Chain Mail requires STR 13. Your STR is {str_score}."}
    target["equipped"] = equip
    scores = {ab: char["ability_scores"][ab]["score"] for ab in ABILITIES}
    char["combat"]["armor_class"] = _compute_ac(scores, equipment)
    char["equipment"] = equipment
    _char_file().write_text(json.dumps(char, indent=2))
    return {"success": True, "item_id": item_id, "equipped": equip, "new_ac": char["combat"]["armor_class"]}


def add_item_to_equipment(item_id, qty=1):
    char = load_character()
    if not char:
        return False
    cat = ITEM_CATALOG.get(item_id)
    if not cat:
        return False
    equipment = char.get("equipment", [])
    existing = next((e for e in equipment if e.get("item_id") == item_id), None)
    if existing:
        existing["quantity"] = existing.get("quantity", 1) + qty
    else:
        equipment.append({"item_id":item_id,"name":cat["name"],"weight":cat.get("weight",0),
                          "type":cat.get("type",""),"description":cat.get("description",""),
                          "equipped":False,"quantity":qty})
    char["equipment"] = equipment
    _char_file().write_text(json.dumps(char, indent=2))
    return True


def buy_item(item_id, floor_num):
    char = load_character()
    if not char:
        return {"error": "No character found."}
    cat = ITEM_CATALOG.get(item_id)
    if not cat:
        return {"error": "Unknown item."}
    if item_id not in SHOP_BY_FLOOR.get(floor_num, []):
        return {"error": "Item not available in this shop."}
    cost = cat["cost"]
    gp   = char.get("currency", {}).get("gp", 0)
    if gp < cost:
        return {"error": f"Not enough gold. Need {cost} gp, have {gp} gp."}
    char["currency"]["gp"] -= cost
    equipment = char.get("equipment", [])
    existing = next((e for e in equipment if e.get("item_id") == item_id), None)
    if existing:
        existing["quantity"] = existing.get("quantity", 1) + 1
    else:
        equipment.append({"item_id":item_id,"name":cat["name"],"weight":cat.get("weight",0),
                          "type":cat.get("type",""),"description":cat.get("description",""),
                          "equipped":False,"quantity":1})
    char["equipment"] = equipment
    _char_file().write_text(json.dumps(char, indent=2))
    return {"success": True, "item_id": item_id, "name": cat["name"], "cost": cost,
            "gold_remaining": char["currency"]["gp"]}


def get_class_skill_options():
    return {cls: {"pick": v["pick"], "options": v["options"]} for cls, v in CLASS_SKILL_OPTIONS.items()}


# PHASE 5 added — encumbrance helpers
def get_carry_weight(char):
    """Sum of weight * quantity for all equipment."""
    return round(sum(e.get("weight", 0) * e.get("quantity", 1) for e in char.get("equipment", [])), 1)


def get_carry_capacity(char):
    """D&D 5e: carrying capacity = STR score × 15."""
    str_score = char.get("ability_scores", {}).get("STR", {})
    if isinstance(str_score, dict):
        str_score = str_score.get("score", 10)
    return int(str_score) * 15


def is_encumbered(char):
    """Character is encumbered when carrying more than 67 % of capacity."""
    weight   = get_carry_weight(char)
    capacity = get_carry_capacity(char)
    return capacity > 0 and weight > capacity * 0.67
