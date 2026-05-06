const $ = id => document.getElementById(id);
let busy        = false;
let twTimer     = null;
let turnCount   = 0;
let historyOpen = false;
let diceTimer   = null;
let inCombat    = false;
let _lastBroadcastNarrative = "";
var _lastAvailableSpells = [];
var _lastSpellSlots      = {};

const api = {
  resume: ()  => fetch("/api/resume").then(r => r.json()),
  reset:  ()  => fetch("/api/reset",  {method:"POST"}).then(r => r.json()),
  new:    ()  => fetch("/api/new", {method:"POST"}).then(r => r.json()),
  action: (d) => fetch("/api/action", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(d)}).then(r => r.json()),
  enemyTurn: () => fetch("/api/combat/enemy-turn", {method:"POST"}).then(r => r.json()),
  inv:    ()  => fetch("/api/inventory").then(r => r.json()),

  character: () => fetch("/api/character").then(r => r.json()),
  characterOptions: () => fetch("/api/character/options").then(r => r.json()),
  createCharacter: (d) => fetch("/api/character/create", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(d)
  }).then(async r => {
    const data = await r.json();
    if (!r.ok) throw data;
    return data;
  }),
};

let characterOptions = null;

function fillSelect(id, values, labelPrefix) {
  const sel = $(id);
  sel.innerHTML = "";

  values.forEach(function(v) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = labelPrefix ? labelPrefix + " " + v : v;
    sel.appendChild(opt);
  });
}

function getCheckedValues(containerId) {
  const container = $(containerId);
  if (!container) return [];

  return Array.from(container.querySelectorAll("input[type=checkbox]:checked"))
    .map(function(x) {
      return x.value;
    });
}

function renderSpellChecks(values, id) {
  const row = $(id);
  if (!row) return;

  row.innerHTML = "";

  values.forEach(function(value) {
    const label = document.createElement("label");
    label.className = "cc-check";
    label.innerHTML = '<input type="checkbox" value="' + value + '"> ' + value;
    row.appendChild(label);
  });
}

function renderClassChoices() {
  if (!characterOptions) return;

  const cls = $("cc-class").value;
  const skillsBox = $("cc-class-skills");
  const extraBox = $("cc-extra-choices");

  skillsBox.innerHTML = "";
  extraBox.innerHTML = "";

  const skillInfo = characterOptions.class_skill_options[cls];

  if (skillInfo) {
    skillsBox.innerHTML =
      '<div class="load-msg">Choose ' + skillInfo.pick + ' class skill(s)</div>' +
      '<div class="cc-check-row" id="cc-skill-checks"></div>';

    const row = $("cc-skill-checks");

    skillInfo.options.forEach(function(skill) {
      const label = document.createElement("label");
      label.className = "cc-check";
      label.innerHTML = '<input type="checkbox" value="' + skill + '"> ' + skill;
      row.appendChild(label);
    });
  }

  if (cls === "Rogue") {
    extraBox.innerHTML +=
      '<h3 class="cc-title">Expertise</h3>' +
      '<div class="load-msg">Choose 2 skills from your selected proficiencies.</div>' +
      '<div class="cc-check-row" id="cc-expertise-checks"></div>';

    const row = $("cc-expertise-checks");

    characterOptions.class_skill_options.Rogue.options.forEach(function(skill) {
      const label = document.createElement("label");
      label.className = "cc-check";
      label.innerHTML = '<input type="checkbox" value="' + skill + '"> ' + skill;
      row.appendChild(label);
    });
  }

  if (cls === "Fighter") {
    extraBox.innerHTML += '<select id="cc-fighting-style" class="cc-input"></select>';
    fillSelect("cc-fighting-style", characterOptions.fighting_styles, "Fighting Style:");
  }

  if (cls === "Cleric") {
    extraBox.innerHTML +=
      '<select id="cc-domain" class="cc-input"></select>' +
      '<h3 class="cc-title">Cantrips</h3><div class="cc-check-row" id="cc-cantrips"></div>' +
      '<h3 class="cc-title">Prepared Spells</h3><div class="cc-check-row" id="cc-spells"></div>';

    fillSelect("cc-domain", characterOptions.cleric_domains, "Domain:");
    renderSpellChecks(characterOptions.cleric_cantrips, "cc-cantrips");
    renderSpellChecks(characterOptions.cleric_spells, "cc-spells");
  }

  if (cls === "Wizard") {
    extraBox.innerHTML +=
      '<h3 class="cc-title">Cantrips</h3><div class="cc-check-row" id="cc-cantrips"></div>' +
      '<h3 class="cc-title">Prepared Spells</h3><div class="cc-check-row" id="cc-spells"></div>';

    renderSpellChecks(characterOptions.wizard_cantrips, "cc-cantrips");
    renderSpellChecks(characterOptions.wizard_spells, "cc-spells");
  }

  if (cls === "Ranger") {
    extraBox.innerHTML +=
      '<select id="cc-favored-enemy" class="cc-input"></select>' +
      '<select id="cc-favored-terrain" class="cc-input" style="margin-left:.5rem"></select>';

    fillSelect("cc-favored-enemy", characterOptions.ranger_favored_enemies, "Favored Enemy:");
    fillSelect("cc-favored-terrain", characterOptions.ranger_favored_terrains, "Favored Terrain:");
  }
}

function showCharacterError(msg) {
  const box = $("cc-error");
  box.textContent = Array.isArray(msg) ? msg.join(" | ") : msg;
  box.classList.add("show");
}

function hideCharacterError() {
  $("cc-error").classList.remove("show");
}

function renderRaceChoices() {
  if (!characterOptions) return;
  var race = $("cc-race").value;
  var box = $("cc-race-choices");
  box.innerHTML = "";

  if (race === "Human") {
    box.innerHTML =
      '<h3 class="cc-title">Extra Skill Proficiency</h3>' +
      '<div class="load-msg">Humans gain one bonus skill proficiency.</div>' +
      '<select id="cc-human-extra-skill" class="cc-input"></select>';
    fillSelect("cc-human-extra-skill", characterOptions.all_skills, "Choose a skill:");
  }

  if (race === "Dwarf") {
    box.innerHTML =
      '<h3 class="cc-title">Tool Proficiency</h3>' +
      '<div class="load-msg">Dwarves are trained with one artisan tool.</div>' +
      '<select id="cc-dwarf-tool" class="cc-input"></select>';
    fillSelect("cc-dwarf-tool", characterOptions.dwarf_tools, "Choose a tool:");
  }
}

async function showCharacterCreator() {
  characterOptions = await api.characterOptions();

  fillSelect("cc-class", characterOptions.classes);
  fillSelect("cc-race", characterOptions.races);
  fillSelect("cc-background", characterOptions.backgrounds);
  fillSelect("cc-alignment", characterOptions.alignments);

  ["STR", "DEX", "CON", "INT", "WIS", "CHA"].forEach(function(ab, index) {
    fillSelect("cc-" + ab, characterOptions.standard_array, ab + ":");
    $("cc-" + ab).value = characterOptions.standard_array[index];
  });

  $("cc-class").addEventListener("change", renderClassChoices);
  $("cc-race").addEventListener("change", renderRaceChoices);
  renderClassChoices();
  renderRaceChoices();

  $("character-screen").classList.remove("gone");
  $("load-screen").classList.add("gone");
}

async function createCharacterFromForm() {
  hideCharacterError();

  const abilityScores = {};

  ["STR", "DEX", "CON", "INT", "WIS", "CHA"].forEach(function(ab) {
    abilityScores[ab] = parseInt($("cc-" + ab).value, 10);
  });

  const cls = $("cc-class").value;

  const payload = {
    character_name: $("cc-character-name").value.trim(),
    player_name: $("cc-player-name").value.trim(),
    class: cls,
    race: $("cc-race").value,
    background: $("cc-background").value,
    alignment: $("cc-alignment").value,
    ability_scores: abilityScores,
    chosen_class_skills: getCheckedValues("cc-skill-checks"),
    expertise: getCheckedValues("cc-expertise-checks"),

    age: $("cc-age").value.trim(),
    height: $("cc-height").value.trim(),
    weight: $("cc-weight").value.trim(),
    eyes: $("cc-eyes").value.trim(),
    skin: $("cc-skin").value.trim(),
    hair: $("cc-hair").value.trim(),
    personality_trait: $("cc-personality").value.trim(),
    ideal: $("cc-ideal").value.trim(),
    bond: $("cc-bond").value.trim(),
    flaw: $("cc-flaw").value.trim(),
    backstory: $("cc-backstory").value.trim(),
    allies_organisations: $("cc-allies").value.trim()
  };

  var race = $("cc-race").value;
  if (race === "Human" && $("cc-human-extra-skill")) {
    payload.human_extra_skill = $("cc-human-extra-skill").value;
  }
  if (race === "Dwarf" && $("cc-dwarf-tool")) {
    payload.dwarf_tool = $("cc-dwarf-tool").value;
  }

  if (cls === "Fighter") {
    payload.fighting_style = $("cc-fighting-style").value;
  }

  if (cls === "Cleric") {
    payload.domain = $("cc-domain").value;
    payload.cantrips_known = getCheckedValues("cc-cantrips");
    payload.spells_known = getCheckedValues("cc-spells");
  }

  if (cls === "Wizard") {
    payload.cantrips_known = getCheckedValues("cc-cantrips");
    payload.spells_known = getCheckedValues("cc-spells");
  }

  if (cls === "Ranger") {
    payload.favored_enemy = $("cc-favored-enemy").value;
    payload.favored_terrain = $("cc-favored-terrain").value;
  }

  try {
    await api.createCharacter(payload);
    $("character-screen").classList.add("gone");
    if (window.isMultiplayer && window.myRoomCode && socket) {
      var charResp = await api.character();
      socket.emit("player_ready", {
        room_code:   window.myRoomCode,
        player_name: window.myPlayerName || payload.player_name,
        character:   charResp.character
      });
      $("lobby-screen").classList.remove("gone");
    } else {
      await startFresh();
    }
  } catch(err) {
    showCharacterError(err.errors || err.error || "Could not create character.");
  }
}

// Typewriter
function typewrite(text, speed) {
  speed = speed || 22;
  const el = $("narrative-text");
  if (twTimer) clearInterval(twTimer);
  el.innerHTML = "";
  let i = 0;
  const cur = document.createElement("span");
  cur.className = "cursor";
  el.appendChild(cur);
  twTimer = setInterval(function() {
    if (i < text.length) {
      el.insertBefore(document.createTextNode(text[i++]), cur);
    } else {
      clearInterval(twTimer);
      twTimer = null;
      cur.remove();
    }
  }, speed);
}

// History
function addHistory(turnNum, text) {
  const log   = $("history-log");
  const e     = document.createElement("div");
  e.className = "h-entry";
  e.style.cursor = "pointer";
  e.title = "Click to collapse/expand";

  var turnSpan = document.createElement("span");
  turnSpan.className = "h-turn";
  var arrow = document.createElement("span");
  arrow.style.cssText = "font-size:.5rem;margin-right:.18rem;transition:transform .15s;display:inline-block";
  arrow.textContent = "▾";
  turnSpan.appendChild(arrow);
  turnSpan.appendChild(document.createTextNode("T" + turnNum));

  var textSpan = document.createElement("span");
  textSpan.className = "h-text";
  textSpan.textContent = text;

  e.appendChild(turnSpan);
  e.appendChild(textSpan);

  e.addEventListener("click", function() {
    var collapsed = textSpan.style.display === "none";
    textSpan.style.display = collapsed ? "" : "none";
    arrow.style.transform  = collapsed ? "" : "rotate(-90deg)";
  });

  log.appendChild(e);
  if (log.scrollHeight > 0) log.scrollTop = log.scrollHeight;
}

var _lootToastTimer = null;
function showLootToast(lootList) {
  if (!lootList || !lootList.length) return;
  var lines = lootList.map(function(l) {
    return (l.qty > 1 ? l.qty + "x " : "") + (l.name || l.item_id);
  });
  var toast = $("loot-toast");
  toast.textContent = "Loot: " + lines.join(", ");
  toast.classList.add("show");
  if (_lootToastTimer) clearTimeout(_lootToastTimer);
  _lootToastTimer = setTimeout(function() { toast.classList.remove("show"); }, 5000);
}

// XP bar + level badge + level-up notification
function updateXP(state, data) {
  var xp      = state.xp || 0;
  var level   = state.level || 1;
  var toNext  = state.xp_to_next;
  var thresholds = {1:0, 2:300, 3:900, 4:2700};
  var currentFloor = thresholds[level] || 0;
  var pct = toNext ? Math.min(100, (xp - currentFloor) / (toNext - currentFloor) * 100) : 100;

  $("level-badge").textContent = "Level " + level;
  $("xp-fill").style.width     = pct + "%";
  $("xp-val").textContent      = xp + " / " + (toNext || "MAX");

  var bar = $("levelup-bar");
  if (data && data.level_up) {
    var feats = (data.new_features || []).join(" | ");
    bar.textContent = "LEVEL UP! You are now Level " + (data.new_level || level) + (feats ? " — " + feats : "");
    bar.classList.add("show");
    setTimeout(function() { bar.classList.remove("show"); }, 7000);
  } else {
    bar.classList.remove("show");
  }
}

// Mini-map
var _lastDungeonMap = [];
var _lastCurrentRoomId = null;

function renderMiniMap(rooms, currentRoomId) {
  _lastDungeonMap    = rooms || [];
  _lastCurrentRoomId = currentRoomId || null;
  var wrap        = $("minimap-wrap");
  var grid        = $("minimap-grid");
  var placeholder = $("minimap-placeholder");
  if (!rooms || !rooms.length) {
    wrap.style.display = "none";
    if (placeholder) placeholder.style.display = "block";
    return;
  }
  wrap.style.display = "block";
  if (placeholder) placeholder.style.display = "none";
  grid.innerHTML = "";

  var currentRoom = rooms.find(function(r) { return r.is_current || r.id === currentRoomId; });
  var adjacentIds = currentRoom ? (currentRoom.exits || []) : [];

  rooms.forEach(function(room) {
    var col = (room.grid_col || 0) + 1;
    var row = (room.grid_row || 0) + 1;
    var isCurrent  = room.is_current || room.id === currentRoomId;
    var isAdjacent = adjacentIds.indexOf(room.id) !== -1;
    var cls = "room-tile";
    if (isCurrent)  cls += " current";
    else if (isAdjacent) cls += " adjacent" + (room.visited ? " visited" : "");
    else if (room.visited) cls += " visited";
    if (room.cleared && !isCurrent) cls += " cleared";
    if (room.type) cls += " type-" + room.type;

    var tile = document.createElement("div");
    tile.className = cls;
    tile.style.gridColumn = col;
    tile.style.gridRow    = row;

    if (!room.visited && !isCurrent) {
      tile.innerHTML = '<span class="room-ico">?</span>';
    } else {
      var typeLabel = room.cleared ? room.type + " ✓" : room.type;
      tile.innerHTML =
        '<span class="room-ico">' + (room.icon || "?") + '</span>' +
        '<span class="room-name">' + room.name + '</span>' +
        '<span class="room-type">' + typeLabel + '</span>';
    }

    if (isAdjacent && !busy) {
      (function(rid) {
        tile.addEventListener("click", function() { moveToRoom(rid); });
      })(room.id);
    }
    grid.appendChild(tile);
  });
}

async function moveToRoom(roomId) {
  if (busy) return;
  setBusy(true);
  var prevTurn = turnCount;
  try {
    var resp = await fetch("/api/dungeon/move", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({room_id: roomId})
    });
    var data = await resp.json();
    if (data.error) { showError(data.error); setBusy(false); return; }
    turnCount = (data.state && data.state.turn) ? data.state.turn - 1 : turnCount + 1;
    applyData(data, prevTurn);
  } catch(e) {
    showError("Could not move to room.");
  }
  setBusy(false);
}

async function submitPuzzle(roomId) {
  var input  = $("puzzle-input");
  var answer = input ? input.value.trim() : "";
  if (!answer) return;
  if (busy) return;
  setBusy(true);
  var prevTurn = turnCount;
  try {
    var resp = await fetch("/api/dungeon/puzzle", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({room_id: roomId, answer: answer})
    });
    var data = await resp.json();
    if (data.error) { showError(data.error); setBusy(false); return; }
    turnCount = (data.state && data.state.turn) ? data.state.turn - 1 : turnCount + 1;
    applyData(data, prevTurn);
  } catch(e) {
    showError("Puzzle submission failed.");
  }
  setBusy(false);
}

function renderExploreButtons(state, sec) {
  var currentRoom = null;
  for (var i = 0; i < _lastDungeonMap.length; i++) {
    if (_lastDungeonMap[i].id === _lastCurrentRoomId) { currentRoom = _lastDungeonMap[i]; break; }
  }

  var html = '<div class="choice-btns cols2">';

  if (currentRoom && currentRoom.exits && currentRoom.exits.length) {
    currentRoom.exits.forEach(function(exitId) {
      var dest = null;
      for (var j = 0; j < _lastDungeonMap.length; j++) {
        if (_lastDungeonMap[j].id === exitId) { dest = _lastDungeonMap[j]; break; }
      }
      if (!dest) return;
      var label = dest.cleared
        ? dest.name + " <span style='font-size:.75em;opacity:.6'>(cleared)</span>"
        : "Move to " + dest.name;
      html += '<button class="cbtn cbtn-move" onclick="moveToRoom(\'' + dest.id + '\')">' + label + '</button>';
    });
  }

  if (currentRoom && currentRoom.type === "Rest") {
    html += '<button class="cbtn" onclick="doChoice(\'short_rest\')">Short Rest</button>';
    html += '<button class="cbtn" onclick="doChoice(\'long_rest\')">Long Rest</button>';
    html += '<button class="cbtn cbtn-item" onclick="showShop()" style="grid-column:span 2;">&#128722; Visit Shop</button>';
  }

  if (currentRoom && currentRoom.npcs && currentRoom.npcs.length) {
    currentRoom.npcs.forEach(function(npcId) {
      var label = npcId.replace(/_/g, ' ').replace(/\b\w/g, function(c){ return c.toUpperCase(); });
      html += '<button class="cbtn cbtn-npc" style="grid-column:span 2;" onclick="openNpc(\'' + npcId + '\')">&#128172; Talk to ' + label + '</button>';
    });
  }

  html += '</div>';

  // Utility shortcuts (Inventory + Character Sheet)
  html += '<div class="choice-btns cols2" style="margin-top:.4rem">';
  html += '<button class="cbtn cbtn-search" onclick="switchRightTab(\'inv\')">' +
    '<span class="ico">&#127869;</span>Inventory<small>pack &amp; currency</small>' +
  '</button>';
  html += '<button class="cbtn cbtn-search" onclick="switchRightTab(\'sheet\')">' +
    '<span class="ico">&#128196;</span>Character Sheet<small>stats &amp; features</small>' +
  '</button>';
  html += '</div>';

  if (currentRoom && currentRoom.type === "Puzzle" && !currentRoom.cleared) {
    var puzzle = currentRoom.puzzle || {};
    html += '<div class="puzzle-box" style="margin-top:10px;padding:10px;background:rgba(255,255,255,.05);border-radius:6px;">';
    html += '<p style="margin:0 0 8px;font-size:.9em;color:#e2c97e;">' + (puzzle.prompt || "Solve the puzzle:") + '</p>';
    html += '<input id="puzzle-input" type="text" placeholder="Your answer..." style="width:100%;box-sizing:border-box;padding:6px 8px;background:#1a1a2e;color:#e0e0ff;border:1px solid #444;border-radius:4px;font-size:.9em;" />';
    html += '<button class="cbtn" style="margin-top:6px;width:100%;" onclick="submitPuzzle(\'' + currentRoom.id + '\')">Submit Answer</button>';
    html += '</div>';
  }

  sec.innerHTML = html;
}

// HP bars shared scale during combat so bars reflect the real HP disparity
function updateHPBars(playerHp, playerMaxHp, enemy) {
  const enemyAlive = enemy && enemy.hp > 0;
  const sharedMax  = enemyAlive ? Math.max(playerMaxHp, enemy.max_hp) : playerMaxHp;

  const playerPct = Math.max(0, Math.min(100, playerHp / sharedMax * 100));
  $("hp-fill").style.width = playerPct + "%";
  $("hp-val").textContent  = playerHp + " / " + playerMaxHp;

  setEnemyBar(enemy, sharedMax);
}

function setHP(hp, maxHp) {
  const pct = Math.max(0, Math.min(100, hp / maxHp * 100));
  $("hp-fill").style.width = pct + "%";
  $("hp-val").textContent  = hp + " / " + maxHp;
}

function setEnemyBar(enemy, sharedMax) {
  const row = $("enemy-row");
  if (enemy && enemy.hp > 0) {
    row.classList.remove("hidden");
    const scale = sharedMax || enemy.max_hp;
    const pct   = Math.max(0, enemy.hp / scale * 100);
    $("enemy-fill").style.width = pct + "%";
    $("enemy-name").textContent = enemy.name;
    $("enemy-val").textContent  = enemy.hp + " / " + enemy.max_hp;
    inCombat = true;
  } else {
    row.classList.add("hidden");
    inCombat = false;
  }
}

function renderInitiative(combat) {
  const strip = $("initiative-strip");
  strip.innerHTML = "";

  if (!combat || !combat.active || !combat.turn_order || !combat.turn_order.length) {
    strip.classList.remove("active");
    return;
  }

  strip.classList.add("active");

  combat.turn_order.forEach(function(actor) {
    const card = document.createElement("div");
    card.className = "init-card " + actor.type;

    if (combat.current_actor && combat.current_actor.id === actor.id) {
      card.className += " current";
    }

    card.textContent =
      actor.name +
      " · Init " +
      actor.initiative_total;

    strip.appendChild(card);
  });
}

function isEnemyTurn(combat) {
  return !!(
    combat &&
    combat.active &&
    combat.current_actor &&
    combat.current_actor.type === "enemy"
  );
}

// Action chips only shown when NOT in combat (avoids duplicating Fight/Sneak/Parley)
function renderChips(actions, enemyAlive) {
  const box = $("action-chips");
  box.innerHTML = "";
  if (enemyAlive || !actions || !actions.length) return;
  actions.forEach(function(a) {
    const btn     = document.createElement("button");
    btn.className = "chip";
    btn.textContent = a;
    btn.onclick   = function() {
      $("player-input").value = a;
      $("player-input").focus();
    };
    box.appendChild(btn);
  });
}

// Spell buttons
function renderSpells(availableSpells, spellSlots) {
  var sec = $("spell-section");
  if (!sec) return;
  if (!availableSpells || availableSpells.length === 0) {
    sec.innerHTML = "";
    return;
  }

  var slotHtml = "";
  var slotKeys = ["1st", "2nd", "3rd"];
  slotKeys.forEach(function(sk) {
    var slot = spellSlots[sk];
    if (!slot) return;
    var bubbles = "";
    for (var i = 0; i < slot.total; i++) {
      bubbles += '<span class="slot-bubble' + (i < slot.remaining ? " slot-full" : "") + '">&#9679;</span>';
    }
    slotHtml += '<span class="slot-group">' + sk + ': ' + bubbles + '</span>';
  });

  var cols = Math.min(availableSpells.length, 3);
  var btns = availableSpells.map(function(name) {
    return '<button class="cbtn cbtn-spell" onclick="castSpell(\'' + name.replace(/'/g, "\\'") + '\')">' +
      '<span class="ico">&#10024;</span>' + name +
    '</button>';
  }).join("");

  sec.innerHTML =
    (slotHtml ? '<div class="slot-tracker">' + slotHtml + '</div>' : '') +
    '<div class="choice-label">Spells</div>' +
    '<div class="choice-btns cols' + cols + '">' + btns + '</div>';
}

async function castSpell(spellName) {
  setBusy(true);
  prevTurn = spellName;
  try {
    const resp = await fetch("/api/action", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({choice: "cast_spell", spell_name: spellName})
    });
    const data = await resp.json();
    applyData(data);
  } catch(e) {
    showError("Spell casting failed.");
  } finally {
    setBusy(false);
  }
}

// Choice buttons
function renderChoices(state) {
  const sec   = $("choice-section");
  const enemy = state.enemy;
  const alive = enemy && enemy.hp > 0;
  const playerDown = state.hp <= 0;
  if (playerDown) {
    sec.innerHTML =
      '<div class="choice-label">You Are Down</div>' +
      '<div class="choice-btns cols1">' +
        '<button class="cbtn cbtn-death" onclick="doChoice(\'death_save\')">' +
          '<span class="ico">&#9760;</span>Death Save' +
          '<small>d20: 10+ success, 1-9 failure</small>' +
        '</button>' +
      '</div>';
    return;
  }

    if (alive) {
    const combat = window._lastCombatState || {};
    const combatIsPlayerTurn = !combat.active || (combat.current_actor && combat.current_actor.type === "player");
    const isPlayerTurn = combatIsPlayerTurn && (!window.isMultiplayer || window.myTurn);
    var dis = !isPlayerTurn ? 'disabled' : '';
    var hasSpells = _lastAvailableSpells.length > 0;
    var hasSlots  = hasSpells && Object.values(_lastSpellSlots).some(function(s){ return s.remaining > 0; });
    sec.innerHTML =
  '<div class="choice-label">Choose Your Action</div>' +
  '<div class="choice-btns cols3">' +

    '<button class="cbtn cbtn-fight" onclick="doChoice(\'fight\')" ' + dis + '>' +
      '<span class="ico">&#9876;</span>Attack' +
      '<small>d20 + bonus vs AC</small>' +
    '</button>' +

    '<button class="cbtn cbtn-spell" onclick="scrollToCast()" ' + (!isPlayerTurn || !hasSlots ? 'disabled' : '') + '>' +
      '<span class="ico">&#10024;</span>Cast Spell' +
      '<small>' + (hasSpells ? _lastAvailableSpells.length + ' spell(s)' : 'no spells') + '</small>' +
    '</button>' +

    '<button class="cbtn cbtn-dodge" onclick="doChoice(\'dodge\')" ' + dis + '>' +
      '<span class="ico">&#128737;</span>Dodge' +
      '<small>attacks with disadvantage</small>' +
    '</button>' +

    '<button class="cbtn cbtn-dash" onclick="doChoice(\'disengage\')" ' + dis + '>' +
      '<span class="ico">&#8617;</span>Disengage' +
      '<small>no opportunity attacks</small>' +
    '</button>' +

    '<button class="cbtn cbtn-dash" onclick="doChoice(\'dash\')" ' + dis + '>' +
      '<span class="ico">&#10140;</span>Dash' +
      '<small>double movement</small>' +
    '</button>' +

    '<button class="cbtn cbtn-item" onclick="openItemPicker()" ' + dis + '>' +
      '<span class="ico">&#127864;</span>Use Item' +
      '<small>potion or consumable</small>' +
    '</button>' +

    '<button class="cbtn cbtn-help" onclick="doChoice(\'bonus_action\')" ' + dis + ' style="grid-column:span 3">' +
      '<span class="ico">&#10022;</span>Bonus Action' +
      '<small>class ability or off-hand attack</small>' +
    '</button>' +

  '</div>';
    } else if (!state.boss_cleared) {
    renderExploreButtons(state, sec);
  } else if (!state.room_searched) {
    sec.innerHTML =
      '<div class="choice-btns cols2">' +
        '<button class="cbtn cbtn-search" onclick="doFree(\'I search the room carefully for anything useful.\')">' +
          '<span class="ico">&#128269;</span>Search Room' +
        '</button>' +
        (state.floor < 4
          ? '<button class="cbtn cbtn-down" onclick="doFree(\'I descend to the next floor.\')">' +
              '<span class="ico">&#8595;</span>Descend</button>'
          : '') +
      '</div>';
  } else if (state.floor < 4) {
    sec.innerHTML =
      '<div class="choice-btns cols1">' +
        '<button class="cbtn cbtn-down" onclick="doFree(\'I descend to the next floor.\')">' +
          '<span class="ico">&#8595;</span>Descend to Floor ' + (state.floor + 1) +
        '</button>' +
      '</div>';
  } else {
    sec.innerHTML = "";
  }
}

// Dice overlay
function startDiceAnimation(type) {
  const labels = { sneak: "Stealth Check", talk: "Persuasion Check", death_save: "Death Saving Throw"};
  $("dice-type-label").textContent = labels[type] || "Ability Check";
  $("dice-dc-row").innerHTML = "&nbsp;";
  $("dice-verdict").textContent = "";
  $("dice-verdict").className = "dice-verdict";
  $("dice-num").textContent = "?";
  $("dice-num").className = "dice-num";
  $("dice-d20").className = "dice-d20";
  $("dice-wrap").className = "dice-d20-wrap";
  $("dice-overlay").classList.add("active");

  // Roll random numbers rapidly while waiting
  diceTimer = setInterval(function() {
    $("dice-num").textContent = Math.floor(Math.random() * 20) + 1;
  }, 60);
}

function resolveDice(dice) {
  if (diceTimer) { clearInterval(diceTimer); diceTimer = null; }
  if (!dice) { hideDice(); return Promise.resolve(); }

  return new Promise(function(resolve) {
    const cls = dice.success ? "success" : "fail";
    $("dice-num").textContent = dice.roll;
    $("dice-num").className   = "dice-num " + cls;
    $("dice-d20").className   = "dice-d20 " + cls;
    $("dice-wrap").className  = "dice-d20-wrap " + cls;
    $("dice-dc-row").innerHTML = "Roll: <span>" + dice.roll + "</span> &nbsp;|&nbsp; DC: <span>" + dice.dc + "</span>";
    const vrd = $("dice-verdict");
    vrd.textContent = dice.success ? "Success!" : "Failed!";
    vrd.className   = "dice-verdict " + cls;

    setTimeout(function() {
      hideDice();
      resolve();
    }, 2200);
  });
}

function hideDice() {
  if (diceTimer) { clearInterval(diceTimer); diceTimer = null; }
  $("dice-overlay").classList.remove("active");
}

// UI update
function applyData(data, prevTurn) {
  if (data.error) { showError(data.error); return; }
  hideError();
  window._lastCombatState = data.combat || {};
  const prev = $("narrative-text").innerText.replace(/\s+/g, " ").trim();
  if (prev && prev !== "The dungeon awaits your fate..." && prevTurn) {
    addHistory(prevTurn, prev);
  }

  const narrative = data.narrative || data.narrative_text || "";
  _lastBroadcastNarrative = narrative;
  typewrite(narrative);
  const maxHp = data.state.max_hp || 100;
  updateHPBars(data.hp, maxHp, data.state.enemy);
  $("floor-badge").textContent = "Floor " + data.state.floor + " / 4";
  $("gold-badge").textContent  = (data.state.gold || 0) + " Gold";
  updateXP(data.state, data);
  if (data.dungeon_map) { renderMiniMap(data.dungeon_map, data.state.current_room_id); }
  _lastAvailableSpells = data.available_spells || [];
  _lastSpellSlots      = data.spell_slots      || {};
  renderChoices(data.state);
  if (data.loot_dropped && data.loot_dropped.length) { showLootToast(data.loot_dropped); }
  renderSpells(_lastAvailableSpells, _lastSpellSlots);
  renderInitiative(data.combat);

  const enemyAlive = !!(data.state.enemy && data.state.enemy.hp > 0);
  renderChips(data.actions || [], enemyAlive);

  if (data.ending) {
    setTimeout(function() { showEnding(data.ending); }, 2600);
  }
  if (isEnemyTurn(data.combat) && (!window.isMultiplayer || window.isHost)) {
    const textToRead = narrative;
    const readingDelay = Math.max(4500, Math.min(12000, textToRead.length * 35));
    setTimeout(resolveEnemyTurnFromServer, readingDelay);
  }

  var diceRolls = data.dice_rolls || data.dice_rolls_this_turn;
  if (diceRolls && diceRolls.length) showDiceStrip(diceRolls);
  else if (data.dice) {
    // Single d20 from sneak/talk/death_save — also show in strip
    showDiceStrip([{ die: "d20", result: data.dice.roll, purpose: data.dice.type || "" }]);
  } else {
    showDiceStrip([]);
  }

  updateSheetHP(data.hp, data.state && data.state.max_hp);

  if (data.level_up || !window._lastCharacter) {
    loadAndRenderCharSheet();
  }

  if (!$("tab-inv").classList.contains("gone")) {
    refreshPanelInventory();
  }
}

// Busy state
function setBusy(val) {
  busy = val;
  $("send-btn").disabled     = val;
  $("player-input").disabled = val;
  $("thinking").className    = "thinking" + (val ? " show" : "");
  document.querySelectorAll(".cbtn").forEach(function(b) { b.disabled = val; });
  document.querySelectorAll(".chip").forEach(function(b) { b.disabled = val; });
}

// Error
function showError(msg) {
  const bar = $("error-bar");
  bar.textContent = msg;
  bar.classList.add("show");
}
function hideError() { $("error-bar").classList.remove("show"); }

// Send action (freeform text or Fight)
async function doAction(msg, choice) {
  if (busy) return;
  const input = $("player-input");
  const text  = msg || input.value.trim();
  if (!text && !choice) return;
  input.value = "";
  const prevTurn = turnCount;
  setBusy(true);
  try {
    const data = await api.action({message: text, choice: choice});
    turnCount = (data.state && data.state.turn) ? data.state.turn - 1 : turnCount + 1;
    applyData(data, prevTurn);
  } catch(err) {
    showError("Could not reach the dungeon master. Check that the server is running.");
  }
  setBusy(false);
}

// Choice with dice overlay for Sneak / Parley
async function doChoice(type) {
  if (busy) return;
  setBusy(true);
  const prevTurn = turnCount;

  if (type === "sneak" || type === "talk" || type === "death_save") {
    startDiceAnimation(type);
  }

  try {
    const data = await api.action({message: "", choice: type});
    if (data.error) {
      hideDice();
      showError(data.error);
      setBusy(false);
      return;
    }
    // Show dice result (waits 2.2s), then narrative
    if (data.dice) {
      await resolveDice(data.dice);
    } else {
      hideDice();
    }
    turnCount = (data.state && data.state.turn) ? data.state.turn - 1 : turnCount + 1;
    applyData(data, prevTurn);
  } catch(err) {
    hideDice();
    showError("Could not reach the dungeon master. Check that the server is running.");
  }
  setBusy(false);
}

function doFree(msg) { doAction(msg, null); }

function scrollToCast() {
  var sec = $("spell-section");
  if (sec) sec.scrollIntoView({behavior:"smooth", block:"nearest"});
}

async function resolveEnemyTurnFromServer() {
  if (busy) return;

  setBusy(true);
  const prevTurn = turnCount;

  try {
    const data = await api.enemyTurn();

    if (data.error) {
      showError(data.error);
      setBusy(false);
      return;
    }

    turnCount = (data.state && data.state.turn) ? data.state.turn - 1 : turnCount + 1;
    applyData(data, prevTurn);

  } catch(err) {
    showError("Could not resolve enemy turn. Check that the server is running.");
  }

  setBusy(false);
}

// Ending
function showEnding(e) {
  $("ending-title").textContent = e.title    || "";
  $("ending-sub").textContent   = e.subtitle || "";
  $("ending-text").textContent  = e.text     || "";
  $("ending-screen").classList.add("active");
}

// Item picker (combat)
async function openItemPicker() {
  try {
    const resp = await fetch("/api/combat_items");
    const data = await resp.json();
    const list = $("item-picker-list");
    list.innerHTML = "";
    const usable = (data.items || []).filter(function(i) { return i.quantity > 0; });
    if (!usable.length) {
      list.innerHTML = '<p class="item-picker-empty">Your pack has no usable items.</p>';
    } else {
      usable.forEach(function(item) {
        const btn = document.createElement("button");
        btn.className = "item-picker-btn";
        btn.innerHTML = item.name + ' <span style="opacity:0.6">x' + item.quantity + '</span>' +
          (item.description ? '<br><small style="font-family:serif;opacity:0.6">' + item.description + '</small>' : '');
        btn.addEventListener("click", function() {
          $("item-picker-overlay").classList.remove("active");
          executeUseItem(item.id || item.name);
        });
        list.appendChild(btn);
      });
    }
    $("item-picker-overlay").classList.add("active");
  } catch(e) {
    showError("Could not load items.");
  }
}

async function executeUseItem(itemId) {
  if (busy) return;
  setBusy(true);
  const prevTurn = turnCount;
  try {
    const data = await fetch("/api/action", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({choice: "use_item", item_id: itemId})
    }).then(function(r) { return r.json(); });
    if (data.error) { showError(data.error); setBusy(false); return; }
    turnCount = (data.state && data.state.turn) ? data.state.turn - 1 : turnCount + 1;
    applyData(data, prevTurn);
  } catch(err) {
    showError("Could not use item.");
  }
  setBusy(false);
}

// Inventory
async function showInventory() {
  try {
    const data = await api.inv();
    const list  = $("inv-list");
    list.innerHTML = "";
    const items = data.items || [];
    if (!items.length) {
      list.innerHTML = '<p class="inv-empty">Your pack is empty.</p>';
    } else {
      const NON_EQUIP = new Set(["consumable","utility","ammo","tool","book",""]);
      const equipped   = items.filter(function(i){ return i.equipped; });
      const unequipped = items.filter(function(i){ return !i.equipped; });

      function makeRow(item) {
        const d = document.createElement("div");
        d.className = "inv-item";
        const canEquip = !NON_EQUIP.has(item.type || "");
        const typeBadge = item.type ? '<span class="inv-badge type">' + item.type + '</span>' : '';
        const eqBadge   = item.equipped ? '<span class="inv-badge equipped">equipped</span>' : '';
        const qty        = (item.quantity > 1 || NON_EQUIP.has(item.type)) ? ' <span class="inv-qty">x' + item.quantity + '</span>' : '';
        d.innerHTML =
          '<div class="inv-info">' +
            '<div class="inv-name">' + item.name + qty + typeBadge + eqBadge + '</div>' +
            '<div class="inv-desc">' + (item.description || '') + '</div>' +
          '</div>';
        if (canEquip) {
          const btn = document.createElement("button");
          btn.className = "inv-equip-btn" + (item.equipped ? " unequip" : "");
          btn.textContent = item.equipped ? "Unequip" : "Equip";
          btn.addEventListener("click", async function() {
            btn.disabled = true;
            try {
              const r = await fetch("/api/inventory/equip", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({item_id: item.id, equipped: !item.equipped})
              });
              const res = await r.json();
              if (res.error) { showError(res.error); btn.disabled = false; return; }
              if (res.new_ac !== undefined) {
                $("gold-badge") && ($("gold-badge").textContent = ($("gold-badge").textContent));
              }
              showInventory();
            } catch(e) { showError("Equip failed."); btn.disabled = false; }
          });
          d.appendChild(btn);
        }
        list.appendChild(d);
      }

      if (equipped.length) {
        const lbl = document.createElement("div");
        lbl.className = "inv-section-label";
        lbl.textContent = "Equipped";
        list.appendChild(lbl);
        equipped.forEach(makeRow);
      }
      if (unequipped.length) {
        const lbl = document.createElement("div");
        lbl.className = "inv-section-label";
        lbl.textContent = "Pack";
        list.appendChild(lbl);
        unequipped.forEach(makeRow);
      }
    }
    $("inv-overlay").classList.add("active");
  } catch(e) {
    showError("Could not load inventory.");
  }
}

// Shop
async function showShop() {
  try {
    const data = await fetch("/api/shop").then(function(r){ return r.json(); });
    const list = $("shop-list");
    const goldDisplay = $("shop-gold-display");
    goldDisplay.textContent = "Your gold: " + (data.gold || 0) + " gp";
    list.innerHTML = "";
    if (!data.items || !data.items.length) {
      list.innerHTML = '<p class="inv-empty">Nothing for sale here.</p>';
    } else {
      data.items.forEach(function(item) {
        const d = document.createElement("div");
        d.className = "shop-item";
        const canAfford = (data.gold || 0) >= item.cost;
        d.innerHTML =
          '<div class="shop-info">' +
            '<div class="shop-name">' + item.name + '</div>' +
            '<div class="shop-cost">' + item.cost + ' gp</div>' +
            '<div class="shop-desc">' + (item.description || '') + '</div>' +
          '</div>';
        const btn = document.createElement("button");
        btn.className = "shop-buy-btn";
        btn.textContent = "Buy";
        btn.disabled = !canAfford;
        btn.addEventListener("click", async function() {
          btn.disabled = true;
          try {
            const r = await fetch("/api/shop/buy", {
              method: "POST",
              headers: {"Content-Type":"application/json"},
              body: JSON.stringify({item_id: item.id})
            });
            const res = await r.json();
            if (res.error) { showError(res.error); btn.disabled = !canAfford; return; }
            $("gold-badge").textContent = (res.gold_remaining || 0) + " Gold";
            showShop();
          } catch(e) { showError("Purchase failed."); btn.disabled = !canAfford; }
        });
        d.appendChild(btn);
        list.appendChild(d);
      });
    }
    $("shop-overlay").classList.add("active");
  } catch(e) {
    showError("Could not load shop.");
  }
}

// Reset button
async function startFresh(doReset) {
  $("ending-screen").classList.remove("active");
  $("load-screen").classList.remove("gone");
  $("load-msg").textContent = "Clearing dungeon state...";
  turnCount = 0;
  $("history-log").innerHTML = "";
  hideError();
  try {
    if (doReset) await api.reset();
    $("load-msg").textContent = "The dungeon is being prepared...";
    const data = await api.new();
    $("load-screen").classList.add("gone");
    if (data.error) { showError(data.error); return; }
    turnCount = 1;
    applyData(data, null);
    loadAndRenderCharSheet();
  } catch(e) {
    $("load-screen").classList.add("gone");
    showError("Failed to start. Is the server running? Check the terminal for errors.");
  }
}

// Hard reset
function hardReset() {
  var m = $("reset-modal");
  if (m) m.style.display = "flex";
}
function closeResetModal() {
  var m = $("reset-modal");
  if (m) m.style.display = "none";
}
async function confirmReset() {
  closeResetModal();
  await startFresh(true);
}

// Load messages
function cycleLoadMsg() {
  const msgs = [
    "The dungeon stirs...",
    "Summoning the dungeon master...",
    "Ancient torches flicker...",
    "The gate creaks open...",
  ];
  let i = 0;
  return setInterval(function() {
    i = (i + 1) % msgs.length;
    const el = $("load-msg");
    if (el) el.textContent = msgs[i];
  }, 3000);
}

async function _initGame() {
  $("load-screen").classList.remove("gone");
  $("load-msg").textContent = "The dungeon stirs...";
  const msgTimer = cycleLoadMsg();
  try {
    const character = await api.character();
    if (!character.exists) {
      clearInterval(msgTimer);
      $("load-screen").classList.add("gone");
      if (window.myPlayerName) $("cc-player-name").value = window.myPlayerName;
      await showCharacterCreator();
      return;
    }
    const resume = await api.resume();
    clearInterval(msgTimer);
    if (resume.active) {
      $("load-screen").classList.add("gone");
      turnCount = resume.state.turn || 1;
      applyData({narrative: resume.narrative, hp: resume.hp, actions: resume.actions || [], state: resume.state, ending: null}, null);
      if (window.isMultiplayer) {
        var psec = $("party-section");
        if (psec) psec.style.display = "block";
        $("chat-box").style.display  = "block";
      }
      loadAndRenderCharSheet();
    } else {
      $("load-screen").classList.add("gone");
      await startFresh();
    }
  } catch(e) {
    clearInterval(msgTimer);
    $("load-screen").classList.add("gone");
    await showCharacterCreator();
  }
}

async function init() {
  $("load-screen").classList.add("gone");
  $("character-screen").classList.add("gone");
}

// History toggle
var _histToggle = $("history-toggle");
if (_histToggle) _histToggle.addEventListener("click", function() {
  historyOpen = !historyOpen;
  $("history-log").classList.toggle("open", historyOpen);
  var arr = $("toggle-arrow");
  if (arr) arr.classList.toggle("open", historyOpen);
});

// Events
$("player-input").addEventListener("keydown", function(e) {
  if (e.key === "Enter" && !busy) doAction("", null);
});
$("send-btn").addEventListener("click",   function() { doAction("", null); });
var _resetBtn = $("reset-btn");
if (_resetBtn) _resetBtn.addEventListener("click", function() { hardReset(); });
$("inv-btn").addEventListener("click", function() { switchRightTab("inv"); });
$("close-inv").addEventListener("click",  function() { $("inv-overlay").classList.remove("active"); });
$("inv-overlay").addEventListener("click", function(e) {
  if (e.target === $("inv-overlay")) $("inv-overlay").classList.remove("active");
});
$("close-item-picker").addEventListener("click", function() { $("item-picker-overlay").classList.remove("active"); });
$("item-picker-overlay").addEventListener("click", function(e) {
  if (e.target === $("item-picker-overlay")) $("item-picker-overlay").classList.remove("active");
});
$("close-shop").addEventListener("click", function() { $("shop-overlay").classList.remove("active"); });
$("shop-overlay").addEventListener("click", function(e) {
  if (e.target === $("shop-overlay")) $("shop-overlay").classList.remove("active");
});
$("new-btn").addEventListener("click", function() {
  if (confirm("Start a new game? All progress will be lost.")) startFresh();
});
$("restart-btn").addEventListener("click", startFresh);

$("cc-create-btn").addEventListener("click", createCharacterFromForm);

// Right panel tab switching
function switchRightTab(tab) {
  document.querySelectorAll(".r-tab").forEach(function(b) { b.classList.remove("active"); });
  document.querySelectorAll(".r-tab-pane").forEach(function(p) { p.classList.add("gone"); });
  var btn  = document.querySelector('.r-tab[data-tab="' + tab + '"]');
  var pane = $("tab-" + tab);
  if (btn)  btn.classList.add("active");
  if (pane) pane.classList.remove("gone");
  if (tab === "inv") refreshPanelInventory();
  // Scroll right panel into view on mobile
  var panel = document.querySelector(".panel-right");
  if (panel && window.innerWidth <= 768) panel.scrollIntoView({behavior:"smooth"});
}

document.querySelectorAll(".r-tab").forEach(function(btn) {
  btn.addEventListener("click", function() { switchRightTab(btn.dataset.tab); });
});

// Dice roll strip
function showDiceStrip(rolls) {
  var el = $("dice-roll-strip");
  if (!el) return;
  if (!rolls || !rolls.length) { el.style.display = "none"; return; }
  el.style.display = "flex";
  el.innerHTML = '<span class="dc-die" style="margin-right:.2rem">Rolls:</span>' +
    rolls.map(function(r) {
      var nat = r.result === 20 ? " dc-nat20" : r.result === 1 ? " dc-nat1" : "";
      return '<div class="dice-chip"><span class="dc-die">' + (r.die || "d?") + '&nbsp;</span>' +
        '<span class="dc-val' + nat + '">' + r.result + '</span>' +
        (r.purpose ? '<span class="dc-die">&nbsp;(' + r.purpose + ')</span>' : '') + '</div>';
    }).join("");
}

// Character sheet renderer
window._lastCharacter = null;

function renderCharacterSheet(char) {
  var el = $("char-sheet-content");
  if (!el) return;
  if (!char || !char.identity) { el.innerHTML = '<p class="cs-empty">No character loaded.</p>'; return; }

  var id    = char.identity    || {};
  var ab    = char.ability_scores || {};
  var cm    = char.combat       || {};
  var st    = char.saving_throws || {};
  var sk    = char.skills        || {};
  var sp    = char.spellcasting  || {};
  var feats = char.class_features || [];
  var traits= char.racial_traits  || [];
  var profs = char.proficiencies  || {};
  var atks  = char.attacks        || [];

  function abMod(k) {
    var m = (ab[k] || {}).modifier || 0;
    return m >= 0 ? "+" + m : "" + m;
  }
  function profDot(proficient, expertise) {
    if (expertise)  return '<span class="cs-dot expertise">&#9679;</span>';
    if (proficient) return '<span class="cs-dot proficient">&#9679;</span>';
    return '<span class="cs-dot">&#9675;</span>';
  }
  function fmtMod(n) { return n >= 0 ? "+" + n : "" + n; }

  var h = "";

  // Identity
  h += '<div class="cs-identity">';
  h += '<div class="cs-char-name">' + (id.character_name || "—") + '</div>';
  if (id.player_name) h += '<div class="cs-char-sub" style="color:var(--gold-dim);font-size:.72rem">Player: ' + id.player_name + '</div>';
  h += '<div class="cs-char-sub">' + (id.class || "?") + " • " + (id.race || "?") + " • Level " + (id.level || 1) + '</div>';
  h += '<div class="cs-char-sub">' + (id.background || "") + (id.alignment ? " • " + id.alignment : "") + '</div>';
  h += '</div>';

  // Inspiration + prof bonus
  h += '<div class="cs-row-insp">';
  if (id.inspiration) h += '<span class="cs-badge gold">&#9733; Inspired</span>';
  h += '<span class="cs-badge">Prof +'  + (id.prof_bonus || 2) + '</span>';
  h += '<span class="cs-badge">XP ' + (id.xp || 0) + '</span>';
  h += '</div>';

  // Ability scores
  h += '<div class="cs-section-label">Ability Scores</div>';
  h += '<div class="cs-ab-row">';
  ["STR","DEX","CON","INT","WIS","CHA"].forEach(function(k) {
    var a = ab[k] || {}; var mod = fmtMod(a.modifier || 0);
    h += '<div class="cs-ab">' +
      '<div class="cs-ab-key">' + k + '</div>' +
      '<div class="cs-ab-mod">' + mod + '</div>' +
      '<div class="cs-ab-score">' + (a.score || 0) + '</div>' +
    '</div>';
  });
  h += '</div>';

  // Combat stats
  h += '<div class="cs-section-label">Combat</div>';
  h += '<div class="cs-combat-row">';
  h += '<div class="cs-stat"><div class="cs-stat-val">' + (cm.armor_class || 0) + '</div><div class="cs-stat-lbl">AC</div></div>';
  h += '<div class="cs-stat"><div class="cs-stat-val">' + fmtMod(cm.initiative || 0) + '</div><div class="cs-stat-lbl">Init</div></div>';
  h += '<div class="cs-stat"><div class="cs-stat-val">' + (cm.speed || 30) + '</div><div class="cs-stat-lbl">Speed</div></div>';
  h += '<div class="cs-stat"><div class="cs-stat-val" id="cs-hp-display">' + (cm.current_hp || 0) + '/' + (cm.max_hp || 0) + '</div><div class="cs-stat-lbl">HP</div></div>';
  if (cm.temp_hp) h += '<div class="cs-stat"><div class="cs-stat-val">' + cm.temp_hp + '</div><div class="cs-stat-lbl">Temp HP</div></div>';
  h += '<div class="cs-stat"><div class="cs-stat-val">' + (cm.passive_perception || 10) + '</div><div class="cs-stat-lbl">Pass Perc</div></div>';
  if (cm.hit_dice_total) h += '<div class="cs-stat"><div class="cs-stat-val">' + (cm.hit_dice_remaining || 0) + '</div><div class="cs-stat-lbl">Hit Dice</div></div>';
  var exhLvl = cm.exhaustion_level || 0;
  var exhColors = ["var(--dim)","#e8c060","#d4843a","#c85050","#b83030","#a00000","#700000"];
  h += '<div class="cs-stat" title="Exhaustion: 0=none, 1=disadv checks, 2=speed halved, 3=disadv attacks/saves, 4=HP max halved, 5=speed 0, 6=death"><div class="cs-stat-val" style="color:' + (exhColors[exhLvl] || "var(--dim)") + '">' + exhLvl + '/6</div><div class="cs-stat-lbl">Exhaust</div></div>';
  h += '</div>';

  // Death saves
  if (cm.death_saves) {
    var ds = cm.death_saves;
    var succDots = "", failDots = "";
    for (var i = 0; i < 3; i++) {
      succDots += '<span style="color:' + (i < (ds.successes||0) ? "#44cc77" : "#333") + '">&#9679;</span>';
      failDots  += '<span style="color:' + (i < (ds.failures||0)  ? "#cc4444" : "#333") + '">&#9679;</span>';
    }
    if ((ds.successes||0) > 0 || (ds.failures||0) > 0) {
      h += '<div class="cs-row-insp" style="font-size:.65rem;gap:.5rem"><span style="color:#44cc77">Death Saves: ' + succDots + '</span><span style="color:#cc4444">Failures: ' + failDots + '</span></div>';
    }
  }

  // Conditions
  if (cm.conditions && cm.conditions.length) {
    h += '<div class="cs-row-insp">';
    cm.conditions.forEach(function(c) {
      var name = c.name || c;
      h += '<span class="cs-badge" style="color:#c07070;border-color:#4a2a2a">' + name + '</span>';
    });
    h += '</div>';
  }

  // Saving throws
  h += '<div class="cs-section-label">Saving Throws</div>';
  h += '<div class="cs-saves">';
  ["STR","DEX","CON","INT","WIS","CHA"].forEach(function(k) {
    var s = st[k] || {}; var mod = fmtMod(s.modifier || 0);
    h += '<div class="cs-save-row">' + profDot(s.proficient) +
      '<span class="cs-save-key">' + k + '</span>' +
      '<span class="cs-save-mod">' + mod + '</span></div>';
  });
  h += '</div>';

  // Skills
  h += '<div class="cs-section-label">Skills</div>';
  h += '<div class="cs-skills">';
  Object.keys(sk).sort().forEach(function(name) {
    var s = sk[name] || {}; var mod = fmtMod(s.modifier || 0);
    h += '<div class="cs-skill-row">' + profDot(s.proficient, s.expertise) +
      '<span class="cs-skill-name" title="' + name + '">' + name + '</span>' +
      '<span class="cs-skill-ab">(' + (s.ability || "?") + ')</span>' +
      '<span class="cs-skill-mod">' + mod + '</span></div>';
  });
  h += '</div>';

  // Attacks
  if (atks.length) {
    h += '<div class="cs-section-label">Attacks</div>';
    h += '<table class="cs-atk-table"><tr><th>Name</th><th>Atk</th><th>Damage</th></tr>';
    atks.forEach(function(a) {
      h += '<tr><td>' + (a.name||"?") + '</td><td>' + fmtMod(a.attack_bonus||0) + '</td><td>' + (a.damage_dice||"—") + " " + (a.damage_type||"") + '</td></tr>';
    });
    h += '</table>';
  }

  // Spellcasting
  if (sp.ability) {
    h += '<div class="cs-section-label">Spellcasting (' + sp.ability + ')</div>';
    h += '<div class="cs-spell-row">';
    h += '<span class="cs-badge">Save DC ' + (sp.spell_save_dc||0) + '</span>';
    h += '<span class="cs-badge">Atk +' + (sp.spell_attack_bonus||0) + '</span>';
    h += '</div>';
    var slots = sp.spell_slots || {};
    var slotRows = "";
    ["1st","2nd","3rd","4th","5th"].forEach(function(lv) {
      var s = slots[lv]; if (!s) return;
      var bubs = "";
      for (var i = 0; i < s.total; i++)
        bubs += '<span class="slot-bubble' + (i < s.remaining ? " slot-full" : "") + '">&#9679;</span>';
      slotRows += '<span class="slot-group">' + lv + ": " + bubs + '</span>';
    });
    if (slotRows) h += '<div class="slot-tracker">' + slotRows + '</div>';
    if (sp.cantrips_known && sp.cantrips_known.length)
      h += '<div class="cs-sub-label"><strong style="color:var(--text)">Cantrips:</strong> ' + sp.cantrips_known.join(", ") + '</div>';
    if (sp.spells_known && sp.spells_known.length)
      h += '<div class="cs-sub-label"><strong style="color:var(--text)">Prepared:</strong> ' + sp.spells_known.join(", ") + '</div>';
  }

  // Class features
  if (feats.length) {
    h += '<div class="cs-section-label">Class Features</div>';
    feats.forEach(function(f) {
      var uses = (f.uses_max != null) ? ' <span class="cs-badge">' + (f.uses_remaining||0) + "/" + f.uses_max + '</span>' : "";
      h += '<div class="cs-feature"><div class="cs-feature-name">' + (f.name||"?") + uses + '</div>' +
        '<div class="cs-feature-desc">' + (f.description||"") + '</div></div>';
    });
  }

  // Racial traits
  if (traits.length) {
    h += '<div class="cs-section-label">Racial Traits</div>';
    traits.forEach(function(t) {
      h += '<div class="cs-feature"><div class="cs-feature-name">' + (t.name||"?") + '</div>' +
        '<div class="cs-feature-desc">' + (t.description||"") + '</div></div>';
    });
  }

  // Proficiencies
  h += '<div class="cs-section-label">Proficiencies</div>';
  h += '<div class="cs-profs">';
  if (profs.armor    && profs.armor.length)    h += '<div><span class="cs-prof-type">Armor:</span> '     + profs.armor.join(", ")    + '</div>';
  if (profs.weapons  && profs.weapons.length)  h += '<div><span class="cs-prof-type">Weapons:</span> '   + profs.weapons.join(", ")  + '</div>';
  if (profs.tools    && profs.tools.length)    h += '<div><span class="cs-prof-type">Tools:</span> '     + profs.tools.join(", ")    + '</div>';
  if (profs.languages&& profs.languages.length)h += '<div><span class="cs-prof-type">Languages:</span> ' + profs.languages.join(", ")+ '</div>';
  h += '</div>';

  // Personality
  var hasPers = id.personality_trait || id.ideal || id.bond || id.flaw;
  if (hasPers) {
    h += '<div class="cs-section-label">Personality</div>';
    h += '<div class="cs-personality">';
    if (id.personality_trait) h += '<div class="cs-pers-row"><span class="cs-pers-key">Trait — </span>' + id.personality_trait + '</div>';
    if (id.ideal)             h += '<div class="cs-pers-row"><span class="cs-pers-key">Ideal — </span>' + id.ideal + '</div>';
    if (id.bond)              h += '<div class="cs-pers-row"><span class="cs-pers-key">Bond — </span>'  + id.bond  + '</div>';
    if (id.flaw)              h += '<div class="cs-pers-row"><span class="cs-pers-key">Flaw — </span>'  + id.flaw  + '</div>';
    h += '</div>';
  }

  // Backstory
  if (id.backstory) {
    h += '<div class="cs-section-label">Backstory</div>';
    h += '<div class="cs-backstory">' + id.backstory + '</div>';
  }

  el.innerHTML = h;
}

// Inline update of HP in sheet (avoids full re-render on each turn)
function updateSheetHP(currentHp, maxHp) {
  if (!window._lastCharacter) return;
  if (window._lastCharacter.combat) window._lastCharacter.combat.current_hp = currentHp;
  var el = $("cs-hp-display");
  if (el) el.textContent = currentHp + "/" + (maxHp || (window._lastCharacter.combat && window._lastCharacter.combat.max_hp) || 0);
}

// Panel inventory
function renderPanelInventory(items, currency, currentWeight, carryingCapacity) {
  var el = $("panel-inv-list");
  if (!el) return;
  var cu  = currency || {};
  var wt  = currentWeight || 0;
  var cap = carryingCapacity || 0;

  var h = '<div class="cs-section-label">Currency</div>';
  h += '<div class="cs-currency">';
  if (cu.pp) h += '<span class="cu-badge pp">' + cu.pp + ' PP</span>';
  h += '<span class="cu-badge gp">' + (cu.gp || 0) + ' GP</span>';
  if (cu.sp) h += '<span class="cu-badge sp">' + cu.sp + ' SP</span>';
  if (cu.cp) h += '<span class="cu-badge cp">' + cu.cp + ' CP</span>';
  h += '</div>';

  if (cap > 0) {
    var wtPct = Math.min(100, wt / cap * 100);
    h += '<div class="cs-section-label">Carry Weight</div>';
    h += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.4rem">';
    h += '<div class="bar-track" style="flex:1;height:5px"><div class="bar-fill" style="width:' + wtPct + '%;background:linear-gradient(90deg,#4a7a3a,#8aca5a)"></div></div>';
    h += '<span style="font-size:.65rem;color:var(--dim)">' + wt + '/' + cap + ' lb</span></div>';
  }

  h += '<div class="cs-section-label">Equipment</div>';
  el.innerHTML = h;

  if (!items || !items.length) {
    el.innerHTML += '<p class="cs-empty">Pack is empty.</p>';
    return;
  }

  var NON_EQUIP = new Set(["consumable","utility","ammo","tool","book",""]);
  var listDiv = document.createElement("div");

  items.forEach(function(item) {
    var d = document.createElement("div");
    d.className = "inv-item";
    var canEquip = !NON_EQUIP.has(item.type || "");
    var typeBadge = item.type ? '<span class="inv-badge type">' + item.type + '</span>' : "";
    var eqBadge   = item.equipped ? '<span class="inv-badge equipped">equipped</span>' : "";
    var qty = (item.quantity > 1 || NON_EQUIP.has(item.type)) ? ' <span class="inv-qty">x' + item.quantity + '</span>' : "";
    d.innerHTML =
      '<div class="inv-info">' +
        '<div class="inv-name">' + item.name + qty + typeBadge + eqBadge + '</div>' +
        '<div class="inv-desc">' + (item.description || "") + '</div>' +
      '</div>';
    if (canEquip) {
      var btn = document.createElement("button");
      btn.className = "inv-equip-btn" + (item.equipped ? " unequip" : "");
      btn.textContent = item.equipped ? "Unequip" : "Equip";
      btn.addEventListener("click", async function() {
        btn.disabled = true;
        try {
          var r   = await fetch("/api/inventory/equip", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({item_id: item.id, equipped: !item.equipped})});
          var res = await r.json();
          if (res.error) { showError(res.error); btn.disabled = false; return; }
          refreshPanelInventory();
        } catch(e) { showError("Equip failed."); btn.disabled = false; }
      });
      d.appendChild(btn);
    }
    if (item.type === "consumable" && item.quantity > 0 && !inCombat) {
      var useBtn = document.createElement("button");
      useBtn.className = "share-btn";
      useBtn.style.cssText = "background:#0a1a10;border-color:#1a5a20;color:#7acf7a;margin-left:2px";
      useBtn.textContent = "Use";
      (function(iid, ib) {
        ib.addEventListener("click", async function() {
          ib.disabled = true;
          try {
            var r = await fetch("/api/action", {
              method: "POST", headers: {"Content-Type":"application/json"},
              body: JSON.stringify({choice: "use_item", item_id: iid})
            }).then(function(r){ return r.json(); });
            if (r.error) { showError(r.error); ib.disabled = false; return; }
            applyData(r);
            refreshPanelInventory();
          } catch(e) { showError("Could not use item."); ib.disabled = false; }
        });
      })(item.id, useBtn);
      d.appendChild(useBtn);
    }
    if (window.isMultiplayer && item.type === "consumable" && item.quantity > 0) {
      var shareBtn = document.createElement("button");
      shareBtn.className = "share-btn";
      shareBtn.title = "Share with party";
      shareBtn.textContent = "Share";
      (function(iid) {
        shareBtn.addEventListener("click", async function() {
          shareBtn.disabled = true;
          await shareToChest(iid);
          refreshPanelInventory();
          loadPartyChest();
          shareBtn.disabled = false;
        });
      })(item.id);
      d.appendChild(shareBtn);
    }
    listDiv.appendChild(d);
  });
  el.appendChild(listDiv);
}

async function refreshPanelInventory() {
  var el = $("panel-inv-list");
  if (!el) return;
  try {
    var invData  = await api.inv();
    var char     = window._lastCharacter || {};
    renderPanelInventory(invData.items || [], char.currency || {}, char.current_weight || 0, char.carrying_capacity || 0);
  } catch(e) {
    el.innerHTML = '<p class="cs-empty">Could not load inventory.</p>';
  }
}

async function loadAndRenderCharSheet() {
  try {
    var r = await api.character();
    if (r.character) {
      window._lastCharacter = r.character;
      renderCharacterSheet(r.character);
    }
  } catch(e) {}
}

var _currentNpcId = null;
async function openNpc(npcId) {
  _currentNpcId = npcId;
  var talkData  = await fetch("/api/npc/" + npcId + "/talk", {method:"POST"}).then(function(r){return r.json();});
  $("npc-modal-title").textContent = "◆ " + (talkData.npc_name || "NPC");
  // Show LLM narrative if present, otherwise fall back to raw greeting
  $("npc-greeting").textContent    = talkData.narrative || talkData.greeting || "";
  $("npc-persuade-result").innerHTML = "";

  // Shop
  var shopSec = $("npc-shop-section");
  shopSec.innerHTML = "";
  if (talkData.has_shop && talkData.shop_inventory && talkData.shop_inventory.length) {
    var lbl = document.createElement("div");
    lbl.className = "npc-section-label";
    lbl.textContent = "Wares for Sale";
    shopSec.appendChild(lbl);
    talkData.shop_inventory.forEach(function(listing) {
      var row = document.createElement("div");
      row.className = "npc-shop-item";
      row.innerHTML =
        '<div class="npc-item-info"><div class="npc-item-name">' + listing.name + '</div>' +
        '<div class="npc-item-cost">' + listing.cost + ' gp</div></div>';
      var btn = document.createElement("button");
      btn.className   = "save-btn";
      btn.textContent = "Buy";
      btn.addEventListener("click", function() { buyFromNpc(npcId, listing.item_id, listing.name, listing.cost, btn); });
      row.appendChild(btn);
      shopSec.appendChild(row);
    });
  }

  // Quest
  var questSec = $("npc-quest-section");
  questSec.innerHTML = "";
  if (talkData.quest_offer) {
    var q  = talkData.quest_offer;
    var lbl2 = document.createElement("div");
    lbl2.className = "npc-section-label";
    lbl2.textContent = "Quest Available";
    questSec.appendChild(lbl2);
    var qd = document.createElement("div");
    qd.className = "quest-row";
    qd.innerHTML =
      '<div class="quest-name">' + q.name + '</div>' +
      '<div class="quest-desc">' + (q.dialogue || q.description) + '</div>';
    var acceptBtn = document.createElement("button");
    acceptBtn.className   = "save-btn";
    acceptBtn.textContent = "Accept Quest";
    acceptBtn.style.marginTop = ".4rem";
    acceptBtn.addEventListener("click", async function() {
      acceptBtn.disabled = true;
      var r = await fetch("/api/quest/accept", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({quest_id: q.id})}).then(function(r){return r.json();});
      if (r.error) { showError(r.error); acceptBtn.disabled = false; return; }
      qd.innerHTML += '<span class="quest-status accepted" style="margin-top:.3rem">Accepted!</span>';
      acceptBtn.remove();
    });
    qd.appendChild(acceptBtn);
    questSec.appendChild(qd);
  } else if (talkData.quest_status === "accepted") {
    var lbl3 = document.createElement("div");
    lbl3.className = "npc-section-label";
    lbl3.textContent = "Active Quest";
    questSec.appendChild(lbl3);
    var qd2 = document.createElement("div");
    qd2.className = "quest-row";
    qd2.innerHTML =
      '<div class="quest-desc">' + (talkData.quest_progress || "") + '</div>';
    var complBtn = document.createElement("button");
    complBtn.className   = "save-btn";
    complBtn.textContent = "Turn In Quest";
    complBtn.style.marginTop = ".4rem";
    complBtn.addEventListener("click", async function() {
      complBtn.disabled = true;
      var r = await fetch("/api/quest/complete", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({quest_id: talkData.quest_id})}).then(function(r){return r.json();});
      if (r.error) { showError(r.error); complBtn.disabled = false; return; }
      qd2.innerHTML += '<div class="persuade-result success">Quest complete! +'  + r.xp_reward + ' XP, +' + r.gold_reward + ' gp</div>';
      complBtn.remove();
      $("gold-badge").textContent = (parseInt($("gold-badge").textContent) + r.gold_reward) + " Gold";
    });
    qd2.appendChild(complBtn);
    questSec.appendChild(qd2);
  }

  // Action buttons
  var btns = $("npc-action-btns");
  btns.innerHTML = "";
  var perBtn = document.createElement("button");
  perBtn.className   = "save-btn";
  perBtn.textContent = "Persuade";
  perBtn.addEventListener("click", async function() {
    perBtn.disabled = true;
    var r = await fetch("/api/npc/" + npcId + "/persuade", {method:"POST"}).then(function(r){return r.json();});
    var res = $("npc-persuade-result");
    res.innerHTML = '<div class="persuade-result ' + (r.success ? "success" : "fail") + '">' +
      (r.success ? "✓" : "✗") + " Roll " + r.roll + " + " + r.cha_mod + " = " + r.total +
      " vs DC " + r.dc + " &mdash; " + (r.dialogue || "") +
    '</div>';
    perBtn.disabled = false;
  });
  btns.appendChild(perBtn);

  $("npc-overlay").classList.add("active");
}

async function buyFromNpc(npcId, itemId, itemName, cost, btn) {
  btn.disabled = true;
  var r = await fetch("/api/npc/" + npcId + "/buy", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({item_id: itemId, quantity: 1})
  }).then(function(r){return r.json();});
  if (r.error) { showError(r.error); btn.disabled = false; return; }
  showLootToast([{name: itemName, qty: 1}]);
  $("gold-badge").textContent = (r.gold_remaining || 0) + " Gold";
  btn.disabled = false;
}

async function openQuestLog() {
  var data = await fetch("/api/quests").then(function(r){return r.json();});
  var list = $("quest-list");
  list.innerHTML = "";
  var quests = data.quests || [];
  if (!quests.length) { list.innerHTML = '<p class="inv-empty">No quests known yet.</p>'; }
  quests.forEach(function(q) {
    var row = document.createElement("div");
    row.className = "quest-row";
    var statusLabel = {available:"Available", accepted:"In Progress", completed:"Completed"}[q.status] || q.status;
    row.innerHTML =
      '<div class="quest-name">' + q.name + '</div>' +
      '<div class="quest-desc">' + q.description + '</div>' +
      '<span class="quest-status ' + q.status + '">' + statusLabel + '</span>' +
      '<div class="quest-reward">' + q.xp_reward + ' XP &bull; ' + q.gold_reward + ' gp</div>';
    if (q.status === "accepted" && q.objective_met) {
      var complBtn = document.createElement("button");
      complBtn.className   = "save-btn";
      complBtn.textContent = "Turn In";
      complBtn.style.marginTop = ".35rem";
      complBtn.addEventListener("click", async function() {
        complBtn.disabled = true;
        var r = await fetch("/api/quest/complete", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({quest_id: q.id})}).then(function(r){return r.json();});
        if (r.error) { showError(r.error); complBtn.disabled = false; return; }
        openQuestLog();
        $("gold-badge").textContent = (parseInt($("gold-badge").textContent) + r.gold_reward) + " Gold";
      });
      row.appendChild(complBtn);
    }
    list.appendChild(row);
  });
  $("quest-overlay").classList.add("active");
}

$("quest-btn").addEventListener("click", openQuestLog);
$("close-quest").addEventListener("click", function() { $("quest-overlay").classList.remove("active"); });
$("quest-overlay").addEventListener("click", function(e) {
  if (e.target === $("quest-overlay")) $("quest-overlay").classList.remove("active");
});
$("close-npc").addEventListener("click", function() { $("npc-overlay").classList.remove("active"); });
$("npc-overlay").addEventListener("click", function(e) {
  if (e.target === $("npc-overlay")) $("npc-overlay").classList.remove("active");
});

// SAVE / LOAD

async function openSaveLoad() {
  await refreshSaveList();
  $("save-overlay").classList.add("active");
}

async function refreshSaveList() {
  var list = $("save-list");
  list.innerHTML = '<p class="inv-empty" style="padding:.5rem 0">Loading...</p>';
  try {
    var data = await fetch("/api/saves").then(function(r){ return r.json(); });
    var savesArr = (data.saves || []).slice().sort(function(a, b){ return b.saved_at - a.saved_at; });
    if (!savesArr.length) {
      list.innerHTML = '<p class="inv-empty">No saves yet.</p>'; return;
    }
    list.innerHTML = "";
    savesArr.forEach(function(s) {
      var d   = new Date(s.saved_at * 1000);
      var dt  = d.toLocaleDateString() + " " + d.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
      var lbl = s.is_auto ? "Autosave" : s.name;
      var row = document.createElement("div");
      row.className = "save-slot";
      row.innerHTML =
        '<div class="save-info">' +
          '<div class="save-name">' + lbl + '</div>' +
          '<div class="save-meta">' + s.char_name + ' &bull; ' + s.class + ' Lv ' + s.level +
            ' &bull; Floor ' + s.floor + ' &bull; HP ' + s.hp + ' &bull; ' + dt + '</div>' +
        '</div>';
      var loadBtn = document.createElement("button");
      loadBtn.className = "save-btn";
      loadBtn.textContent = "Load";
      loadBtn.addEventListener("click", function() { loadSave(s.id, lbl); });
      var delBtn = document.createElement("button");
      delBtn.className = "save-btn del";
      delBtn.textContent = "Del";
      delBtn.addEventListener("click", function() { deleteSave(s.id, row); });
      row.appendChild(loadBtn);
      row.appendChild(delBtn);
      list.appendChild(row);
    });
  } catch(e) {
    list.innerHTML = '<p class="inv-empty">Could not load saves.</p>';
  }
}

async function doSave() {
  var name = $("save-name-input").value.trim();
  if (!name) { showError("Enter a save name."); return; }
  var btn = $("do-save-btn");
  btn.disabled = true; btn.textContent = "Saving...";
  try {
    var r = await fetch("/api/saves/save", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name: name})
    }).then(function(r){ return r.json(); });
    if (r.error) { showError(r.error); }
    else { $("save-name-input").value = ""; await refreshSaveList(); }
  } catch(e) { showError("Save failed."); }
  btn.disabled = false; btn.textContent = "Save";
}

async function loadSave(saveId, label) {
  if (!confirm("Load \"" + label + "\"? Unsaved progress will be lost.")) return;
  $("save-overlay").classList.remove("active");
  $("load-screen").classList.remove("gone");
  $("load-msg").textContent = "Loading save...";
  try {
    var data = await fetch("/api/saves/load", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({save_id: saveId})
    }).then(function(r){ return r.json(); });
    $("load-screen").classList.add("gone");
    if (data.error) { showError(data.error); return; }
    turnCount = (data.state && data.state.turn) || 1;
    applyData(data, null);
  } catch(e) {
    $("load-screen").classList.add("gone");
    showError("Load failed.");
  }
}

async function deleteSave(saveId, row) {
  if (!confirm("Delete this save?")) return;
  try {
    await fetch("/api/saves/" + saveId, {method: "DELETE"});
    row.remove();
    var list = $("save-list");
    if (!list.children.length) list.innerHTML = '<p class="inv-empty">No saves yet.</p>';
  } catch(e) { showError("Delete failed."); }
}

$("save-btn").addEventListener("click", openSaveLoad);
$("close-save").addEventListener("click", function() { $("save-overlay").classList.remove("active"); });
$("save-overlay").addEventListener("click", function(e) {
  if (e.target === $("save-overlay")) $("save-overlay").classList.remove("active");
});
$("do-save-btn").addEventListener("click", doSave);
$("save-name-input").addEventListener("keydown", function(e) {
  if (e.key === "Enter") doSave();
});

// Global MP state
window.myPlayerName  = null;
window.myRoomCode    = null;
window.isHost        = false;
window.isMultiplayer = false;
window.myTurn        = true;

// Fetch interceptor — auto-inject room/player headers
(function() {
  var _orig = window.fetch.bind(window);
  window.fetch = function(url, init) {
    if (window.myRoomCode && window.myRoomCode !== "SOLO") {
      init = init ? Object.assign({}, init) : {};
      var h = init.headers ? Object.assign({}, init.headers) : {};
      h["X-Room-Code"]   = window.myRoomCode;
      if (window.myPlayerName) h["X-Player-Name"] = window.myPlayerName;
      init.headers = h;
    }
    return _orig(url, init);
  };
})();

// Socket.IO
var socket = io();

// Party bar (left panel)
var COND_ICONS  = { Poisoned:"☠", Stunned:"💫", Blinded:"👁", Frightened:"😱", Charmed:"💝", Prone:"⬇", Paralyzed:"⚡", Exhaustion:"😫" };
var CLASS_ICONS = { Fighter:"⚔", Rogue:"†", Wizard:"✦", Cleric:"✝", Ranger:"⚜", Paladin:"☩", Barbarian:"⚡", Bard:"♪", Druid:"☘", Monk:"☯" };
function renderPartyBar(party) {
  var bar     = $("party-bar");
  var section = $("party-section");
  if (!party || !party.length || !window.isMultiplayer) {
    if (section) section.style.display = "none";
    return;
  }
  if (section) section.style.display = "block";
  bar.style.display = "flex";
  bar.innerHTML = party.map(function(p) {
    var cls    = "party-card" + (p.is_current_turn ? " active-turn" : "") + (!p.connected ? " disconnected" : "");
    var hpPct  = p.max_hp ? Math.max(0, Math.min(100, p.hp / p.max_hp * 100)) : 0;
    var icon   = CLASS_ICONS[p.class] || "◆";
    var condHtml = "";
    if (p.conditions && p.conditions.length) {
      condHtml = '<div style="font-size:.68rem;margin-top:.15rem">' +
        p.conditions.map(function(c){ return '<span title="' + c + '">' + (COND_ICONS[c] || "⚠") + '</span>'; }).join(" ") +
      '</div>';
    }
    return '<div class="' + cls + '">' +
      '<div class="party-card-name">' +
        '<span style="color:var(--gold-dim);margin-right:.2rem">' + icon + '</span>' +
        (p.character_name || p.player_name) +
        (p.player_name === window.myPlayerName ? ' <span style="color:var(--dim);font-size:.62rem">(you)</span>' : "") +
      '</div>' +
      '<div style="display:flex;align-items:center;gap:.3rem;margin-top:.18rem">' +
        '<div class="bar-track" style="flex:1;height:4px"><div class="bar-fill hp-fill" style="width:' + hpPct + '%"></div></div>' +
        '<span class="party-card-hp" style="font-size:.65rem">' + (p.hp||0) + '/' + (p.max_hp||0) + '</span>' +
      '</div>' +
      condHtml +
      (p.is_current_turn ? '<div class="party-card-turn">&#9654; acting</div>' : '') +
    '</div>';
  }).join("");
}

// Turn banner
function renderTurnBanner(activePlayerName) {
  var banner = $("turn-banner");
  if (!window.isMultiplayer) { banner.style.display = "none"; return; }
  if (!activePlayerName) { banner.style.display = "none"; window.myTurn = true; return; }
  banner.style.display = "block";
  if (activePlayerName === window.myPlayerName) {
    window.myTurn = true;
    banner.className  = "turn-banner your-turn";
    banner.textContent = "Your turn";
  } else {
    window.myTurn = false;
    banner.className  = "turn-banner their-turn";
    banner.textContent = activePlayerName + "'s turn";
  }
}

// Lobby helpers
function renderLobbyPlayers(party) {
  var list = $("lobby-player-list");
  if (!list) return;
  list.innerHTML = party.map(function(p) {
    var badge = p.is_host
      ? '<span class="lobby-badge host">Host</span>'
      : (p.ready ? '<span class="lobby-badge ready">Ready</span>' : '<span class="lobby-badge waiting">Waiting</span>');
    var kick = (window.isHost && !p.is_host)
      ? '<button class="landing-btn" style="font-size:.7rem;padding:.2rem .7rem" onclick="kickPlayer(\'' + p.player_name.replace(/'/g,"\\'") + '\')">Kick</button>'
      : '';
    return '<div class="lobby-player"><span class="lobby-name">' + p.player_name + '</span>' + badge + kick + '</div>';
  }).join("");
  var allReady = party.length > 0 && party.every(function(p) { return p.ready; });
  if (window.isHost) $("start-game-btn").classList.toggle("gone", !allReady);
  $("lobby-status").textContent = allReady ? "All players ready!" : "Waiting for players to choose characters...";
}

function kickPlayer(name) {
  if (socket) socket.emit("kick_player", {room_code: window.myRoomCode, target_name: name});
}

// Socket events
socket.on("room_created", function(data) {
  window.myPlayerName  = data.player_name;
  window.myRoomCode    = data.room_code;
  window.isHost        = true;
  window.isMultiplayer = true;
  $("lobby-code").textContent = data.room_code;
  renderLobbyPlayers(data.party || []);
  $("load-screen").classList.add("gone");
  $("landing-screen").classList.add("gone");
  $("lobby-screen").classList.remove("gone");
  $("start-game-btn").classList.add("gone");
  hideError();
});

socket.on("room_joined", function(data) {
  window.myPlayerName  = data.player_name;
  window.myRoomCode    = data.room_code;
  window.isHost        = data.is_host;
  window.isMultiplayer = true;
  $("lobby-code").textContent = data.room_code;
  renderLobbyPlayers(data.party || []);
  $("load-screen").classList.add("gone");
  $("landing-screen").classList.add("gone");
  $("lobby-screen").classList.remove("gone");
  if (window.isHost) $("start-game-btn").classList.remove("gone");
  else $("start-game-btn").classList.add("gone");
  hideError();
  if (data.rejoined && data.state === "playing") {
    $("lobby-screen").classList.add("gone");
    var psec2 = $("party-section"); if (psec2) psec2.style.display = "block";
    $("chat-box").style.display  = "block";
    api.resume().then(function(resume) {
      if (resume.active) {
        $("load-screen").classList.add("gone");
        turnCount = resume.state.turn || 1;
        applyData({narrative: resume.narrative, hp: resume.hp, actions: resume.actions || [], state: resume.state, ending: null}, null);
      }
    });
  }
});

socket.on("player_list_update", function(data) {
  renderLobbyPlayers(data.party || []);
});

socket.on("game_started", function(data) {
  window.myRoomCode = data.room_code;
  $("lobby-screen").classList.add("gone");
  var psec = $("party-section");
  if (psec) psec.style.display = "block";
  $("chat-box").style.display  = "block";
  loadPartyChest();
  if (window.isHost) {
    startFresh();
  } else {
    $("load-screen").classList.remove("gone");
    $("load-msg").textContent = "Game starting...";
  }
});

socket.on("game_state_update", function(data) {
  window._lastCombatState = data.combat || {};
  renderPartyBar(data.party);
  renderTurnBanner(data.active_player_name);
  if (window.isMultiplayer) loadPartyChest();
  if (data.state) {
    var maxHp = data.state.max_hp || 100;
    updateHPBars(data.state.hp || 0, maxHp, data.state.enemy);
    $("floor-badge").textContent = "Floor " + (data.state.floor || 1) + " / 4";
    $("gold-badge").textContent  = (data.state.gold || 0) + " Gold";
    updateXP(data.state, data);
    renderChoices(data.state);
  }
  var newNarrative = data.narrative || "";
  if (newNarrative && newNarrative !== _lastBroadcastNarrative) {
    _lastBroadcastNarrative = newNarrative;
    typewrite(newNarrative);
  }
  if (data.dungeon_map) renderMiniMap(data.dungeon_map, data.state && data.state.current_room_id);
  _lastAvailableSpells = data.available_spells || [];
  _lastSpellSlots      = data.spell_slots      || {};
  renderSpells(_lastAvailableSpells, _lastSpellSlots);
  renderInitiative(data.combat);
  var enemyAlive = !!(data.state && data.state.enemy && data.state.enemy.hp > 0);
  renderChips(data.actions || [], enemyAlive);
  if (data.ending) setTimeout(function() { showEnding(data.ending); }, 2600);
  $("load-screen").classList.add("gone");
  if (isEnemyTurn(data.combat) && (!window.isMultiplayer || window.isHost)) {
    var textToRead = newNarrative;
    var readingDelay = Math.max(4500, Math.min(12000, textToRead.length * 35));
    setTimeout(resolveEnemyTurnFromServer, readingDelay);
  }
});

socket.on("player_disconnected", function(data) {
  renderPartyBar(data.party || []);
  var name = data.player_name || "A player";
  if (data.skip_narrative) {
    typewrite(data.skip_narrative);
  } else {
    showError(name + " disconnected.");
  }
});

socket.on("player_kicked", function(data) {
  if (data.player_name === window.myPlayerName) {
    window.myRoomCode    = null;
    window.myPlayerName  = null;
    window.isMultiplayer = false;
    $("lobby-screen").classList.add("gone");
    $("landing-screen").classList.remove("gone");
    showError("You have been kicked from the room.");
  } else {
    renderLobbyPlayers(data.party || []);
  }
});

socket.on("chat_message", function(data) {
  var log = $("chat-log");
  var div = document.createElement("div");
  div.className = "chat-entry";
  div.innerHTML = '<span class="cn">' + (data.player_name || "?") + ':</span> ' + (data.message || "");
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
});

socket.on("error", function(data) {
  var msg = (data && data.message) || "A server error occurred.";
  if (!$("landing-screen").classList.contains("gone")) showLandingError(msg);
  else showError(msg);
});

socket.on("level_up_notification", function(data) {
  var who   = data.player_name || "Someone";
  var lvl   = data.new_level || "?";
  var feats = (data.new_features || []).join(" | ");
  var toast = $("levelup-toast");
  toast.textContent = "⬆ " + who + " reached Level " + lvl + (feats ? " — " + feats : "");
  toast.classList.add("show");
  clearTimeout(window._lvlToastTimer);
  window._lvlToastTimer = setTimeout(function() { toast.classList.remove("show"); }, 6000);
  // Also show local level-up bar if it's us
  if (who === window.myPlayerName) {
    var bar = $("levelup-bar");
    bar.textContent = toast.textContent;
    bar.classList.add("show");
    setTimeout(function() { bar.classList.remove("show"); }, 8000);
  }
});

// Party chest helpers
async function loadPartyChest() {
  if (!window.isMultiplayer) return;
  try {
    var r    = await fetch("/api/party/inventory");
    var data = await r.json();
    renderPartyChest(data.items || []);
  } catch(e) {}
}

function renderPartyChest(items) {
  var sec  = $("party-chest-section");
  var list = $("party-chest-list");
  if (!window.isMultiplayer) { sec.style.display = "none"; return; }
  sec.style.display = "block";
  if (!items || !items.length) {
    list.innerHTML = '<span class="party-chest-empty">Empty.</span>';
    return;
  }
  list.innerHTML = items.map(function(it) {
    return '<div class="chest-item">' +
      '<span class="chest-item-name">' + (it.name || it.item_id) + '</span>' +
      '<span class="chest-item-qty">×' + it.qty + '</span>' +
      '<button class="chest-take-btn" onclick="takeFromChest(\'' + it.item_id + '\')">Take</button>' +
    '</div>';
  }).join("");
}

async function takeFromChest(itemId) {
  if (busy) return;
  setBusy(true);
  try {
    var r    = await fetch("/api/party/inventory/take", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({item_id: itemId, qty: 1})
    });
    var data = await r.json();
    if (data.error) { showError(data.error); } else { renderPartyChest(data.pool || []); }
  } catch(e) { showError("Could not take item."); }
  setBusy(false);
}

async function shareToChest(itemId) {
  if (busy || !window.isMultiplayer) return;
  setBusy(true);
  try {
    var r    = await fetch("/api/party/inventory/share", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({item_id: itemId, qty: 1})
    });
    var data = await r.json();
    if (data.error) { showError(data.error); } else { renderPartyChest(data.pool || []); }
  } catch(e) { showError("Could not share item."); }
  setBusy(false);
}

// Chat
$("chat-send").addEventListener("click", function() {
  var input = $("chat-input");
  var msg   = input.value.trim();
  if (!msg || !window.myRoomCode) return;
  socket.emit("chat_message", {room_code: window.myRoomCode, player_name: window.myPlayerName, message: msg});
  input.value = "";
});
$("chat-input").addEventListener("keydown", function(e) {
  if (e.key === "Enter") $("chat-send").click();
});

// Landing buttons
$("solo-btn").addEventListener("click", async function() {
  window.myRoomCode    = "SOLO";
  window.isMultiplayer = false;
  window.myTurn        = true;
  $("landing-screen").classList.add("gone");
  await _initGame();
});

function showLandingError(msg) {
  var el = $("landing-error");
  el.textContent = msg; el.style.display = "block";
  setTimeout(function() { el.style.display = "none"; }, 4000);
}

$("create-room-btn").addEventListener("click", function() {
  var name = $("mp-name-input").value.trim();
  if (!name) { showLandingError("Enter your player name first."); return; }
  socket.emit("create_game", {player_name: name});
});

$("join-room-btn").addEventListener("click", function() {
  var name = $("mp-name-input").value.trim();
  var code = $("mp-code-input").value.trim().toUpperCase();
  if (!name) { showLandingError("Enter your player name first."); return; }
  if (code.length < 4) { showLandingError("Enter a valid 4-character room code."); return; }
  socket.emit("join_game", {player_name: name, room_code: code});
});

$("lobby-char-btn").addEventListener("click", async function() {
  $("lobby-screen").classList.add("gone");
  if (window.myPlayerName) $("cc-player-name").value = window.myPlayerName;
  await showCharacterCreator();
});

$("start-game-btn").addEventListener("click", function() {
  if (window.isHost && window.myRoomCode) {
    socket.emit("game_start", {room_code: window.myRoomCode});
  }
});

$("lobby-back-btn").addEventListener("click", function() {
  window.myRoomCode    = null;
  window.myPlayerName  = null;
  window.isMultiplayer = false;
  $("lobby-screen").classList.add("gone");
  $("landing-screen").classList.remove("gone");
});

init();
