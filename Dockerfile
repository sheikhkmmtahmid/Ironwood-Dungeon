FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Remove local game state files and secrets — these come from env vars at runtime
RUN rm -f game_state_*.json history_*.json character_*.json \
          dungeon_map_*.json party.json party_inventory_*.json \
          active_quests.json inventory.json npc_registry.json .env

RUN mkdir -p saves

EXPOSE 7860

CMD ["python", "app.py"]
