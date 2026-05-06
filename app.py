import json, time, threading, os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, after_this_request
from flask_socketio import SocketIO, emit, join_room as sio_join
from openai import OpenAI

load_dotenv()  # loads .env locally; HF Spaces injects secrets as real env vars
import rpg_engine as engine
import character_manager as chars
import combat_manager as combat
import spell_manager as spells
import dungeon_generator as dungeon
import multiplayer_manager as mp
import save_manager as saves
import npc_manager as npcm
import party_inventory_manager as party_inv

app            = Flask(__name__)
# app.secret_key = "ironwood-dungeon-secret-key-2025"  # old hardcoded key
app.secret_key = os.environ.get("SECRET_KEY", "ironwood-dungeon-secret-key-2025")
socketio       = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
client         = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    # api_key="nvapi-..."  # old hardcoded key — now read from environment
    api_key=os.environ["NVIDIA_API_KEY"],
)

SYSTEM_PROMPT = """\
You are the Game Master of IRONWOOD DUNGEON, an atmospheric D&D-style dungeon crawl.

THE DUNGEON - 4 floors, each guarded by a unique enemy:
  Floor 1: Dungeon Troll   -- savage, primal, all muscle and fury
  Floor 2: Shadow Wraith   -- cold, cunning, drains hope as much as HP
  Floor 3: Stone Golem     -- ancient, patient, unstoppable but slow
  Floor 4: Bone Dragon     -- the final terror; ancient, contemptuous, enormous

MULTI-ROOM MAP - Each floor has 5 rooms of these types:
  Entrance  -- arrival point, no threats
  Combat    -- minor enemy guards the room; must be cleared to safely pass
  Trap      -- mechanical hazard (spike/fire/poison); server already resolved save + damage
  Treasure  -- loot chest; already awarded on entry
  Rest      -- safe campfire or shrine; player may take a short rest here
  Puzzle    -- riddle on a stone tablet; server checks the answer
  Boss      -- floor guardian; defeating it unlocks the next floor

When you receive [MOVE_TO_ROOM] the full_room JSON contains the room's description_seed,
type, cleared status, and exits. Use description_seed as the atmosphere seed for your narration.
For Trap rooms narrate the trap_result exactly (save roll, damage taken).
For Puzzle rooms display the puzzle_text verbatim as an in-world inscription.
For Rest rooms tell the player they may take a short rest here.
For Combat/Boss rooms, if cleared is false, describe the enemy rising to fight. If cleared is true, describe remnants of the past battle — the room is safe, no enemy.

PLAYER APPROACHES (resolved before your turn -- narrate the result faithfully):
  FIGHT:  Standard combat. Player attacks; use use_item() with a weapon.
  SNEAK:  Dice roll already resolved in [SNEAK ATTEMPT] context. Narrate that outcome.
  PARLEY: Dice roll already resolved in [PARLEY ATTEMPT] context. Narrate that outcome.

After an enemy is defeated: suggest search_room() for loot and next_floor() to descend.
Clearing Floor 4 ends the game with a victory.

GROUNDING CONTRACT (NEVER VIOLATE):
  You are the Dungeon Master. You CANNOT invent dice results, HP values, AC values,
  spell slots, inventory items, XP awards, room contents, NPC dialogue not in their
  registry, or condition effects. You MUST call the appropriate tool to read world
  state before describing it. If a tool result contradicts your expectation, narrate
  the tool result faithfully. All mechanical outcomes have already been determined
  by the game engine before you receive this message. Your job is narration only.

IRONCLAD RULES -- violating these is a critical failure:
  1. Call get_inventory() before referencing, describing, or using ANY item.
  2. Narrate ONLY numbers returned by tools or present in the game state context.
  3. Do NOT take actions the player did not request. Never attack on the opening scene.
  4. Always end every turn with exactly one call to game_response(). Never skip it.
  5. Keep current_hp equal to the player HP shown in game state or returned by tools.
  6. NPC dialogue must come only from talk_to_npc() or persuade_npc() tool results.
     Never fabricate NPC speech that is not in their dialogue_tree registry.
  7. Room contents (traps, loot, enemies, puzzles) are established by server tools.
     You may not invent room features, items, or encounters not in the tool result.

NARRATIVE TONE:
  Epic, immersive, second-person present tense. Think skilled D&D dungeon master.
  Describe the environment. Give enemies presence and menace. Make choices feel weighted.
  3 to 5 sentences per turn. Vivid but not verbose.

When a room's JSON contains a "lore_note" field, weave it naturally into your narration as
an inscription, carving, or discovered fragment — do not read it aloud verbatim, flavour it.

INSPIRATION: You may call award_inspiration() when the player does something exceptionally
creative, courageous, or deeply in-character — a moment that deserves recognition beyond XP.
Inspiration does not stack. When the player asks to use it, call use_inspiration() and narrate
their surge of resolve granting advantage on the stated roll. Never award it for routine actions.

ATMOSPHERE: Ironwood Dungeon is ancient, merciless, and alive with dread. Describe stone that
remembers, shadows that move with intent, and silences that have weight. Each floor deeper feels
more oppressive. Rewards feel genuinely earned against genuine danger.

PACING: Routine turns (movement, short rest, search) should resolve in under 120 words. Reserve
longer prose for first encounters, boss reveals, kills, and floor transitions. Never pad quiet
moments with repetitive description.

CONSISTENCY: Never contradict numbers or outcomes already returned by Python tools this turn. If
a tool reports 14 damage dealt, narrate exactly 14. If a save was failed, narrate failure. You
cannot retcon mechanical results — they are already resolved before you narrate.

PLAYER AGENCY: After every non-combat turn, imply 2–3 natural next possibilities through the
environment (sounds, smells, distant light) rather than listing menu options. Choices should feel
weighted and meaningful, not arbitrary.

FLOOR ATMOSPHERE: Each room in the dungeon carries an atmosphere_text field with sensory details
unique to that floor's environment. When present in the full_room JSON, weave it naturally into
your narration as environmental colour. Do not quote it verbatim — let it shade the scene.

FLOOR THEMES (for narration reference):
  Floor 1 — Stone Depths (warm amber-grey): ancient hewn corridors, mineral seepage, cold chisel-work.
  Floor 2 — Flooded Crypts (cold steel-blue): standing black water, drowned stone, eerie stillness.
    On floor 2, fire spells deal reduced damage — standing water smothers the flame.
  Floor 3 — Ancient Library (deep violet): collapsed shelves, rotting vellum, dust of dead knowledge.
  Floor 4 — Dragon's Lair (ember red): heat haze, scorched stone, sulphur on every breath.

SURFACE HUB — IRONWOOD VILLAGE: When on_surface is True in game state, the player stands in
Ironwood Village above the dungeon — a moment of relative safety between descents. Five locations:
  ironwood_inn     — Innkeeper Mira; call rest_at_inn() when player agrees to pay 5 gold to rest.
  village_market   — Supplies and sundries; describe wares, no mechanical shop currently active.
  notice_board     — Bounties, warnings, dungeon lore; weave in flavour from LORE_NOTES.
  ruined_shrine    — One-time spell slot restore; call pray_at_shrine() when player prays.
  dungeon_entrance — The iron gate; call descend_to_dungeon() when player chooses to enter.
Narrate the village as warm, lived-in, and quietly tense — shadows of the dungeon below hang over
every conversation. Do not spawn enemies or hazards in the village.
"""

ENDINGS = {
    "warrior":   {
        "title": "CONQUEROR OF IRON",
        "subtitle": "The Warrior's Path",
        "text": "Every corridor ran red with your fury. Every creature broke against your will. The dungeon did not test you -- it failed you. They will carve your name into stone, and the stone will remember long after men forget."
    },
    "shadow":    {
        "title": "THE UNSEEN BLADE",
        "subtitle": "The Shadow's Path",
        "text": "You moved through the dungeon like a rumour. The creatures are still waiting for an enemy that was never truly there. Legends will speak of a shadow that walked these halls -- and no one will know if you were real."
    },
    "kingmaker": {
        "title": "VOICE OF THE DEEP",
        "subtitle": "The Diplomat's Path",
        "text": "Words are the oldest magic. You turned enemies into reluctant allies, and fear into negotiation. You leave not as a conqueror but as something rarer and more dangerous: a ruler who never had to draw a blade."
    },
    "survivor":  {
        "title": "WANDERER OF IRON",
        "subtitle": "The Survivor's Path",
        "text": "You fought when you had to. You fled when you could. You talked when nothing else worked. The dungeon could not predict you -- and that alone is why you stand in the light again."
    },
    "fallen":    {
        "title": "THE DUNGEON CLAIMS",
        "subtitle": "Your Story Ends Here",
        "text": "Your torch dims. Your knees buckle. The stone floor is colder than you expected. Somewhere above, the sun still rises -- but it rises without you. The dungeon remembers every soul it has taken. It will remember yours."
    },
}

def get_or_init_history():
    history = engine.load_history()
    if not history:
        history = [{"role": "system", "content": SYSTEM_PROMPT}]
    return history

def state_to_dict():
    return json.loads(engine._state_file().read_text())

def _xp_state(event):
    xp = event.get("xp_awarded") or {}
    if not xp or not isinstance(xp, dict):
        return {}
    return {
        "xp_gained":   xp.get("xp_gained", 0),
        "xp_total":    xp.get("new_total", 0),
        "xp_to_next":  xp.get("xp_to_next"),
        "level_up":    xp.get("leveled_up", False),
        "new_level":   xp.get("new_level", 1),
        "new_features": xp.get("new_features", []),
    }

def _spell_state():
    try:
        if not chars.character_exists():
            return {"available_spells": [], "spell_slots": {}}
        char = chars.load_character()
        return {
            "available_spells": spells.get_available_spells(char),
            "spell_slots": char.get("spellcasting", {}).get("spell_slots", {})
        }
    except Exception:
        return {"available_spells": [], "spell_slots": {}}

def _dungeon_state():
    try:
        state = json.loads(engine._state_file().read_text())
        floor_num       = state.get("floor", 1)
        current_room_id = state.get("current_room_id", dungeon.get_entrance_room_id(floor_num))
        return {
            "dungeon_map": dungeon.get_map_for_frontend(floor_num, current_room_id),
            "floor_theme": dungeon.get_floor_theme(floor_num),
        }
    except Exception:
        return {"dungeon_map": [], "floor_theme": {}}

def _handle_enemy_defeat(event, room_code="SOLO", player_name="Player"):  # PHASE 4 added params
    try:
        xp = event.get("xp_awarded") or {}
        if not isinstance(xp, dict) or not xp.get("xp_gained"):
            return
        state     = json.loads(engine._state_file().read_text())
        floor_num = state.get("floor", 1)
        room_id   = state.get("current_room_id")
        if not room_id:
            return
        room = dungeon.get_room(floor_num, room_id)
        if not room:
            return
        dungeon.mark_room_cleared(room_id, floor_num)
        is_boss = room["type"] == "Boss"
        loot_dropped = dungeon.roll_enemy_loot(floor_num, is_boss)
        event["loot_dropped"] = loot_dropped
        state["enemies_defeated"] = state.get("enemies_defeated", 0) + 1
        if is_boss:
            state["boss_cleared"] = True
            cleared = state.get("floors_boss_cleared", [])
            if floor_num not in cleared:
                cleared.append(floor_num)
            state["floors_boss_cleared"] = cleared
            engine._state_file().write_text(json.dumps(state, indent=2))
            if floor_num == 4:
                try:
                    char = chars.load_character()
                    char_name = char.get("identity", {}).get("character_name", "Adventurer") if char else "Adventurer"
                except Exception:
                    char_name = "Adventurer"
                socketio.emit("game_complete", {
                    "floor_reached":    4,
                    "turns_taken":      state.get("turn", 0),
                    "enemies_defeated": state.get("enemies_defeated", 0),
                    "character_name":   char_name,
                    "gold":             state.get("gold", 0),
                }, room=room_code)
        else:
            engine._state_file().write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def _room_ctx():
    data        = request.get_json(silent=True, force=True) or {}
    room_code   = (data.get("room_code") or request.headers.get("X-Room-Code", "SOLO")).upper()
    player_name = data.get("player_name") or request.headers.get("X-Player-Name", "Player")
    return room_code, player_name


_room_locks: dict[str, threading.Lock] = {}
_room_locks_guard = threading.Lock()

def _room_lock(room_code: str) -> threading.Lock:
    with _room_locks_guard:
        if room_code not in _room_locks:
            _room_locks[room_code] = threading.Lock()
        return _room_locks[room_code]


def _setup_room(room_code, player_name=""):
    """Point all per-room modules at the right state files for this request's room."""
    engine.set_room_code(room_code)
    combat.set_room_code(room_code)
    dungeon.set_room_code(room_code)
    party_inv.set_room_code(room_code)
    # In multiplayer each player gets their own character file; solo uses character.json
    chars.set_player_name(player_name if room_code != "SOLO" else "")
    if room_code == "SOLO":
        _migrate_solo_files()


def _migrate_solo_files():
    """One-time rename of old flat JSON files to SOLO-prefixed equivalents."""
    base = engine.BASE
    pairs = [
        ("game_state.json",       "game_state_SOLO.json"),
        ("history.json",          "history_SOLO.json"),
        ("dungeon_map.json",      "dungeon_map_SOLO.json"),
        ("party_inventory.json",  "party_inventory_SOLO.json"),
    ]
    for old, new in pairs:
        o, n = base / old, base / new
        if o.exists() and not n.exists():
            o.rename(n)


def _emit_level_up(room_code, player_name, xp_result):
    if not xp_result or not isinstance(xp_result, dict) or not xp_result.get("leveled_up"):
        return
    socketio.emit("level_up_notification", {
        "player_name":  player_name,
        "new_level":    xp_result.get("new_level", 1),
        "new_features": xp_result.get("new_features", []),
        "xp_total":     xp_result.get("new_total", 0),
    }, room=room_code)


def _broadcast(room_code, extra=None):
    try:
        state     = state_to_dict()
        party     = mp.get_party_status(room_code)
        actor     = mp.get_current_actor(room_code)
        payload   = {
            "state":               state,
            "party":               party,
            "active_player_name":  actor.get("player_name") if actor and actor.get("type") == "player" else None,
            "combat":              combat.get_combat_public_state(),
            "narrative":           state.get("last_narrative", ""),
            **_dungeon_state(),
            **(extra or {}),
        }
        socketio.emit("game_state_update", payload, room=room_code)
    except Exception:
        pass


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/api/character/options")
def character_options():
    return jsonify({
        "abilities": chars.ABILITIES,
        "standard_array": chars.STANDARD_ARRAY,
        "classes": list(chars.HIT_DICE.keys()),
        "races": list(chars.RACE_ASI.keys()),
        "backgrounds": list(chars.BACKGROUND_SKILLS.keys()),
        "alignments": chars.ALIGNMENTS,
        "class_skill_options": chars.get_class_skill_options(),
        "background_skills": chars.BACKGROUND_SKILLS,
        "class_descriptions": chars.CLASS_DESCRIPTIONS,
        "race_descriptions": chars.RACE_DESCRIPTIONS,
        "wizard_cantrips": chars.WIZARD_CANTRIPS,
        "cleric_cantrips": chars.CLERIC_CANTRIPS,
        "wizard_spells": chars.WIZARD_SPELLS,
        "cleric_spells": chars.CLERIC_SPELLS,
        "fighting_styles": chars.FIGHTING_STYLES,
        "cleric_domains": chars.CLERIC_DOMAINS,
        "ranger_favored_enemies": chars.RANGER_FAVORED_ENEMIES,
        "ranger_favored_terrains": chars.RANGER_FAVORED_TERRAINS,
        "all_skills": chars.ALL_SKILLS,
        "dwarf_tools": chars.DWARF_TOOLS,
        "cleric_domain_bonus_spells": chars.CLERIC_DOMAIN_BONUS_SPELLS,
    })


@app.route("/api/character")
def get_character():
    char = chars.load_character()
    return jsonify({
        "exists": bool(char),
        "character": char
    })


@app.route("/api/character/create", methods=["POST"])
def create_character():
    data = request.get_json(silent=True, force=True) or {}
    result = chars.create_character(data)

    if isinstance(result, dict) and result.get("success") is False:
        return jsonify(result), 400

    return jsonify({
        "success": True,
        "character": result
    })

@app.route("/api/reset", methods=["POST"])
def reset_game():
    """Delete all runtime state files (game, combat, dungeon, quests, party inventory,
    history, inventory) so the next /api/new starts completely fresh.
    character.json is intentionally preserved so the player keeps their sheet."""
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    import npc_manager as _npc

    files_to_delete = [
        engine._state_file(),
        engine._hist_file(),
        engine.INVENTORY_FILE,
        dungeon._dungeon_file(),
        _npc.QUESTS_FILE,
        party_inv._inv_file(),
    ]
    # combat_state.json is deleted via the manager so its in-memory cache is also cleared
    combat.reset_combat_state()

    deleted = []
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            deleted.append(f.name)

    return jsonify({"success": True, "deleted": deleted})


@app.route("/api/resume")
def resume():
    """Return current game state if a game is in progress, so the page can restore without a new LLM call."""
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    try:
        if not engine._state_file().exists() or not engine._hist_file().exists():
            return jsonify({"active": False})
        state = state_to_dict()
        if state.get("hp", 0) <= 0 or state.get("turn", 1) <= 1:
            return jsonify({"active": False})
        narrative = state.get("last_narrative", "You stand ready to continue your quest.")
        hub_locs = dungeon.generate_surface_hub() if state.get("on_surface") else []
        actions = state.get("last_actions") or []
        if not actions:
            if state.get("on_surface"):
                actions = [
                    "Visit the Ironwood Inn to speak with Mira",
                    "Read the notice board for bounties and lore",
                    "Pray at the ruined shrine for a blessing",
                    "Approach the dungeon entrance and descend into Ironwood Dungeon",
                ]
            else:
                actions = ["Look around carefully", "Search the room", "Check your inventory"]
        return jsonify({
            "active":        True,
            "state":         state,
            "hp":            state["hp"],
            "narrative":     narrative,
            "actions":       actions,
            "hub_locations": hub_locs,
            **_dungeon_state(),
        })
    except Exception:
        return jsonify({"active": False})


@app.route("/api/hub")
def hub_route():
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    state = state_to_dict()
    return jsonify({
        "on_surface":  state.get("on_surface", False),
        "hub_visited": state.get("hub_visited", False),
        "shrine_used": state.get("shrine_used", False),
        "locations":   dungeon.generate_surface_hub(),
    })


@app.route("/api/hub/rest", methods=["POST"])
def hub_inn_rest():
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    result = npcm.rest_at_inn()
    if result.get("success"):
        combat.sync_game_state_from_character()
    s = mp.get_session(room_code)
    if s and s.get("state") == "playing" and len(s.get("players", [])) > 1:
        _broadcast(room_code)
    state = state_to_dict()
    return jsonify({**result, "state": state, "hp": state.get("hp", 0)})


'''
@app.route("/api/new", methods=["POST"])
def new_game():
    if not chars.character_exists():
        return jsonify({"error": "Create a character before starting the dungeon."}), 400
    engine.INVENTORY_FILE.write_text(json.dumps(engine.INITIAL_INVENTORY, indent=2))
    engine.GAME_STATE_FILE.write_text(json.dumps(engine.INITIAL_GAME_STATE, indent=2))
    combat.reset_combat_state()
    combat.sync_game_state_from_character()
    if engine.HISTORY_FILE.exists():
        engine.HISTORY_FILE.unlink()
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    try:
        char = chars.load_character()
        char_summary = chars.get_sheet_summary(char)
        resp = engine.run_turn(
            client, history,
            f"[CHARACTER SHEET SUMMARY: {char_summary}] "
            "SCENE_OPEN: Describe entering the dungeon gate and encountering the first enemy. "
            "Do NOT attack, do NOT deal damage, do NOT change any stats. Scene-setting only."
        )
        engine.save_history(history)
        state = state_to_dict()
        return jsonify({
            "narrative": resp["narrative_text"],
            "hp":        resp["current_hp"],
            "actions":   resp["available_actions"],
            "state":     state,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
'''
@app.route("/api/new", methods=["POST"])
def new_game():
    if not chars.character_exists():
        return jsonify({"error": "Create a character before starting the dungeon."}), 400

    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    s = mp.get_session(room_code)
    _mp_active = s and s.get("state") == "playing" and len(s.get("players", [])) > 1
    if s:
        char = chars.load_character()
        mp.set_character(room_code, player_name, char)

    @after_this_request
    def _mp_new_post(response):
        if _mp_active:
            mp.save_active_character_to_party(room_code, player_name)
            _broadcast(room_code)
        try:
            saves.auto_save(chars.load_character(), state_to_dict(), engine.load_history())
        except Exception:
            pass
        return response

    chars.reset_for_new_game()

    engine._state_file().write_text(json.dumps(engine.INITIAL_GAME_STATE, indent=2))
    party_inv.reset()

    dungeon.generate_all_floors()
    combat.reset_combat_state()
    combat.sync_game_state_from_character()

    if engine._hist_file().exists():
        engine._hist_file().unlink()

    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    try:
        char = chars.load_character()
        char_summary = chars.get_sheet_summary(char)

        resp = engine.run_turn(
            client,
            history,
            f"[CHARACTER SHEET SUMMARY: {char_summary}] "
            "[HUB CONTEXT — on_surface=True] "
            "SCENE_OPEN: The player has just arrived in Ironwood Village, the last outpost before "
            "the dungeon. Describe the village atmosphere: the Ironwood Inn ahead, the smell of "
            "stew and woodsmoke, villagers who know what lies beneath the old iron gate at the "
            "village edge. Mention Mira the innkeeper and the Dungeon Entrance as the key points "
            "of interest. Do NOT spawn enemies, deal damage, or change stats. Scene-setting only."
        )

        engine.save_history(history)
        state = state_to_dict()

        hub_locations = dungeon.generate_surface_hub() if state.get("on_surface") else []
        return jsonify({
            "narrative":     resp["narrative_text"],
            "hp":            state["hp"],
            "actions":       resp["available_actions"],
            "state":         state,
            "combat":        combat.get_combat_public_state(),
            "hub_locations": hub_locations,
            **_dungeon_state(),
            **_spell_state(),
        })

    except Exception as e:
        print("LLM failed during /api/new:", repr(e))
        state = state_to_dict()
        fallback = (
            "The lantern above the Ironwood Inn swings in a cold breeze. The village square is quiet — "
            "a few villagers who know better than to ask questions about the iron gate at the far end of the road. "
            "Mira the innkeeper waves from the doorway. The dungeon can wait."
        )
        state["last_narrative"] = fallback
        engine._state_file().write_text(json.dumps(state, indent=2))
        hub_locations = dungeon.generate_surface_hub() if state.get("on_surface") else []
        return jsonify({
            "narrative":     fallback,
            "hp":            state["hp"],
            "actions":       [],
            "state":         state,
            "combat":        combat.get_combat_public_state(),
            "hub_locations": hub_locations,
            **_dungeon_state(),
        })

@app.route("/api/action", methods=["POST"])
def action():
    data        = request.get_json(silent=True, force=True) or {}
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    message = data.get("message", "").strip()
    choice  = data.get("choice")

    # Multiplayer turn gate + post-action broadcast
    s = mp.get_session(room_code)
    _mp_active = s and s.get("state") == "playing" and len(s.get("players", [])) > 1
    if _mp_active:
        combat_choices = {"fight","sneak","talk","use_item","dodge","dash","help","death_save","disengage","bonus_action"}
        if choice in combat_choices and not mp.is_player_turn(room_code, player_name):
            return jsonify({"error": "It is not your turn."}), 403
        mp.activate_player_character(room_code, player_name)

    @after_this_request
    def _mp_post(response):
        if _mp_active:
            mp.save_active_character_to_party(room_code, player_name)
            is_live = combat.get_combat_public_state().get("active", False)
            if is_live and choice in {"fight","sneak","talk","use_item","dodge","dash","help","disengage","bonus_action"}:
                mp.advance_turn(room_code)
            elif not is_live:
                mp.clear_combat(room_code)
            _broadcast(room_code)
        return response

    history   = get_or_init_history()
    state     = state_to_dict()
    extra     = ""
    dice_roll = None

    if choice == "fight":
        try:
            # Multiplayer: initialise initiative order at the start of a new combat
            if _mp_active and not combat.get_combat_public_state().get("active"):
                _st = state_to_dict()
                _en = _st.get("enemy")
                if _en:
                    mp.init_combat_order(room_code, _en)

            event = combat.resolve_player_attack()

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_COMBAT]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            _handle_enemy_defeat(event, room_code, player_name)  # PHASE 4 updated
            state = state_to_dict()

            xp = event.get("xp_awarded") or {}
            if _mp_active and xp.get("leveled_up"):
                _emit_level_up(room_code, player_name, xp)

            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice": {
                    "roll":    event.get("attack_roll"),
                    "dc":      event.get("enemy_ac"),
                    "success": event.get("hit", False),
                    "type":    "fight",
                } if event.get("attack_roll") is not None else None,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": combat.get_combat_public_state(),
                "loot_dropped": event.get("loot_dropped", []),
                **_xp_state(event),
                **_dungeon_state(),
            }

            if state["hp"] <= 0:
                result["ending"] = {"type": "fallen", **ENDINGS["fallen"]}

            enemy = state.get("enemy")
            if enemy and enemy.get("hp", 0) <= 0:
                result["narrative"] += " The enemy collapses. The room grows still."

            return jsonify(result)

        except Exception as e:
            state = state_to_dict()
            return jsonify({
                "error": f"Combat engine failed: {str(e)}",
                "hp": state.get("hp", 0),
                "state": state
            }), 500

    if choice in ("sneak", "talk"):
        try:
            state = state_to_dict()
            enemy = state.get("enemy")

            if not enemy or enemy.get("hp", 0) <= 0:
                return jsonify({
                    "error": "There is no active enemy for this action.",
                    "hp": state.get("hp", 0),
                    "state": state
                }), 400

            state["choices"].append(choice)
            engine._state_file().write_text(json.dumps(state, indent=2))

            if choice == "sneak":
                event = combat.resolve_sneak_attempt()
                dice_payload = {
                    "roll": event.get("roll"),
                    "dc": event.get("dc"),
                    "success": event.get("success"),
                    "type": "sneak"
                }
            else:
                event = combat.resolve_parley_attempt()
                dice_payload = {
                    "roll": event.get("roll"),
                    "dc": event.get("dc"),
                    "success": event.get("success"),
                    "type": "parley"
                }

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_SKILL_ACTION]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            _handle_enemy_defeat(event, room_code, player_name)  # PHASE 4 updated
            state = state_to_dict()

            xp = event.get("xp_awarded") or {}
            if _mp_active and xp.get("leveled_up"):
                _emit_level_up(room_code, player_name, xp)

            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice": dice_payload,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": event,
                "loot_dropped": event.get("loot_dropped", []),
                **_xp_state(event),
                **_dungeon_state(),
            }

            if state["hp"] <= 0:
                result["ending"] = {"type": "fallen", **ENDINGS["fallen"]}

            enemy = state.get("enemy")
            if enemy and enemy.get("hp", 0) <= 0:
                result["narrative"] += " The room is cleared."

            return jsonify(result)

        except Exception as e:
            state = state_to_dict()
            return jsonify({
                "error": f"Skill action failed: {str(e)}",
                "hp": state.get("hp", 0),
                "state": state
            }), 500

    # PHASE 2 STEP 6: server-authoritative death saving throw.
    if choice == "death_save":
        try:
            event = combat.resolve_death_save()

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_DEATH_SAVE]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice": {
                    "roll": event.get("roll"),
                    "dc": 10,
                    "success": event.get("success", False),
                    "type": "death_save"
                } if event.get("roll") is not None else None,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": combat.get_combat_public_state()
            }

            if event.get("dead"):
                result["ending"] = {"type": "fallen", **ENDINGS["fallen"]}
                # PHASE 4 added — emit game_over for death screen overlay
                try:
                    socketio.emit("game_over", {
                        "floor":            state.get("floor", 1),
                        "turns_taken":      state.get("turn", 0),
                        "enemies_defeated": state.get("enemies_defeated", 0),
                    }, room=room_code)
                except Exception:
                    pass

            return jsonify(result)

        except Exception as e:
            state = state_to_dict()
            return jsonify({
                "error": f"Death save failed: {str(e)}",
                "hp": state.get("hp", 0),
                "state": state,
                "combat": combat.get_combat_public_state()
            }), 500

    if choice in ("dodge", "dash", "help", "disengage", "bonus_action"):
        try:
            state = state_to_dict()
            enemy = state.get("enemy")

            if not enemy or enemy.get("hp", 0) <= 0:
                return jsonify({
                    "error": "There is no active enemy for this combat action.",
                    "hp": state.get("hp", 0),
                    "state": state,
                    "combat": combat.get_combat_public_state()
                }), 400

            event = combat.resolve_player_combat_action(choice)

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_COMBAT_ACTION]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice": None,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": combat.get_combat_public_state()
            }

            if state["hp"] <= 0:
                result["ending"] = {"type": "fallen", **ENDINGS["fallen"]}

            return jsonify(result)

        except Exception as e:
            state = state_to_dict()
            return jsonify({
                "error": f"Combat action failed: {str(e)}",
                "hp": state.get("hp", 0),
                "state": state,
                "combat": combat.get_combat_public_state()
            }), 500

    if choice == "second_wind":
        try:
            event = combat.resolve_second_wind()

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_SECOND_WIND]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            return jsonify({
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": combat.get_combat_public_state()
            })

        except Exception as e:
            state = state_to_dict()
            return jsonify({"error": f"Second Wind failed: {str(e)}", "hp": state.get("hp", 0)}), 500

    if choice == "hunters_mark":
        try:
            event = combat.resolve_hunters_mark_cast()

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_HUNTERS_MARK]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            return jsonify({
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice_rolls": [],
                "combat": combat.get_combat_public_state()
            })

        except Exception as e:
            state = state_to_dict()
            return jsonify({"error": f"Hunter's Mark failed: {str(e)}", "hp": state.get("hp", 0)}), 500

    if choice == "cunning_action":
        try:
            sub = data.get("sub_action", "dash")
            event = combat.resolve_cunning_action(sub)

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_CUNNING_ACTION]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            return jsonify({
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": combat.get_combat_public_state()
            })

        except Exception as e:
            state = state_to_dict()
            return jsonify({"error": f"Cunning Action failed: {str(e)}", "hp": state.get("hp", 0)}), 500

    if choice == "use_item":
        try:
            item_id = data.get("item_id", "")
            if not item_id:
                return jsonify({"error": "No item selected."}), 400
            event = combat.resolve_use_item_combat(item_id)

            if not event.get("success"):
                state = state_to_dict()
                return jsonify({
                    "narrative": event.get("summary", "You couldn't use that item."),
                    "hp": state["hp"],
                    "actions": event.get("available_actions", []),
                    "state": state,
                    "ending": None,
                    "dice_rolls": [],
                    "combat": combat.get_combat_public_state()
                })

            history.append({
                "role": "user",
                "content": "[SERVER_RESOLVED_USE_ITEM]\n" + json.dumps(event, indent=2)
            })

            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)

            state = state_to_dict()

            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state,
                "ending": None,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": combat.get_combat_public_state()
            }

            if state["hp"] <= 0:
                result["ending"] = {"type": "fallen", **ENDINGS["fallen"]}

            return jsonify(result)

        except Exception as e:
            state = state_to_dict()
            return jsonify({"error": f"Use Item failed: {str(e)}", "hp": state.get("hp", 0)}), 500

    if choice == "cast_spell":
        try:
            spell_name = data.get("spell_name", "")
            slot_level = data.get("slot_level")
            event = spells.resolve_cast(spell_name, slot_level)
            _spell_floor = state_to_dict().get("floor", 1)
            event = combat.apply_water_dampening(event, _spell_floor)
            history.append({"role": "user", "content": "[SERVER_RESOLVED_SPELL]\n" + json.dumps(event, indent=2)})
            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)
            state = state_to_dict()
            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": resp.get("available_actions", event.get("available_actions", [])),
                "state": state, "ending": None,
                "dice_rolls": event.get("dice_rolls_this_turn", []),
                "combat": combat.get_combat_public_state()
            }
            result.update(_spell_state())
            if state["hp"] <= 0:
                result["ending"] = {"type": "fallen", **ENDINGS["fallen"]}
            return jsonify(result)
        except Exception as e:
            state = state_to_dict()
            return jsonify({"error": f"Spell failed: {str(e)}", "hp": state.get("hp", 0)}), 500

    if choice == "short_rest":
        try:
            hit_dice = data.get("hit_dice", 1)
            rest = chars.take_short_rest(hit_dice)
            combat.sync_game_state_from_character()
            event = {
                "type": "short_rest",
                "summary": (
                    f"Short rest: spent {rest['hit_dice_spent']} hit dice, recovered {rest['hp_gained']} HP "
                    f"({rest['hp_before']} -> {rest['hp_after']}). "
                    f"Features recharged: {', '.join(rest['features_recharged']) or 'none'}."
                ),
                "dice_rolls_this_turn": [],
                "available_actions": combat.get_available_combat_actions()
            }
            history.append({"role": "user", "content": "[SHORT_REST]\n" + json.dumps(event, indent=2)})
            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)
            state = state_to_dict()
            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": combat.get_available_combat_actions(),
                "state": state, "ending": None, "dice_rolls": [],
                "combat": combat.get_combat_public_state()
            }
            result.update(_spell_state())
            return jsonify(result)
        except Exception as e:
            state = state_to_dict()
            return jsonify({"error": f"Short rest failed: {str(e)}", "hp": state.get("hp", 0)}), 500

    if choice == "long_rest":
        try:
            # PHASE 1 added — enforce once-per-floor limit
            state = state_to_dict()
            if state.get("long_rest_used_this_floor"):
                return jsonify({
                    "error": "Long rest already taken this floor. Only one long rest is allowed per floor. Use Short Rest to spend hit dice instead.",
                    "hp": state.get("hp", 0),
                    "state": state,
                    "available_actions": combat.get_available_combat_actions()
                }), 400

            rest = chars.take_long_rest()
            combat.sync_game_state_from_character()

            # PHASE 1 added — mark long rest as used this floor
            state = state_to_dict()
            state["long_rest_used_this_floor"] = True
            engine._state_file().write_text(json.dumps(state, indent=2))

            event = {
                "type": "long_rest",
                "summary": (
                    f"Long rest: HP fully restored to {rest['hp_after']}. "
                    f"All spell slots and features recovered. All conditions cleared."
                ),
                "dice_rolls_this_turn": [],
                "available_actions": combat.get_available_combat_actions()
            }
            history.append({"role": "user", "content": "[LONG_REST]\n" + json.dumps(event, indent=2)})
            resp = engine.run_resolved_turn(client, history, event)
            engine.save_history(history)
            state = state_to_dict()
            result = {
                "narrative": resp["narrative_text"],
                "hp": state["hp"],
                "actions": combat.get_available_combat_actions(),
                "state": state, "ending": None, "dice_rolls": [],
                "combat": combat.get_combat_public_state()
            }
            result.update(_spell_state())
            return jsonify(result)
        except Exception as e:
            state = state_to_dict()
            return jsonify({"error": f"Long rest failed: {str(e)}", "hp": state.get("hp", 0)}), 500

    if choice in ("fight", "sneak", "talk"):
        enemy = state.get("enemy")
        if enemy and enemy["hp"] > 0:
            state["choices"].append(choice)
            engine._state_file().write_text(json.dumps(state, indent=2))

            if choice == "sneak":
                r     = engine.attempt_sneak()
                extra = f"[SNEAK ATTEMPT -- {r['note']}] "
                dice_roll = {"roll": r["roll"], "dc": r["dc"], "success": r["success"], "type": "sneak"}
                if not message:
                    message = "I try to slip past the enemy unseen."
            elif choice == "talk":
                r     = engine.attempt_talk()
                extra = f"[PARLEY ATTEMPT -- {r['note']}] "
                if r.get("roll") is not None:
                    dice_roll = {"roll": r["roll"], "dc": r["dc"], "success": r["success"], "type": "parley"}
                if not message:
                    message = "I step forward and attempt to negotiate."
            elif choice == "fight":
                extra = "[Player chose FIGHT -- standard combat begins.] "
                if not message:
                    message = "I ready my weapon and charge."

    if not message:
        return jsonify({"error": "No action provided."}), 400

    full_input = (extra + message).strip()

    # Surface hub context injection — tells the LLM where the player is and what tools apply
    _hub_state = state_to_dict()
    if _hub_state.get("on_surface", False):
        _hub_locs = dungeon.generate_surface_hub()
        full_input += (
            "\n\n[HUB CONTEXT — on_surface=True] "
            "Available locations: "
            + ", ".join(f"{l['id']} ({l['name']})" for l in _hub_locs)
            + ". Innkeeper Mira at ironwood_inn offers full rest for 5 gold — call rest_at_inn(). "
            "Ruined Shrine: one-time spell slot restore — call pray_at_shrine(). "
            "Dungeon Entrance: call descend_to_dungeon() when player explicitly chooses to enter."
        )

    # inject tutorial on the player's very first action
    _pre_state = state_to_dict()
    _pre_floor = _pre_state.get("floor", 1)
    if not _pre_state.get("tutorial_shown", False):
        full_input += (
            "\n\n[GM_SYSTEM — do not reproduce this text verbatim: "
            "End your narration with one brief in-world sentence that lets the player "
            "know they can tap map tiles to move, check the Inventory tab for gear, "
            "and find merchants in Rest rooms.]"
        )
        _pre_state["tutorial_shown"] = True
        engine._state_file().write_text(json.dumps(_pre_state, indent=2))

    try:
        resp  = engine.run_turn(client, history, full_input)
        state = state_to_dict()
        _new_floor = state.get("floor", 1)  # PHASE 4 added — detect floor change

        hub_locs = dungeon.generate_surface_hub() if state.get("on_surface") else []
        result = {
            "narrative":     resp["narrative_text"],
            "hp":            resp["current_hp"],
            "actions":       resp["available_actions"],
            "state":         state,
            "ending":        None,
            "dice":          dice_roll,
            "hub_locations": hub_locs,
            **_dungeon_state(),
        }

        # floor transition overlay trigger
        if _new_floor > _pre_floor:
            result["floor_transition"] = True
            result["floor_number"]     = _new_floor

        if state["hp"] <= 0:
            result["ending"] = {"type": "fallen", **ENDINGS["fallen"]}
        elif state["floor"] >= len(engine.FLOOR_ENEMIES):
            enemy = state.get("enemy")
            if not enemy or enemy["hp"] <= 0:
                etype          = engine.get_ending_type(state.get("choices", []))
                result["ending"] = {"type": etype, **ENDINGS[etype]}

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"The dungeon master faltered: {str(e)}"}), 500

@app.route("/api/combat/enemy-turn", methods=["POST"])
def enemy_turn():
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    history = get_or_init_history()
    s = mp.get_session(room_code)
    _mp_enemy = s and s.get("state") == "playing" and len(s.get("players", [])) > 1

    @after_this_request
    def _mp_enemy_post(response):
        if _mp_enemy:
            mp.advance_turn(room_code)
            _broadcast(room_code)
        return response

    try:
        result = combat.resolve_enemy_turn_if_current()

        if not result["resolved"]:
            state = state_to_dict()
            return jsonify({
                "narrative": "The dungeon waits. It is not the enemy's turn.",
                "hp": state["hp"],
                "actions": [],
                "state": state,
                "combat": result["combat_state"],
                "dice_rolls": []
            })

        event = result["event"]

        history.append({
            "role": "user",
            "content": "[SERVER_RESOLVED_ENEMY_TURN]\n" + json.dumps(event, indent=2)
        })

        resp = engine.run_resolved_turn(client, history, event)
        engine.save_history(history)

        state = state_to_dict()

        payload = {
            "narrative": resp["narrative_text"],
            "hp": state["hp"],
            "actions": resp.get("available_actions", event.get("available_actions", [])),
            "state": state,
            "ending": None,
            "dice": {
                "roll":    event.get("attack_roll"),
                "dc":      chars.load_character().get("combat", {}).get("armor_class") if event.get("attack_roll") is not None else None,
                "success": event.get("hit", False),
                "type":    "enemy_turn",
            } if event.get("attack_roll") is not None else None,
            "dice_rolls": event.get("dice_rolls_this_turn", []),
            "combat": combat.get_combat_public_state()
        }

        if state["hp"] <= 0:
            payload["ending"] = {"type": "fallen", **ENDINGS["fallen"]}

        return jsonify(payload)

    except Exception as e:
        state = state_to_dict()
        return jsonify({
            "error": f"Enemy turn failed: {str(e)}",
            "hp": state.get("hp", 0),
            "state": state
        }), 500

@app.route("/api/inventory")
def inventory():
    character = chars.load_character()
    if not character:
        return jsonify({"items": []})
    items = [
        {
            "id":          e.get("item_id", ""),
            "name":        e.get("name", ""),
            "quantity":    e.get("quantity", 1),
            "equipped":    e.get("equipped", False),
            "type":        e.get("type", ""),
            "description": e.get("description", ""),
            "weight":      e.get("weight", 0),
        }
        for e in character.get("equipment", [])
    ]
    return jsonify({"items": items})

@app.route("/api/combat_items")
def combat_items():
    character = chars.load_character()
    if not character:
        return jsonify({"items": []})
    consumable_types = {"consumable"}
    items = [
        {
            "id":          e.get("item_id", ""),
            "name":        e.get("name", ""),
            "quantity":    e.get("quantity", 0),
            "description": e.get("description", ""),
            "type":        e.get("type", ""),
        }
        for e in character.get("equipment", [])
        if e.get("type") in consumable_types and e.get("quantity", 0) > 0
    ]
    return jsonify({"items": items})

@app.route("/api/inventory/equip", methods=["POST"])
def inventory_equip():
    data    = request.get_json(silent=True, force=True) or {}
    item_id = data.get("item_id", "")
    equip   = bool(data.get("equipped", True))
    if not item_id:
        return jsonify({"error": "item_id required"}), 400
    result = chars.equip_item(item_id, equip)
    if "error" in result:
        return jsonify(result), 400
    combat.sync_game_state_from_character()
    return jsonify(result)

@app.route("/api/shop")
def shop():
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    state     = state_to_dict()
    floor_num = state.get("floor", 1)
    catalog   = chars.ITEM_CATALOG
    item_ids  = chars.SHOP_BY_FLOOR.get(floor_num, [])
    items = [
        {
            "id":          iid,
            "name":        catalog[iid]["name"],
            "cost":        catalog[iid]["cost"],
            "type":        catalog[iid].get("type", ""),
            "description": catalog[iid].get("description", ""),
            "weight":      catalog[iid].get("weight", 0),
        }
        for iid in item_ids if iid in catalog
    ]
    character = chars.load_character()
    gold = character.get("currency", {}).get("gp", 0) if character else 0
    return jsonify({"items": items, "gold": gold, "floor": floor_num})

@app.route("/api/party/inventory")
def party_inventory_get():
    return jsonify({"items": party_inv.get_pool()})


@app.route("/api/party/inventory/share", methods=["POST"])
def party_inventory_share():
    data    = request.get_json(silent=True, force=True) or {}
    item_id = data.get("item_id", "")
    qty     = max(1, int(data.get("qty", 1)))
    if not item_id:
        return jsonify({"error": "item_id required"}), 400
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    with _room_lock(room_code):
        mp.activate_player_character(room_code, player_name)
        result = party_inv.share_item(item_id, qty, player_name)
        if "error" in result:
            return jsonify(result), 400
        mp.save_active_character_to_party(room_code, player_name)
    _broadcast(room_code)
    return jsonify({**result, "pool": party_inv.get_pool()})


@app.route("/api/party/inventory/take", methods=["POST"])
def party_inventory_take():
    data    = request.get_json(silent=True, force=True) or {}
    item_id = data.get("item_id", "")
    qty     = max(1, int(data.get("qty", 1)))
    if not item_id:
        return jsonify({"error": "item_id required"}), 400
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    with _room_lock(room_code):
        mp.activate_player_character(room_code, player_name)
        result = party_inv.take_item(item_id, qty, player_name)
        if "error" in result:
            return jsonify(result), 400
        mp.save_active_character_to_party(room_code, player_name)
    _broadcast(room_code)
    return jsonify({**result, "pool": party_inv.get_pool()})


@app.route("/api/shop/buy", methods=["POST"])
def shop_buy():
    data    = request.get_json(silent=True, force=True) or {}
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    item_id = data.get("item_id", "")
    if not item_id:
        return jsonify({"error": "item_id required"}), 400
    with _room_lock(room_code):
        state     = state_to_dict()
        floor_num = state.get("floor", 1)
        result = chars.buy_item(item_id, floor_num)
        if "error" in result:
            return jsonify(result), 400
        state["gold"] = result["gold_remaining"]
        engine._state_file().write_text(json.dumps(state, indent=2))
    return jsonify(result)

@app.route("/api/dungeon/current_room")
def dungeon_current_room():
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    state           = state_to_dict()
    floor_num       = state.get("floor", 1)
    current_room_id = state.get("current_room_id", dungeon.get_entrance_room_id(floor_num))
    room = dungeon.get_current_room(floor_num, current_room_id)
    if not room:
        return jsonify({"error": "No current room."}), 404
    return jsonify({"room": room, "floor": floor_num})


@app.route("/api/dungeon/map")
def dungeon_map_route():
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    state           = state_to_dict()
    floor_num       = state.get("floor", 1)
    current_room_id = state.get("current_room_id", dungeon.get_entrance_room_id(floor_num))
    return jsonify({
        "floor":           floor_num,
        "current_room_id": current_room_id,
        "boss_cleared":    state.get("boss_cleared", False),
        "rooms":           dungeon.get_map_for_frontend(floor_num, current_room_id),
    })

@app.route("/api/dungeon/move", methods=["POST"])
def dungeon_move():
    data    = request.get_json(silent=True, force=True) or {}
    room_id = data.get("room_id", "")
    if not room_id:
        return jsonify({"error": "room_id required"}), 400
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    s = mp.get_session(room_code)
    _mp_move = s and s.get("state") == "playing" and len(s.get("players", [])) > 1
    if _mp_move:
        if not mp.is_player_turn(room_code, player_name):
            return jsonify({"error": "It is not your turn to move."}), 403
        mp.activate_player_character(room_code, player_name)

    @after_this_request
    def _mp_move_post(response):
        if _mp_move:
            mp.save_active_character_to_party(room_code, player_name)
            _broadcast(room_code)
        try:
            saves.auto_save(chars.load_character(), state_to_dict(), engine.load_history())
        except Exception:
            pass
        return response

    state           = state_to_dict()
    floor_num       = state.get("floor", 1)
    current_room_id = state.get("current_room_id", dungeon.get_entrance_room_id(floor_num))

    if state.get("enemy") and state["enemy"].get("hp", 0) > 0:
        return jsonify({"error": "Cannot move rooms while in combat."}), 400

    result = dungeon.move_to_room(room_id, current_room_id, floor_num)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400

    state["current_room_id"] = room_id
    state["location"]        = f"Ironwood Dungeon -- Floor {floor_num}, {result['room_name']}"
    if result.get("gold_gained"):
        state["gold"] = state.get("gold", 0) + result["gold_gained"]
    if result.get("enemy"):
        state["enemy"]          = result["enemy"]
        state["room_searched"]  = False
    elif result["room_type"] == "Boss":
        boss = dict(engine.FLOOR_ENEMIES.get(floor_num, {}))
        if boss and (not state.get("enemy") or state.get("enemy", {}).get("hp", 0) <= 0):
            state["enemy"]         = boss
            state["room_searched"] = False
    engine._state_file().write_text(json.dumps(state, indent=2))
    combat.sync_game_state_from_character()
    # Initialize initiative order immediately so the first move response
    # already has combat.active = true — this is what triggers combat music.
    if state.get("enemy") and state["enemy"].get("hp", 0) > 0:
        s = mp.get_session(room_code)
        party = s.get("players", []) if s else []
        combat.start_combat_if_needed(party if len(party) > 1 else None)
    state = state_to_dict()

    full_room = dungeon.get_current_room(floor_num, room_id) or {}
    event = {
        "type":              "move_room",
        "room_id":           room_id,
        "room_name":         result["room_name"],
        "room_type":         result["room_type"],
        "description_seed":  result["description_seed"],
        "exits":             result["exits"],
        "cleared":           result["cleared"],
        "trap_triggered":    result.get("trap_triggered"),
        "trap_result":       result.get("trap_result"),
        "loot":              result.get("loot"),
        "gold_gained":       result.get("gold_gained", 0),
        "enemy":             result.get("enemy"),
        "puzzle_text":       result.get("puzzle_text"),
        "rest_available":    result.get("rest_available", False),
        "full_room":         full_room,
        "available_actions": combat.get_available_combat_actions(),
        "dice_rolls_this_turn": result.get("dice_rolls_this_turn", []),
        "xp_awarded":        result.get("xp_awarded"),
    }

    history = get_or_init_history()
    history.append({"role": "user", "content": "[MOVE_TO_ROOM]\n" + json.dumps(event, indent=2)})
    resp = engine.run_resolved_turn(client, history, event)
    engine.save_history(history)
    state = state_to_dict()

    response = {
        "narrative":   resp["narrative_text"],
        "hp":          state["hp"],
        "actions":     resp.get("available_actions", event["available_actions"]),
        "state":       state,
        "ending":      None,
        "dice_rolls":  event["dice_rolls_this_turn"],
        "combat":      combat.get_combat_public_state(),
        "gold_gained": result.get("gold_gained", 0),
        **_xp_state(event),
        **_dungeon_state(),
        **_spell_state(),
    }
    if state["hp"] <= 0:
        response["ending"] = {"type": "fallen", **ENDINGS["fallen"]}
    return jsonify(response)

@app.route("/api/dungeon/puzzle", methods=["POST"])
def dungeon_puzzle():
    data    = request.get_json(silent=True, force=True) or {}
    room_id = data.get("room_id", "")
    answer  = data.get("answer", "").strip()
    if not room_id or not answer:
        return jsonify({"error": "room_id and answer required"}), 400
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    s = mp.get_session(room_code)
    _mp_puz = s and s.get("state") == "playing" and len(s.get("players", [])) > 1
    if _mp_puz:
        if not mp.is_player_turn(room_code, player_name):
            return jsonify({"error": "It is not your turn."}), 403
        mp.activate_player_character(room_code, player_name)

    @after_this_request
    def _mp_puz_post(response):
        if _mp_puz:
            mp.save_active_character_to_party(room_code, player_name)
            _broadcast(room_code)
        return response

    state     = state_to_dict()
    floor_num = state.get("floor", 1)
    result    = dungeon.check_puzzle(room_id, floor_num, answer)

    if result.get("already_solved"):
        return jsonify({"correct": True, "narrative": result["message"]})

    event = {
        "type":         "puzzle_attempt",
        "room_id":      room_id,
        "answer_given": answer,
        "correct":      result.get("correct", False),
        "message":      result.get("message", ""),
        "reward":       result.get("reward"),
        "xp_awarded":   result.get("xp_awarded"),
        "available_actions": combat.get_available_combat_actions(),
        "dice_rolls_this_turn": [],
    }

    history = get_or_init_history()
    history.append({"role": "user", "content": "[PUZZLE_ATTEMPT]\n" + json.dumps(event, indent=2)})
    resp = engine.run_resolved_turn(client, history, event)
    engine.save_history(history)
    state = state_to_dict()

    return jsonify({
        "narrative": resp["narrative_text"],
        "correct":   result.get("correct", False),
        "hp":        state["hp"],
        "state":     state,
        **_xp_state(event),
        **_dungeon_state(),
        **_spell_state(),
    })

# NPC / Quest routes

@app.route("/api/npc/<npc_id>")
def get_npc(npc_id):
    npc = npcm.get_npc(npc_id)
    if not npc:
        return jsonify({"error": "NPC not found."}), 404
    qid    = npc.get("quest_id")
    return jsonify({
        "npc":          npc,
        "quest_status": npcm.get_quest_status(qid) if qid else None,
    })


@app.route("/api/npc/<npc_id>/talk", methods=["POST"])
def talk_npc(npc_id):
    npc_data = npcm.talk_to_npc(npc_id)
    if "error" in npc_data:
        return jsonify(npc_data), 404
    history = get_or_init_history()
    event   = {
        "type":                 "npc_talk",
        "npc_id":               npc_id,
        "available_actions":    [],
        "dice_rolls_this_turn": [],
        **npc_data,
    }
    history.append({"role": "user", "content": "[NPC_TALK]\n" + json.dumps(event, indent=2)})
    resp = engine.run_resolved_turn(client, history, event)
    engine.save_history(history)
    state = state_to_dict()
    return jsonify({
        "narrative": resp["narrative_text"],
        "state":     state,
        "hp":        state["hp"],
        **npc_data,
    })


@app.route("/api/npc/<npc_id>/persuade", methods=["POST"])
def persuade_npc(npc_id):
    result = npcm.persuasion_check(npc_id)
    if "error" in result:
        return jsonify(result), 404
    history = get_or_init_history()
    event   = {
        "type":                 "npc_persuade",
        "available_actions":    [],
        "dice_rolls_this_turn": [
            {"die": "d20", "result": result["roll"],
             "purpose": f"Persuasion vs {result['npc_name']} DC {result['dc']}"}
        ],
        **result,
    }
    history.append({"role": "user", "content": "[NPC_PERSUADE]\n" + json.dumps(event, indent=2)})
    resp = engine.run_resolved_turn(client, history, event)
    engine.save_history(history)
    state = state_to_dict()
    return jsonify({
        "narrative": resp["narrative_text"],
        "state":     state,
        "hp":        state["hp"],
        **result,
    })


@app.route("/api/npc/<npc_id>/buy", methods=["POST"])
def buy_from_npc(npc_id):
    data     = request.get_json(silent=True, force=True) or {}
    item_id  = data.get("item_id", "")
    quantity = max(1, int(data.get("quantity", 1)))
    if not item_id:
        return jsonify({"error": "item_id required."}), 400
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    s = mp.get_session(room_code)
    _mp_buy = s and s.get("state") == "playing" and len(s.get("players", [])) > 1
    if _mp_buy:
        mp.activate_player_character(room_code, player_name)
    result = npcm.buy_item(npc_id, item_id, quantity, player_name)
    if result.get("success"):
        char = chars.load_character()
        if char:
            char["currency"]["gp"] = result["gold_remaining"]
            chars._char_file().write_text(json.dumps(char, indent=2))
        state = state_to_dict()
        state["gold"] = result["gold_remaining"]
        engine._state_file().write_text(json.dumps(state, indent=2))
        chars.add_item_to_equipment(item_id, quantity)
        if _mp_buy:
            mp.save_active_character_to_party(room_code, player_name)
            _broadcast(room_code)
    return jsonify(result)


@app.route("/api/quest/accept", methods=["POST"])
def accept_quest():
    data = request.get_json(silent=True, force=True) or {}
    return jsonify(npcm.accept_quest(data.get("quest_id", "")))


@app.route("/api/quest/complete", methods=["POST"])
def complete_quest():
    data        = request.get_json(silent=True, force=True) or {}
    quest_id    = data.get("quest_id", "")
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    result      = npcm.complete_quest(quest_id, player_name)
    if result.get("success"):
        combat.sync_game_state_from_character()
        _emit_level_up(room_code, player_name, result.get("xp_awarded"))
    return jsonify(result)


@app.route("/api/quests")
def list_quests():
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    defs  = npcm.QUEST_DEFINITIONS
    state = state_to_dict()
    out   = []
    for qid, defn in defs.items():
        status = npcm.get_quest_status(qid)
        obj    = defn["objective"]
        met    = npcm._check_objective(obj, state)
        out.append({
            "id":          qid,
            "name":        defn["name"],
            "description": defn["description"],
            "giver":       defn["giver_id"],
            "status":      status,
            "objective_met": met,
            "xp_reward":   defn["xp_reward"],
            "gold_reward": defn["gold_reward"],
        })
    return jsonify({"quests": out})


# Save / Load routes

@app.route("/api/saves")
def list_saves_route():
    return jsonify({"saves": saves.list_saves()})


@app.route("/api/saves/save", methods=["POST"])
def save_game_route():
    data = request.get_json(silent=True, force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Save name required."}), 400
    char  = chars.load_character()
    state = state_to_dict()
    hist  = engine.load_history()
    if not char:
        return jsonify({"error": "No character to save."}), 400
    return jsonify(saves.save_game(name, char, state, hist))


@app.route("/api/saves/load", methods=["POST"])
def load_save_route():
    data    = request.get_json(silent=True, force=True) or {}
    room_code, player_name = _room_ctx()
    _setup_room(room_code, player_name)
    save_id = (data.get("save_id") or "").strip()
    if not save_id:
        return jsonify({"error": "save_id required."}), 400
    result = saves.load_game(
        save_id,
        str(chars._char_file()),
        str(engine._state_file()),
        str(engine._hist_file()),
    )
    if "error" in result:
        return jsonify(result), 404
    combat.reset_combat_state()
    combat.sync_game_state_from_character()
    state = state_to_dict()
    return jsonify({
        "success":   True,
        "narrative": state.get("last_narrative", "You resume your journey..."),
        "hp":        state["hp"],
        "state":     state,
        "combat":    combat.get_combat_public_state(),
        **_dungeon_state(),
        **_spell_state(),
    })


@app.route("/api/saves/<save_id>", methods=["DELETE"])
def delete_save_route(save_id):
    return jsonify(saves.delete_save(save_id))


# SocketIO events for multiplayer lobby and chat

@socketio.on("connect")
def on_connect():
    pass


@socketio.on("disconnect")
def on_disconnect():
    room_code, player_name = mp.on_disconnect(request.sid)
    if not room_code:
        return
    s            = mp.get_session(room_code)
    skip_msg     = None
    combat_state = combat.get_combat_public_state()
    if (s and s.get("state") == "playing" and combat_state.get("active")):
        actor = mp.get_current_actor(room_code)
        if actor and actor.get("type") == "player" and actor.get("player_name") == player_name:
            mp.advance_turn(room_code)
            skip_msg = f"{player_name} has gone silent mid-battle. Their turn is skipped."
    payload = {"player_name": player_name, "party": mp.get_party_status(room_code)}
    if skip_msg:
        payload["skip_narrative"] = skip_msg
    socketio.emit("player_disconnected", payload, room=room_code)


@socketio.on("create_game")
def on_create_game(data):
    player_name = (data or {}).get("player_name", "Player")
    room_code   = mp.create_room(request.sid, player_name)
    sio_join(room_code)
    emit("room_created", {
        "room_code":   room_code,
        "player_name": player_name,
        "is_host":     True,
        "party":       mp.get_party_status(room_code),
    })


@socketio.on("join_game")
def on_join_game(data):
    data        = data or {}
    room_code   = (data.get("room_code") or "").upper()
    player_name = data.get("player_name", "Player")
    result      = mp.join_room(room_code, request.sid, player_name)
    if "error" in result:
        emit("error", {"message": result["error"]})
        return
    sio_join(result["room_code"])
    emit("room_joined", {
        "room_code":   result["room_code"],
        "player_name": player_name,
        "is_host":     result["is_host"],
        "rejoined":    result["rejoined"],
        "state":       result["state"],
        "party":       mp.get_party_status(result["room_code"]),
    })
    socketio.emit("player_list_update",
                  {"party": mp.get_party_status(result["room_code"])},
                  room=result["room_code"])


@socketio.on("player_ready")
def on_player_ready(data):
    data        = data or {}
    room_code   = (data.get("room_code") or "").upper()
    player_name = data.get("player_name", "")
    character   = data.get("character")
    if character:
        mp.set_character(room_code, player_name, character)
    s = mp.get_session(room_code)
    if s:
        socketio.emit("player_list_update",
                      {"party": mp.get_party_status(room_code),
                       "all_ready": mp.all_ready(room_code)},
                      room=room_code)


@socketio.on("game_start")
def on_game_start(data):
    data      = data or {}
    room_code = (data.get("room_code") or "").upper()
    result    = mp.start_game(room_code, request.sid)
    if "error" in result:
        emit("error", {"message": result["error"]})
        return
    s = mp.get_session(room_code)
    host_name = s["players"][0]["player_name"] if s and s.get("players") else ""
    _setup_room(room_code, host_name)
    dungeon.generate_all_floors()
    engine._state_file().write_text(json.dumps(engine.INITIAL_GAME_STATE, indent=2))
    engine._hist_file().write_text(json.dumps([], indent=2))
    socketio.emit("game_started", {"room_code": room_code}, room=room_code)


@socketio.on("kick_player")
def on_kick_player(data):
    data        = data or {}
    room_code   = (data.get("room_code") or "").upper()
    target_name = data.get("target_name", "")
    result      = mp.kick_player(room_code, request.sid, target_name)
    if "error" in result:
        emit("error", {"message": result["error"]})
        return
    socketio.emit("player_kicked",
                  {"player_name": target_name, "party": mp.get_party_status(room_code)},
                  room=room_code)


@socketio.on("chat_message")
def on_chat_message(data):
    data        = data or {}
    room_code   = (data.get("room_code") or "").upper()
    player_name = data.get("player_name", "?")
    message     = (data.get("message") or "").strip()[:300]
    if not message:
        return
    socketio.emit("chat_message",
                  {"player_name": player_name, "message": message,
                   "ts": int(time.time())},
                  room=room_code)


@socketio.on("pause_game")
def on_pause_game(data):
    data      = data or {}
    room_code = (data.get("room_code") or "").upper()
    s         = mp.get_session(room_code)
    if s and s.get("host_sid") == request.sid:
        s["paused"] = not s.get("paused", False)
        socketio.emit("game_paused", {"paused": s["paused"]}, room=room_code)


if __name__ == "__main__":
    # socketio.run(app, debug=True, port=5000)  # old local-only config
    port  = int(os.environ.get("PORT", 7860))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug, allow_unsafe_werkzeug=True)
