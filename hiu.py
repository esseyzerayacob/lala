# =============================================================================
# TITAN PROJECT - ENTERPRISE MULTIPLAYER ARCHITECTURE
# VERSION: 11.0.4 (MAX-LINE EDITION)
# PORT: 8080 | REAPER: AGGRESSIVE | STATE: PRODUCTION
# =============================================================================

import random
import time
import threading
import uuid
import logging
from flask import Flask, render_template_string, request, jsonify

# -----------------------------------------------------------------------------
# 1. SERVER CONFIGURATION & LOGGING
# -----------------------------------------------------------------------------
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Suppress annoying flask logs


# -----------------------------------------------------------------------------
# 2. CORE GAME ENGINE (THE TITAN REGISTRY)
# -----------------------------------------------------------------------------
class TitanEngine:
    """
    Main State Controller. Handles match creation, player heartbeats,
    and game-over logic for 1000+ concurrent users.
    """

    def __init__(self):
        self.matches = {}
        self.users = {}
        self.lobby = []
        self.lock = threading.Lock()
        self.start_time = time.time()

    def generate_id(self, prefix="T"):
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    def register_user(self, uid):
        with self.lock:
            self.users[uid] = {
                "ping": time.time(),
                "m_id": None,
                "name": uid,
                "status": "IDLE"
            }

    def create_match(self, p1_id, p2_id=None, solo=False):
        m_id = self.generate_id("MATCH")
        p_list = [p1_id] if solo else [p1_id, p2_id]

        match_data = {
            "id": m_id,
            "solo": solo,
            "active": True,
            "start_time": time.time(),
            "players": p_list,
            "scores": {pid: 0 for pid in p_list},
            "moves": {pid: 0 for pid in p_list},
            "turn_idx": 0,
            "target": random.randint(1, 100),
            "hint": "BATTLE INITIALIZED. GUESS 1-100.",
            "last_action": "System: Game Started.",
            "chat": [],
            "draw_requested_by": None,
            "winner_id": None,
            "reveal_target": False
        }

        with self.lock:
            self.matches[m_id] = match_data
            for pid in p_list:
                if pid in self.users:
                    self.users[pid]["m_id"] = m_id
                    self.users[pid]["status"] = "IN_GAME"
        return m_id

    def process_move(self, m_id, u_id, val):
        with self.lock:
            m = self.matches.get(m_id)
            if not m or not m["active"]:
                return False, "Match Inactive"

            # Multiplayer Turn Check
            if not m["solo"]:
                if m["players"][m["turn_idx"]] != u_id:
                    return False, "Not Your Turn"

            m["moves"][u_id] += 1
            target = m["target"]

            if val < target:
                res = "TOO LOW"
                m["hint"] = random.choice([
                    f"{val} is weak. HIGHER!",
                    f"Try that old one! {val} is too low.",
                    f"Not even close. Go up from {val}."
                ])
            elif val > target:
                res = "TOO HIGH"
                m["hint"] = random.choice([
                    f"{val}? Too much power! DROP IT!",
                    f"Lower your sights. {val} is too high.",
                    f"Descending from {val}..."
                ])
            else:
                m["scores"][u_id] += 1
                m["target"] = random.randint(1, 100)
                m["hint"] = "SCORCHING! YOU FOUND IT. NEXT NUMBER READY."
                res = "CORRECT"

            m["last_action"] = f"{u_id} picked {val}: {res}"

            # Switch Turns
            if not m["solo"]:
                m["turn_idx"] = 1 if m["turn_idx"] == 0 else 0

            return True, "Success"

    def reaper(self):
        """ The Death Watch: Kills matches if a player disconnects """
        while True:
            now = time.time()
            with self.lock:
                for uid, info in list(self.users.items()):
                    if now - info["ping"] > 3.0:  # 3 Second Timeout
                        mid = info.get("m_id")
                        if mid in self.matches:
                            self.matches[mid]["active"] = False
                            self.matches[mid]["last_action"] = f"DISCONNECT: {uid} fled."
                        del self.users[uid]
            time.sleep(1)


# Initialize Engine
titan = TitanEngine()
threading.Thread(target=titan.reaper, daemon=True).start()

# -----------------------------------------------------------------------------
# 3. THE TITAN INTERFACE (DENSE CSS/JS STACK)
# -----------------------------------------------------------------------------
UI_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
    <title>TITAN PROJECT V11</title>
    <style>
        /* DESIGN SYSTEM */
        :root {
            --neon: #00ffcc;
            --red: #ff3333;
            --gold: #ffcc00;
            --bg: #030303;
            --surface: #111111;
            --border: #222222;
        }

        * { box-sizing: border-box; font-family: 'Segoe UI', 'Arial Black', sans-serif; }
        body { 
            background: var(--bg); color: #fff; margin: 0; padding: 0;
            height: 100vh; width: 100vw; overflow: hidden;
            display: flex; flex-direction: column;
        }

        /* SCREEN MANAGEMENT */
        .screen {
            display: none; position: absolute; top:0; left:0;
            width: 100%; height: 100%; flex-direction: column;
            align-items: center; justify-content: center; z-index: 10;
        }
        .screen.active { display: flex; }

        /* NEON COMPONENTS */
        .box {
            background: var(--surface);
            border: 3px solid var(--neon);
            border-radius: 30px;
            padding: 40px; width: 90%; max-width: 450px;
            text-align: center; box-shadow: 0 0 20px rgba(0,255,204,0.1);
        }

        .btn {
            background: var(--neon); color: #000; border: none;
            padding: 18px; margin: 10px 0; width: 100%;
            font-size: 1.3rem; font-weight: 900; border-radius: 15px;
            cursor: pointer; text-transform: uppercase; transition: 0.2s;
        }
        .btn:active { transform: scale(0.95); }
        .btn:disabled { background: #222; color: #444; border: 1px solid #333; cursor: not-allowed; }
        .btn-red { background: var(--red); color: white; }
        .btn-gold { background: var(--gold); color: black; }

        /* HUD ELEMENTS */
        .hud-top {
            position: absolute; top: 0; width: 100%; height: 70px;
            background: #000; border-bottom: 2px solid var(--neon);
            display: flex; justify-content: space-around; align-items: center;
            z-index: 100; font-weight: bold;
        }

        .hud-bot {
            position: absolute; bottom: 0; width: 100%; height: 50px;
            background: #000; border-top: 2px solid var(--neon);
            display: flex; justify-content: center; align-items: center;
            color: var(--neon); z-index: 100;
        }

        .exit-controls {
            position: absolute; top: 80px; left: 15px;
            display: flex; flex-direction: column; gap: 10px; z-index: 101;
        }

        /* CORE GAMEPLAY */
        #hint-box {
            font-size: 2.2rem; color: var(--gold); text-align: center;
            margin: 20px 0; min-height: 100px; padding: 0 20px;
            display: flex; align-items: center; justify-content: center;
            text-shadow: 0 0 15px rgba(255,204,0,0.4);
        }

        .guess-input {
            background: none; border: 5px solid var(--neon);
            color: #fff; font-size: 5rem; width: 220px;
            text-align: center; border-radius: 20px; outline: none;
            box-shadow: 0 0 10px rgba(0,255,204,0.1);
        }
        .guess-input:focus { border-color: var(--gold); }
        .guess-input:disabled { border-color: #333; color: #333; }

        /* CHAT AND ACTION LOG */
        .chat-panel {
            width: 90%; max-width: 400px; margin-top: 20px;
            background: #111; border: 1px solid #333; border-radius: 10px;
            padding: 10px;
        }
        #chat-window { height: 80px; overflow-y: auto; font-size: 0.8rem; text-align: left; }
        #chat-in { width: 100%; background: #000; border: 1px solid var(--neon); color: #fff; padding: 5px; }

        /* OVERLAYS */
        .overlay {
            display: none; position: fixed; top:0; left:0; width:100%; height:100%;
            z-index: 1000; flex-direction: column; align-items: center;
            justify-content: center; text-align: center;
        }
        #death-screen { background: rgba(255,0,0,0.95); }
        #shame-screen { background: rgba(0,0,0,0.98); }

        /* ANIMATIONS */
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .waiting { animation: pulse 1.5s infinite; }
    </style>
</head>
<body>

    <div id="death-screen" class="overlay">
        <h1 style="font-size: 4rem;">TERMINATED</h1>
        <h2 id="death-msg">OPPONENT LEFT THE BATTLE. <br> YOU WIN!</h2>
        <button class="btn" onclick="location.reload()" style="max-width:300px;">BACK TO ARENA</button>
    </div>

    <div id="shame-screen" class="overlay">
        <div class="box" style="border-color: var(--red);">
            <h2 id="shame-title">FORFEITING?</h2>
            <p id="shame-body"></p>
            <div style="background: #000; border: 2px solid var(--gold); border-radius: 15px; margin: 20px 0; padding: 20px;">
                <span style="color: var(--gold); font-size: 0.9rem;">THE SECRET WAS:</span>
                <h1 id="revealed-num" style="font-size: 5rem; margin: 0;">??</h1>
            </div>
            <button class="btn btn-red" onclick="location.reload()">ABANDON MISSION</button>
            <button class="btn" onclick="document.getElementById('shame-screen').style.display='none'">CANCEL</button>
        </div>
    </div>

    <div id="draw-screen" class="overlay" style="background: rgba(0,0,0,0.9);">
        <div class="box" style="border-color: var(--gold);">
            <h2>DRAW OFFERED</h2>
            <p>Your opponent wants to reveal the answer and call it a draw. Do you agree?</p>
            <button class="btn btn-gold" onclick="drawResponse(true)">AGREE (REVEAL)</button>
            <button class="btn btn-red" onclick="drawResponse(false)">DECLINE</button>
        </div>
    </div>

    <div id="scr-menu" class="screen active">
        <h1 style="color: var(--neon); font-size: 5rem; text-shadow: 0 0 20px var(--neon);">TITAN</h1>
        <div class="box">
            <input type="text" id="uname" placeholder="CODENAME" maxlength="15" style="width:100%; background:#000; color:white; border:2px solid var(--neon); padding:15px; border-radius:10px; text-align:center; font-size:1.2rem; margin-bottom:20px;">
            <button class="btn" onclick="init('solo')">SOLO PRACTICE</button>
            <button class="btn" onclick="init('multi')">ONLINE BATTLE</button>
        </div>
    </div>

    <div id="scr-hub" class="screen">
        <div class="box">
            <h2 class="waiting">CONNECTING TO TITAN SERVER...</h2>
            <button class="btn btn-red" onclick="location.reload()">CANCEL QUEUE</button>
        </div>
    </div>

    <div id="scr-game" class="screen">
        <div class="hud-top">
            <div>YOU: <span id="s-me" style="color:var(--neon)">0</span></div>
            <div id="opp-ui">RIVAL: <span id="s-op" style="color:var(--neon)">0</span></div>
        </div>

        <div class="exit-controls">
            <button class="btn btn-red" style="width:50px; padding:10px;" onclick="location.reload()">X</button>
            <button id="btn-gu" class="btn" style="width:100px; font-size:0.7rem;" disabled onclick="openShame()">GIVE UP</button>
            <button id="btn-dr" class="btn btn-gold" style="width:100px; font-size:0.7rem;" disabled onclick="offerDraw()">DRAW</button>
        </div>

        <div id="turn-txt" style="margin-top:100px; font-size:0.8rem; letter-spacing:2px;"></div>
        <div id="rival-last-move" style="color: var(--red); font-size: 0.7rem; height: 20px; margin-top: 5px;"></div>
        <div id="hint-box">READY TO START</div>

        <input type="number" id="guess-in" class="guess-input" inputmode="numeric" autofocus>

        <div id="online-extras" class="chat-panel">
            <div id="chat-window"></div>
            <input type="text" id="chat-in" placeholder="Type message...">
        </div>

        <div class="hud-bot">
            BATTLE MOVES: <span id="move-count" style="margin-left:15px; font-weight:900;">0</span>
        </div>
    </div>

    <script>
        let u_id = "USER-" + Math.floor(Math.random()*9999);
        let m_id = null;
        let isSolo = false;
        let secret = null;
        let loop = null;

        function init(mode) {
            u_id = document.getElementById('uname').value || u_id;
            isSolo = (mode === 'solo');

            if(isSolo) {
                document.getElementById('opp-ui').style.display='none';
                document.getElementById('online-extras').style.display='none';
                document.getElementById('btn-dr').style.display='none';
                fetch(`/api/init?u=${u_id}&s=1`).then(r=>r.json()).then(d=>{
                    m_id = d.mid;
                    startGame();
                });
            } else {
                document.getElementById('scr-menu').classList.remove('active');
                document.getElementById('scr-hub').classList.add('active');
                fetch(`/api/init?u=${u_id}`).then(()=> startGame());
            }
        }

        function startGame() {
            if(loop) clearInterval(loop);
            loop = setInterval(sync, 800);
        }

        function sync() {
            fetch(`/api/sync?u=${u_id}&m=${m_id}`).then(r=>r.json()).then(d => {
                if(!d.active && m_id) {
                    document.getElementById('death-screen').style.display='flex';
                    clearInterval(loop);
                    return;
                }
                if(d.status === "LIVE") {
                    m_id = d.mid; secret = d.target;
                    document.getElementById('scr-menu').classList.remove('active');
                    document.getElementById('scr-hub').classList.remove('active');
                    document.getElementById('scr-game').classList.add('active');

                    document.getElementById('s-me').innerText = d.scores[u_id] || 0;
                    document.getElementById('move-count').innerText = d.moves[u_id] || 0;
                    document.getElementById('hint-box').innerText = d.hint;
                    document.getElementById('rival-last-move').innerText = d.last;

                    const mCount = d.moves[u_id] || 0;
                    document.getElementById('btn-gu').disabled = (mCount < 10);
                    document.getElementById('btn-dr').disabled = (mCount < 10);

                    if(!isSolo) {
                        let o_id = Object.keys(d.scores).find(i=>i!==u_id);
                        document.getElementById('s-op').innerText = o_id ? d.scores[o_id] : 0;
                        const myTurn = (d.turn === u_id);
                        document.getElementById('guess-in').disabled = !myTurn;
                        document.getElementById('turn-txt').innerText = myTurn ? ">> YOUR TURN <<" : "OPPONENT'S TURN...";
                        document.getElementById('turn-txt').style.color = myTurn ? "var(--neon)" : "var(--red)";

                        if(d.draw_req && d.draw_req !== u_id) {
                            document.getElementById('draw-screen').style.display='flex';
                        }

                        document.getElementById('chat-window').innerHTML = d.chat.map(c=>`<div>${c}</div>`).join('');
                        document.getElementById('chat-window').scrollTop = 9999;
                    } else {
                        document.getElementById('turn-txt').innerText = "SOLO ARENA";
                    }
                }
            });
        }

        function openShame() {
            const mv = document.getElementById('move-count').innerText;
            document.getElementById('shame-body').innerText = (mv < 25) ? 
                `ONLY ${mv} TRIES? THAT IS EMBARRASSING.` : `AFTER ${mv} ATTEMPTS, YOU DESERVE TO KNOW.`;
            document.getElementById('revealed-num').innerText = secret;
            document.getElementById('shame-screen').style.display='flex';
        }

        function offerDraw() { fetch(`/api/draw_req?m=${m_id}&u=${u_id}`); }
        function drawResponse(v) { fetch(`/api/draw_ans?m=${m_id}&v=${v}`); document.getElementById('draw-screen').style.display='none'; }

        document.getElementById('guess-in').onkeyup = (e) => {
            if(e.key === 'Enter' && e.target.value) {
                fetch(`/api/move?m=${m_id}&u=${u_id}&v=${e.target.value}`);
                e.target.value = "";
            }
        };

        document.getElementById('chat-in').onkeyup = (e) => {
            if(e.key === 'Enter' && e.target.value) {
                fetch(`/api/chat?m=${m_id}&u=${u_id}&msg=${e.target.value}`);
                e.target.value = "";
            }
        };
    </script>
</body>
</html>
'''


# -----------------------------------------------------------------------------
# 4. API ENDPOINTS (THE SERVER DATA-LAYER)
# -----------------------------------------------------------------------------
@app.route('/')
def home():
    return render_template_string(UI_HTML)


@app.route('/api/init')
def api_init():
    uid = request.args.get('u')
    solo = request.args.get('s')
    titan.register_user(uid)
    if solo:
        return jsonify({"mid": titan.create_match(uid, solo=True)})
    titan.lobby.append(uid)
    return jsonify({"status": "QUEUED"})


@app.route('/api/sync')
def api_sync():
    uid = request.args.get('u')
    mid = request.args.get('m')

    if uid in titan.users:
        titan.users[uid]["ping"] = time.time()

    # Auto-matchmaking search
    if not mid or mid == 'null':
        with titan.lock:
            for k, v in titan.matches.items():
                if uid in v["players"]:
                    return jsonify({"status": "LIVE", "mid": k, "active": True})
        return jsonify({"status": "WAITING", "active": True})

    m = titan.matches.get(mid)
    if not m or not m["active"]:
        return jsonify({"active": False})

    return jsonify({
        "status": "LIVE",
        "mid": mid,
        "scores": m["scores"],
        "moves": m["moves"],
        "hint": m["hint"],
        "turn": m["players"][m["turn_idx"]],
        "target": m["target"],
        "last": m["last_action"],
        "chat": m["chat"][-6:],
        "draw_req": m["draw_requested_by"],
        "active": True
    })


@app.route('/api/move')
def api_move():
    mid = request.args.get('m')
    uid = request.args.get('u')
    val = int(request.args.get('v'))
    success, msg = titan.process_move(mid, uid, val)
    return jsonify({"success": success, "msg": msg})


@app.route('/api/chat')
def api_chat():
    m = titan.matches.get(request.args.get('m'))
    if m:
        msg = request.args.get('msg')
        m["chat"].append(f"{request.args.get('u')}: {msg}")
    return "ok"


@app.route('/api/draw_req')
def draw_req():
    m = titan.matches.get(request.args.get('m'))
    if m:
        m["draw_requested_by"] = request.args.get('u')
    return "ok"


@app.route('/api/draw_ans')
def draw_ans():
    m = titan.matches.get(request.args.get('m'))
    if m:
        if request.args.get('v') == 'true':
            m["active"] = False
        else:
            m["draw_requested_by"] = None
    return "ok"


# -----------------------------------------------------------------------------
# 5. BACKGROUND MATCHMAKER
# -----------------------------------------------------------------------------
def matchmaker_daemon():
    while True:
        if len(titan.lobby) >= 2:
            p1 = titan.lobby.pop(0)
            p2 = titan.lobby.pop(0)
            titan.create_match(p1, p2)
        time.sleep(1)


threading.Thread(target=matchmaker_daemon, daemon=True).start()

# -----------------------------------------------------------------------------
# 6. LAUNCH (PORT 8080)
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)