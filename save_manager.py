import json, time, shutil
from pathlib import Path

BASE      = Path(__file__).parent
SAVES_DIR = BASE / "saves"
INDEX_FILE = SAVES_DIR / "index.json"

AUTOSAVE_NAME = "__autosave__"


def _ensure():
    SAVES_DIR.mkdir(exist_ok=True)


def _load_index():
    _ensure()
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except Exception:
            return []
    return []


def _write_index(index):
    INDEX_FILE.write_text(json.dumps(index, indent=2))


def list_saves():
    return _load_index()


def save_game(name, character, game_state, history):
    _ensure()
    index = _load_index()

    # Find existing slot by name
    save_id = None
    for s in index:
        if s["name"] == name:
            save_id = s["id"]
            break

    if not save_id:
        save_id = str(int(time.time() * 1000))

    save_dir = SAVES_DIR / save_id
    save_dir.mkdir(exist_ok=True)

    (save_dir / "character.json").write_text(json.dumps(character, indent=2))
    (save_dir / "game_state.json").write_text(json.dumps(game_state, indent=2))
    (save_dir / "history.json").write_text(json.dumps(history, indent=2))

    identity = character.get("identity", {}) if character else {}
    meta = {
        "id":        save_id,
        "name":      name,
        "char_name": identity.get("character_name", "Unknown"),
        "class":     identity.get("class", ""),
        "level":     identity.get("level", 1),
        "floor":     game_state.get("floor", 1) if game_state else 1,
        "hp":        game_state.get("hp", 0) if game_state else 0,
        "saved_at":  int(time.time()),
        "is_auto":   name == AUTOSAVE_NAME,
    }

    updated = False
    for i, s in enumerate(index):
        if s["id"] == save_id:
            index[i] = meta
            updated = True
            break
    if not updated:
        index.append(meta)

    _write_index(index)
    return {"success": True, "save_id": save_id, "metadata": meta}


def load_game(save_id, char_path, state_path, history_path, inventory_path=None):
    save_dir = SAVES_DIR / save_id
    if not save_dir.exists():
        return {"error": "Save not found."}
    try:
        char    = json.loads((save_dir / "character.json").read_text())
        state   = json.loads((save_dir / "game_state.json").read_text())
        history = json.loads((save_dir / "history.json").read_text())
        Path(char_path).write_text(json.dumps(char, indent=2))
        Path(state_path).write_text(json.dumps(state, indent=2))
        Path(history_path).write_text(json.dumps(history, indent=2))
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def delete_save(save_id):
    save_dir = SAVES_DIR / save_id
    if save_dir.exists():
        shutil.rmtree(save_dir)
    index = [s for s in _load_index() if s["id"] != save_id]
    _write_index(index)
    return {"success": True}


def auto_save(character, game_state, history):
    return save_game(AUTOSAVE_NAME, character, game_state, history)
