"""
Πthon Arena — Server
Usage: python3 server.py <port>

Client-server architecture over TCP.
All messages are newline-delimited JSON.
"""

import socket
import threading
import json
import sys
import random
import time
import uuid

# ═══════════════════════════════════════════
#  PROTOCOL  (send / recv)
# ═══════════════════════════════════════════


def send_msg(sock, data: dict):
    try:
        sock.sendall((json.dumps(data) + "\n").encode())
    except Exception:
        pass


def recv_msg(sock):
    buf = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                return None
            buf += chunk
            if b"\n" in buf:
                line, _ = buf.split(b"\n", 1)
                return json.loads(line.decode())
        except Exception:
            return None


# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

BOARD_W = 40
BOARD_H = 30
TICK_RATE = 0.15   # seconds per game tick
TIME_LIMIT = 120    # seconds
STARTING_HP = 100
MAX_PIES = 8
MAX_OBS = 10

PIE_TYPES_EASY = [
    {"type": "gold",   "hp": +30},
    {"type": "gold",   "hp": +30},
    {"type": "silver", "hp": +20},
    {"type": "silver", "hp": +20},
    {"type": "poison", "hp": -10},
]
PIE_TYPES_MED = [
    {"type": "gold",   "hp": +20},
    {"type": "silver", "hp": +15},
    {"type": "poison", "hp": -20},
    {"type": "poison", "hp": -20},
]
PIE_TYPES_HARD = [
    {"type": "gold",   "hp": +15},
    {"type": "silver", "hp": +10},
    {"type": "poison", "hp": -25},
    {"type": "poison", "hp": -30},
    {"type": "poison", "hp": -35},
]
OBS_TYPES = [
    {"type": "spike", "hp": -20},
    {"type": "wall",  "hp": -30},
]

OPPOSITE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}
DELTA = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}


# ═══════════════════════════════════════════
#  GAME STATE
# ═══════════════════════════════════════════

class GameState:
    def __init__(self, p1: str, p2: str):
        self.p1, self.p2 = p1, p2
        self.snakes = {
            p1: {"body": [[5, 15], [4, 15], [3, 15]],   "dir": "RIGHT", "alive": True, "growth": 0},
            p2: {"body": [[35, 15], [36, 15], [37, 15]], "dir": "LEFT", "alive": True, "growth": 0},
        }
        self.next_dir = {p1: "RIGHT", p2: "LEFT"}
        self.health = {p1: STARTING_HP, p2: STARTING_HP}
        self.scores = {p1: 0, p2: 0}
        self.pies:      list = []
        self.obstacles: list = []
        self.time_left = TIME_LIMIT
        self.running = True

        for _ in range(MAX_OBS):
            self._spawn_obstacle()
        for _ in range(MAX_PIES):
            self._spawn_pie()

    def _occupied(self):
        cells = set()
        for s in self.snakes.values():
            for seg in s["body"]:
                cells.add(tuple(seg))
        for p in self.pies:
            cells.add((p["x"], p["y"]))
        for o in self.obstacles:
            cells.add((o["x"], o["y"]))
        return cells

    def _free_cell(self):
        occupied = self._occupied()
        for _ in range(200):
            x, y = random.randint(1, BOARD_W-2), random.randint(1, BOARD_H-2)
            if (x, y) not in occupied:
                return x, y
        return None

    def _spawn_pie(self):
        c = self._free_cell()
        if c:
            pool = PIE_TYPES_EASY if self.time_left > 80 else (
                PIE_TYPES_MED if self.time_left > 40 else PIE_TYPES_HARD)
            t = random.choice(pool)
            self.pies.append(
                {"x": c[0], "y": c[1], "type": t["type"], "hp": t["hp"]})

    def _spawn_obstacle(self):
        c = self._free_cell()
        if c:
            t = random.choice(OBS_TYPES)
            self.obstacles.append(
                {"x": c[0], "y": c[1], "type": t["type"], "hp": t["hp"]})

    def set_direction(self, player, direction):
        if direction != OPPOSITE.get(self.snakes[player]["dir"]):
            self.next_dir[player] = direction

    def tick(self):
        self.time_left -= 1
        if self.time_left <= 0:
            return self._end_by_time()

        for pname, snake in self.snakes.items():
            if not snake["alive"]:
                continue

            snake["dir"] = self.next_dir[pname]
            dx, dy = DELTA[snake["dir"]]
            nx, ny = snake["body"][0][0]+dx, snake["body"][0][1]+dy

            if nx < 0 or nx >= BOARD_W or ny < 0 or ny >= BOARD_H:
                self._hit(pname, -30)
                self._respawn(pname)
                continue
            obs = next(
                (o for o in self.obstacles if o["x"] == nx and o["y"] == ny), None)
            if obs:
                self._hit(pname, obs["hp"])
                self._respawn(pname)
                continue
            if [nx, ny] in snake["body"][1:]:
                self._hit(pname, -30)
                self._respawn(pname)
                continue
            opp = self.p2 if pname == self.p1 else self.p1
            if [nx, ny] in self.snakes[opp]["body"]:
                self._hit(pname, -30)
                self._respawn(pname)
                continue

            snake["body"].insert(0, [nx, ny])

            pie = next(
                (p for p in self.pies if p["x"] == nx and p["y"] == ny), None)
            if pie:
                self._hit(pname, pie["hp"])
                if pie["hp"] > 0:
                    self.scores[pname] = self.scores.get(pname, 0) + pie["hp"]
                    snake["growth"] += max(1, pie["hp"]//10)
                self.pies.remove(pie)
                self._spawn_pie()

            if snake["growth"] > 0:
                snake["growth"] -= 1
            else:
                snake["body"].pop()

        for pname in [self.p1, self.p2]:
            if self.health[pname] <= 0:
                self.running = False
                winner = self.p2 if pname == self.p1 else self.p1
                return {"type": "game_over", "winner": winner,
                        "reason": "health_depleted",
                        "health": dict(self.health), "scores": dict(self.scores)}
        return None

    def _hit(self, player, delta):
        self.health[player] = max(0, self.health[player]+delta)

    def _respawn(self, player):
        c = self._free_cell()
        if c:
            x, y = c
            self.snakes[player].update({"body": [[x, y], [x-1, y], [x-2, y]],
                                        "dir": "RIGHT", "growth": 0})
            self.next_dir[player] = "RIGHT"

    def _end_by_time(self):
        self.running = False
        h1, h2 = self.health[self.p1], self.health[self.p2]
        winner = self.p1 if h1 > h2 else (self.p2 if h2 > h1 else "draw")
        return {"type": "game_over", "winner": winner, "reason": "time_limit",
                "health": dict(self.health), "scores": dict(self.scores)}

    def to_state_msg(self):
        elapsed = TIME_LIMIT-self.time_left
        diff = "easy" if elapsed < 40 else (
            "medium" if elapsed < 80 else "hard")
        return {
            "type":       "state",
            "snakes":     {p: {"body": s["body"], "dir": s["dir"], "alive": s["alive"]}
                           for p, s in self.snakes.items()},
            "pies":       self.pies,
            "obstacles":  self.obstacles,
            "health":     dict(self.health),
            "scores":     dict(self.scores),
            "time_left":  self.time_left,
            "difficulty": diff,
        }


# ═══════════════════════════════════════════
#  SHARED SERVER STATE
# ═══════════════════════════════════════════

lock = threading.Lock()
clients: dict = {}   # username → socket
customs: dict = {}   # username → {"color": ..., "hat": ...}
# game_id → {"state": GameState, "players": [p1,p2], "spectators": set()}
games:   dict = {}
pending: dict = {}   # challenged_username → {"from": challenger_username}
ready:   dict = {}   # username → {"opponent": str, "color": ..., "hat": ...}


# ═══════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════

def _in_game(username):
    """Return game_id if username is an active player, else None. Call under lock."""
    for gid, g in games.items():
        if username in g["players"]:
            return gid
    return None


def _spectating(username):
    """Return game_id if username is spectating, else None. Call under lock."""
    for gid, g in games.items():
        if username in g["spectators"]:
            return gid
    return None


# ═══════════════════════════════════════════
#  BROADCAST HELPERS
# ═══════════════════════════════════════════

def broadcast(data, exclude=None):
    with lock:
        targets = list(clients.items())
    for username, sock in targets:
        if exclude is None or username not in exclude:
            send_msg(sock, data)


def broadcast_game(game_id, data):
    """Send data only to players and spectators of a specific game."""
    with lock:
        g = games.get(game_id)
        if not g:
            return
        recipients = list(g["players"]) + list(g["spectators"])
        socks = [(u, clients[u]) for u in recipients if u in clients]
    for _, sock in socks:
        send_msg(sock, data)


def broadcast_lobby():
    with lock:
        in_play = set()
        spectating = set()
        active_list = []
        for gid, g in games.items():
            in_play.update(g["players"])
            spectating.update(g["spectators"])
            active_list.append({
                "game_id": gid,
                "player1": g["players"][0],
                "player2": g["players"][1],
            })
        lobby_players = [
            u for u in clients if u not in in_play and u not in spectating]
    broadcast({"type": "lobby", "players": lobby_players,
              "active_games": active_list})


# ═══════════════════════════════════════════
#  CLIENT HANDLER THREAD
# ═══════════════════════════════════════════

def handle_client(sock, addr):
    print(f"[+] Connection from {addr}")
    username = None

    try:
        # ── Phase 1: join / username ──────────────────────────────────────
        while True:
            msg = recv_msg(sock)
            if msg is None:
                return

            if msg.get("type") != "join":
                send_msg(sock, {"type": "error",
                         "msg": "Send a join message first"})
                continue

            name = msg.get("username", "").strip()
            if not name:
                send_msg(sock, {"type": "error",
                         "msg": "Username cannot be empty"})
                continue

            with lock:
                taken = name in clients
            if taken:
                send_msg(sock, {"type": "error",
                         "msg": "Username already taken"})
                continue

            username = name
            with lock:
                clients[username] = sock
                customs[username] = {
                    "color": msg.get("color", None),
                    "hat":   msg.get("hat", "none"),
                }

            send_msg(sock, {"type": "join_ok", "username": username})
            print(f"[+] '{username}' joined")
            broadcast_lobby()
            break

        # ── Phase 2: main message loop ────────────────────────────────────
        while True:
            msg = recv_msg(sock)
            if msg is None:
                break
            mtype = msg.get("type")

            if mtype == "challenge":
                target = msg.get("target", "")
                with lock:
                    t_sock = clients.get(target)
                    already_pending = target in pending
                    sender_pending = any(
                        v["from"] == username for v in pending.values())
                    t_in_game = _in_game(target) is not None
                    u_in_game = _in_game(username) is not None

                if not t_sock:
                    send_msg(sock, {"type": "error",
                             "msg": "Player not found"})
                elif target == username:
                    send_msg(sock, {"type": "error",
                             "msg": "Cannot challenge yourself"})
                elif u_in_game:
                    send_msg(sock, {"type": "error",
                             "msg": "You are already in a game"})
                elif t_in_game:
                    send_msg(
                        sock, {"type": "error", "msg": "That player is currently in a game"})
                elif already_pending:
                    send_msg(
                        sock, {"type": "error", "msg": "That player already has a pending challenge"})
                elif sender_pending:
                    send_msg(sock, {"type": "error",
                             "msg": "You already sent a challenge"})
                else:
                    with lock:
                        pending[target] = {"from": username}
                    send_msg(
                        t_sock, {"type": "challenge_request", "from": username})
                    send_msg(
                        sock,   {"type": "challenge_sent",   "to": target})

            elif mtype == "challenge_accept":
                with lock:
                    entry = pending.pop(username, None)
                if entry:
                    challenger = entry["from"]
                    with lock:
                        c_exists  = challenger in clients
                        c_in_game = _in_game(challenger) is not None
                        c_sock    = clients.get(challenger)
                    if c_exists and not c_in_game:
                        # Tell both players to go customize — record pairing in ready dict
                        with lock:
                            ready[username]   = {"opponent": challenger}
                            ready[challenger] = {"opponent": username}
                        # Notify challenger their challenge was accepted
                        if c_sock:
                            send_msg(c_sock, {"type": "challenge_accepted", "by": username})
                    else:
                        send_msg(sock, {"type": "error", "msg": "Challenger is no longer available"})
                else:
                    send_msg(sock, {"type": "error", "msg": "No pending challenge"})

            elif mtype == "player_ready":
                # Both players send this after customizing + picking map
                with lock:
                    customs[username] = {
                        "color": msg.get("color", None),
                        "hat":   msg.get("hat", "none"),
                    }
                    entry    = ready.get(username)
                    opponent = entry["opponent"] if entry else None
                    opp_ready = opponent and opponent in ready and ready[opponent].get("done")
                    if entry:
                        ready[username]["done"] = True

                if not opponent:
                    send_msg(sock, {"type": "error", "msg": "No active match setup"})
                elif opp_ready:
                    # Both ready — clean up and start
                    with lock:
                        ready.pop(username, None)
                        ready.pop(opponent, None)
                    start_game(opponent, username)
                # else: wait for opponent to also send player_ready

            elif mtype == "challenge_decline":
                with lock:
                    entry = pending.pop(username, None)
                    c_sock = clients.get(entry["from"]) if entry else None
                if c_sock:
                    send_msg(
                        c_sock, {"type": "challenge_declined", "by": username})

            elif mtype == "watch":
                game_id = msg.get("game_id", "")
                with lock:
                    g = games.get(game_id)
                    if g:
                        g["spectators"].add(username)
                        gs = g["state"]
                        p1, p2 = g["players"]
                        c1 = customs.get(p1, {"color": None, "hat": "none"})
                        c2 = customs.get(p2, {"color": None, "hat": "none"})
                if g:
                    send_msg(sock, {"type": "game_start",
                                    "game_id":    game_id,
                                    "player1":    p1,
                                    "player2":    p2,
                                    "board_w":    BOARD_W,
                                    "board_h":    BOARD_H,
                                    "time_limit": TIME_LIMIT,
                                    "customs":    {p1: c1, p2: c2}})
                    send_msg(sock, gs.to_state_msg())
                else:
                    send_msg(sock, {"type": "error",
                             "msg": "Game not found or already over"})

            elif mtype == "update_custom":
                with lock:
                    customs[username] = {
                        "color": msg.get("color", None),
                        "hat":   msg.get("hat", "none"),
                    }

            elif mtype == "move":
                d = msg.get("dir", "").upper()
                if d in ("UP", "DOWN", "LEFT", "RIGHT"):
                    with lock:
                        gid = _in_game(username)
                        gs = games[gid]["state"] if gid else None
                    if gs and username in gs.snakes:
                        gs.set_direction(username, d)
                else:
                    send_msg(sock, {"type": "error",
                             "msg": "Invalid direction"})

            elif mtype == "chat":
                target = msg.get("to", "")
                text = str(msg.get("msg", ""))[:300]
                with lock:
                    tsock = clients.get(target)
                    ssock = clients.get(username)
                if tsock:
                    send_msg(tsock, {"type": "chat",
                             "from": username, "msg": text})
                elif ssock:
                    send_msg(ssock, {"type": "error",
                             "msg": "Player not found"})

            else:
                send_msg(sock, {"type": "error",
                         "msg": f"Unknown type: {mtype}"})

    finally:
        if username:
            # Collect all state under lock, then send notifications outside
            with lock:
                clients.pop(username, None)
                customs.pop(username, None)

                # Clean up ready state
                ready_entry = ready.pop(username, None)
                ready_opponent = ready_entry["opponent"] if ready_entry else None
                if ready_opponent:
                    ready.pop(ready_opponent, None)

                # Cancel outgoing challenge (username is the challenger)
                outgoing_targets = [t for t, e in list(
                    pending.items()) if e["from"] == username]
                for t in outgoing_targets:
                    pending.pop(t, None)
                notify_challenged = [(t, clients.get(t))
                                     for t in outgoing_targets]

                # Cancel incoming challenge (username is the challenged)
                incoming = pending.pop(username, None)
                notify_challenger = (incoming["from"], clients.get(
                    incoming["from"])) if incoming else None

                # Find if username is a player in a game
                in_game_id = _in_game(username)

                # Find if username is spectating
                spec_id = _spectating(username)
                if spec_id and spec_id in games:
                    games[spec_id]["spectators"].discard(username)

            # Send cancellation messages outside lock
            for t, tsock in notify_challenged:
                if tsock:
                    send_msg(
                        tsock, {"type": "challenge_cancelled", "by": username})
            if notify_challenger:
                _, c_sock = notify_challenger
                if c_sock:
                    send_msg(
                        c_sock, {"type": "challenge_cancelled", "by": username})

            print(f"[-] '{username}' disconnected")
            broadcast_lobby()

            # Handle mid-game disconnect
            if in_game_id:
                with lock:
                    g = games.get(in_game_id)
                if g:
                    g["state"].running = False
                    opponent = [p for p in g["players"] if p != username]
                    result = {
                        "type":   "game_over",
                        "game_id": in_game_id,
                        "winner":  opponent[0] if opponent else "draw",
                        "reason":  "opponent_disconnected",
                        "health":  dict(g["state"].health),
                        "scores":  dict(g["state"].scores),
                    }
                    broadcast_game(in_game_id, result)

        sock.close()


# ═══════════════════════════════════════════
#  GAME LIFECYCLE
# ═══════════════════════════════════════════

def start_game(player1, player2):
    game_id = str(uuid.uuid4())
    gs = GameState(player1, player2)

    with lock:
        games[game_id] = {"state": gs, "players": [
            player1, player2], "spectators": set()}
        c1 = customs.get(player1, {"color": None, "hat": "none"})
        c2 = customs.get(player2, {"color": None, "hat": "none"})
        s1 = clients.get(player1)
        s2 = clients.get(player2)

    print(f"[GAME] {player1} vs {player2}  id={game_id[:8]}")

    game_msg = {
        "type":       "game_start",
        "game_id":    game_id,
        "player1":    player1,
        "player2":    player2,
        "board_w":    BOARD_W,
        "board_h":    BOARD_H,
        "time_limit": TIME_LIMIT,
        "customs":    {player1: c1, player2: c2},
    }
    state_msg = gs.to_state_msg()
    if s1:
        send_msg(s1, game_msg)
        send_msg(s1, state_msg)
    if s2:
        send_msg(s2, game_msg)
        send_msg(s2, state_msg)

    broadcast_lobby()
    threading.Thread(target=game_loop, args=(game_id,), daemon=True).start()


def game_loop(game_id):
    print(f"[GAME] Loop started for {game_id[:8]}")

    with lock:
        g = games.get(game_id)
    if not g:
        return
    gs = g["state"]

    while gs.running:
        time.sleep(TICK_RATE)
        result = gs.tick()
        broadcast_game(game_id, gs.to_state_msg())
        if result:
            result["game_id"] = game_id
            broadcast_game(game_id, result)
            print(f"[GAME] {game_id[:8]} over — {result.get('winner')} wins")
            break

    with lock:
        games.pop(game_id, None)
    broadcast_lobby()
    print(f"[GAME] {game_id[:8]} cleaned up")


# ═══════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 server.py <port>")
        sys.exit(1)

    port = int(sys.argv[1])
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("", port))
    srv.listen()
    print(f"[SERVER] Listening on port {port} ...")

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(
            conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
