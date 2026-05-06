---
title: Ironwood Dungeon
emoji: 🏰
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Ironwood Dungeon

Ironwood Dungeon is a browser-based role-playing game where an AI acts as your Game Master. You explore a four-floor dungeon, fight enemies, solve puzzles, manage your inventory, and talk to NPCs. All of it is narrated in real time by a large language model that is strictly grounded in the actual game state on the server.

**Live demo:** [HuggingFace Space](https://huggingface.co/spaces) *(replace with your Space URL)*

---

## What This Project Is

This project shows how to safely connect an AI language model to a game without letting it make things up. The AI can only describe things the server has already confirmed to be true. It cannot invent items the player does not own, cannot change HP values on its own, and cannot describe a room it has not been given information about. Every mechanical outcome (combat rolls, trap saves, spell effects) is resolved by Python code on the server before the AI ever receives it. The AI handles narration only.

This project was built as a submission for an AI course. It covers grounded AI tool use, structured outputs, persistent game state, real-time multiplayer, and a full deployment pipeline on HuggingFace Spaces.

---

## Features

- **AI Game Master** powered by NVIDIA's nemotron-super-120b model, accessed through the NVIDIA NIM API
- **10 playable character classes**: Fighter, Wizard, Rogue, Cleric, Ranger, Barbarian, Paladin, Bard, Druid, and Monk, each with unique stats, spell lists, and abilities
- **4-floor dungeon** procedurally arranged each run, with 5 rooms per floor including Entrance, Combat, Trap, Treasure, Rest, Puzzle, and Boss rooms
- **D&D 5th Edition rules** for saving throws, conditions, advantage and disadvantage, spell slots, proficiency bonus, XP, and levelling up. All resolved server-side before narration
- **Ironwood Village** as a surface hub between dungeon runs, with an inn, market, notice board, shrine, and dungeon entrance. Each location has interactive NPCs
- **Multiplayer support** for up to 4 players sharing a room with a 4-character code. The AI tracks every player's actions in a shared history file
- **Save system** that writes game state to disk after every action. Resuming a session picks up exactly where it stopped
- **Original soundtrack** with 8 tracks generated using Suno.com, one for each game state (village, exploration, combat, boss battle, victory, and defeat)
- **Sound effects** with 7 short audio clips generated using ElevenLabs (dice roll, hit, miss, level up, door, treasure found, and death)
- **AI-generated portraits** with 10 character class portraits and 16 enemy portraits, all generated using ChatGPT image generation

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask, Flask-SocketIO |
| AI Game Master | NVIDIA NIM API (nemotron-super-120b) via the OpenAI SDK |
| Frontend | Vanilla JavaScript, HTML5, CSS3. No framework, no build step |
| Game Rules Engine | Custom Python implementing D&D 5th Edition combat and spells |
| Real-time Communication | WebSockets via Socket.IO |
| Deployment | Docker on HuggingFace Spaces |
| Portraits | ChatGPT image generation |
| Music | Suno.com |
| Sound Effects | ElevenLabs |

---

## How the AI Game Master Works

This is the core engineering challenge of the project. The AI is given a strict set of rules in its system prompt called the Grounding Contract. It is not allowed to describe the game world from its own imagination. It must call a server-side tool to verify the facts first, then narrate only what the tool returned.

### The Tool System

The AI has access to the following tools, which are Python functions running on the server:

| Tool | What it does |
|---|---|
| `get_inventory()` | Returns the player's real item list from the inventory file |
| `use_item(item_id, target)` | Consumes or applies an item, modifies the file, and returns the result |
| `get_character_sheet()` | Returns HP, class, level, spell slots, and conditions |
| `cast_spell(spell_name, target)` | Resolves all spell mechanics and returns the outcome |
| `attack(weapon_id)` | Rolls attack and damage dice and returns the result |
| `search_room()` | Resolves a loot roll and returns what was found |
| `game_response(narrative_text, current_hp, available_actions)` | Required final call on every single turn. This is the structured output the server sends to the browser |
| `talk_to_npc(npc_id)` | Returns the NPC's scripted dialogue. The AI cannot invent NPC speech |
| `next_floor()` | Descends to the next dungeon floor |
| `descend_to_dungeon()` | Moves the player from the village into the dungeon |

### The Ironclad Rules

At the start of every session, the AI's system prompt includes these hard constraints. Violating any of them is defined as a critical failure:

1. Call `get_inventory()` before referencing, describing, or using any item
2. Narrate only numbers returned by tools or already present in the game state
3. Do not take actions the player did not request
4. Always end every turn with exactly one call to `game_response()`, never skip it
5. Keep `current_hp` equal to the value returned by tools. Never alter it in prose
6. NPC dialogue must come only from `talk_to_npc()`. Never fabricate NPC speech
7. Room contents are established by server tools. Never invent room features the tools did not return

### Conversation Memory

Every turn, the full conversation history is loaded from disk and passed to the AI. This means the AI always has the complete picture of the entire session: which rooms were cleared, what was said to each NPC, how much damage was taken several floors ago. In multiplayer, all players share one history file, so the AI remembers the actions of every player in the party, not just the one currently acting.

One known limitation: history is never trimmed. For a normal four-floor run of roughly 50 to 100 turns this is not a problem. A very long session could approach the model's context window limit. A sliding window or a summarization step that compresses old turns would fix this but is not implemented yet.

---

## Task 1: Grounded AI Responses

The central engineering challenge was making the AI Game Master impossible to fool. It cannot describe an item the player does not have, cannot invent HP values, and cannot narrate a spell it has not verified exists in the player's spell slots. This section explains exactly how each requirement is satisfied in the code.

### Requirement: get_inventory() tool

The tool is registered in the AI's tool list so the model knows it exists and can call it. When called, it reads `inventory.json` from disk and returns the real item list. The AI cannot describe any item without calling this first because the system prompt forbids it under Rule 1 of the Ironclad Rules.

- `rpg_engine.py` line 259: tool definition name field
- `rpg_engine.py` line 415: dispatch block — `if name == "get_inventory": return json.dumps(get_inventory())`
- `rpg_engine.py` line 6: `INVENTORY_FILE = BASE / "inventory.json"`

### Requirement: use_item(item_id, target) tool

When the AI decides to use an item, it calls this tool with the item ID and the target. The server removes or modifies the item in `inventory.json` and returns the result. The AI then narrates only what the tool result says happened. If the item does not exist, the tool returns an error and the AI must narrate the failure.

- `rpg_engine.py` line 264: tool definition name field
- `rpg_engine.py` line 416: dispatch block — `if name == "use_item": return json.dumps(use_item(...))`

### Requirement: Structured output with narrative_text, current_hp, and available_actions

Every response the AI sends must end with a call to the `game_response()` tool. This tool has a strict JSON schema the model must follow. The schema marks all three fields as required, so the AI cannot skip any of them. The server extracts these values and sends them to the browser. The player's HP shown on screen comes from `current_hp` in this response, not from anything the AI wrote in prose.

- `rpg_engine.py` line 346: game_response tool name
- `rpg_engine.py` line 349: narrative_text field definition
- `rpg_engine.py` line 350: current_hp field definition
- `rpg_engine.py` line 352: available_actions field definition
- `rpg_engine.py` line 357: `required: ["narrative_text", "current_hp", "available_actions"]`

### Requirement: LLM must verify items via tool call before describing them

This is enforced by the system prompt. The very first ironclad rule the AI sees when a session starts tells it to call `get_inventory()` before mentioning any item at all. If the AI skips this and invents an item, it has violated the grounding contract. The rule is written as a critical failure condition so the model treats it as a hard constraint, not a suggestion.

- `app.py` line 65: IRONCLAD RULES section header
- `app.py` line 66: Rule 1 — "Call get_inventory() before referencing, describing, or using ANY item"

### Conversation Memory

The AI Game Master remembers everything that happened in your session. Every time you take an action, the game sends the full conversation history to the AI, not just your latest message. This means the AI knows which rooms you visited, which enemies you fought, what you said to the innkeeper, and how close to death you came three floors ago. It does not reset between turns.

After every turn, the complete history is written to a file on the server. When the next turn starts, that file is read back in and passed to the AI alongside the new message. The history grows throughout the session and the AI always has the full picture of what came before. In multiplayer, all players share one history file per room, so the AI remembers the actions of every player in the party, not just whoever is acting right now.

- `app.py` line 155: `get_or_init_history()` loads the saved history at the start of every turn, or starts fresh if it is the first turn
- `app.py` line 620: history is loaded before every player action and passed to the AI
- `rpg_engine.py` line 262: `save_history()` writes the updated conversation to disk after each turn
- `rpg_engine.py` line 266: `load_history()` reads it back at the start of the next turn
- `rpg_engine.py` line 19: `_hist_file()` returns the correct history file for the current room, so each multiplayer room keeps its own separate memory
- `rpg_engine.py` line 381: `run_turn()` receives the full history list as a parameter and sends it to the AI model unchanged

One known limitation: there is no truncation or summarization. The history file grows with every turn and is always sent in full to the AI. Every language model has a maximum amount of text it can read at once, called the context window. If a session runs long enough, the history will eventually exceed that limit and the API will return an error. For a normal run through all four floors, which takes roughly 50 to 100 turns, this is very unlikely to happen. A very long session or one with unusually verbose narration could hit it. The proper fix is a sliding window that drops the oldest turns, or a summarization step that compresses them into a short paragraph before they are discarded. Neither is implemented yet.

### Persistent World State

The world state is never held only in memory. Every meaningful change is written to disk immediately. This means the server can restart and the game continues exactly where it left off. The frontend reads these files on resume and restores the full UI state including the map, character sheet, and conversation history.

- `rpg_engine.py` line 6: `INVENTORY_FILE = BASE / "inventory.json"`
- `rpg_engine.py` line 7: `GAME_STATE_FILE = BASE / "game_state.json"`
- `character_manager.py` line 670: character.json read in `load_character()`

---

## Project Structure

```
ironwood-dungeon/
├── app.py                      Flask routes, Socket.IO events, AI tool dispatch, system prompt
├── rpg_engine.py               Core game loop, history I/O, AI tool definitions
├── character_manager.py        Character creation, levelling, spell slots, conditions
├── combat_manager.py           Attack rolls, damage, saving throws, combat conditions
├── spell_manager.py            Spell definitions and resolution
├── dungeon_generator.py        Procedural floor and room generation
├── npc_manager.py              NPC registry, dialogue trees, quest state
├── save_manager.py             Named save slots
├── party_inventory_manager.py  Shared party inventory for multiplayer
├── multiplayer_manager.py      Room codes, player sessions, Socket.IO room events
├── templates/
│   ├── index.html              Main game UI (single page, vanilla JS)
│   ├── about.html              Technical breakdown of how the project was built
│   └── credits.html            Credits page with music player
├── static/
│   ├── game.js                 Shared client-side utilities
│   ├── style.css               Global styles
│   ├── portraits/              Character and enemy PNG portraits
│   ├── sounds/                 MP3 music tracks and sound effects
│   └── textures/               Background texture images
├── enemies.json                Enemy stat blocks
├── Dockerfile                  Container config for HuggingFace Spaces
├── requirements.txt
└── .env.example                Template for local secrets
```

---

## Running Locally

### What You Need

- Python 3.11
- A free NVIDIA NIM API key from [build.nvidia.com](https://build.nvidia.com)

### Setup Steps

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/ironwood-dungeon.git
cd ironwood-dungeon

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your environment file
cp .env.example .env
# Open .env and replace the placeholder with your real NVIDIA_API_KEY
```

### Start the Server

```bash
python app.py
```

Open your browser at `http://127.0.0.1:7860`

---

## Deploying to HuggingFace Spaces

This project uses the Docker SDK on HuggingFace Spaces. The Dockerfile is already set up for port 7860.

1. Create a new Space on [huggingface.co](https://huggingface.co) with Docker as the SDK
2. Push this repository to the Space's git remote
3. In the Space settings, go to Repository Secrets and add a secret named `NVIDIA_API_KEY` with your key value
4. The Space will build the Docker image and start automatically

The `.env` file is never committed because it is listed in `.gitignore`. The API key is read from the environment, which HuggingFace injects from Secrets at runtime. This means your key is never stored in the repository.

---

## AI Generated Assets

All AI-generated content in this project was created specifically for it.

| Asset | Tool Used | Approach |
|---|---|---|
| 10 character portraits | ChatGPT image generation | Dark fantasy oil painting style, portrait orientation, one prompt per class |
| 16 enemy portraits | ChatGPT image generation | Same style, each prompt described the enemy's physical form and the dungeon setting |
| 8 background music tracks | Suno.com | One prompt per game state, looping arrangement, medieval dark fantasy genre |
| 7 sound effects | ElevenLabs | Detailed verbal descriptions for each sound (dice on stone, sword striking armor, etc.) |

---

## Known Limitations

- History grows without limit. Very long sessions may eventually hit the model's context window. A summarization step would be the proper fix
- No authentication on multiplayer rooms. Anyone with the 4-character room code can join. This is fine for demos and classroom use but not for public deployment
- Game state is stored in local JSON files. Two solo sessions on the same server instance will conflict unless they use separate multiplayer room codes

---

## Created By

**SKMMT** [skmmt.rootexception.com](https://skmmt.rootexception.com/)
