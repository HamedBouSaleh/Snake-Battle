

import socket, threading, json, sys, random, time

#  PROTOCOL  (send / recv)

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




BOARD_W     = 40
BOARD_H     = 30
TICK_RATE   = 0.15   # seconds per game tick
TIME_LIMIT  = 120    # seconds
STARTING_HP = 100
MAX_PIES    = 8
MAX_OBS     = 10

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

OPPOSITE = {"UP":"DOWN","DOWN":"UP","LEFT":"RIGHT","RIGHT":"LEFT"}
DELTA    = {"UP":(0,-1),"DOWN":(0,1),"LEFT":(-1,0),"RIGHT":(1,0)}


#  GAME STATE

class GameState:
    def __init__(self, p1: str, p2: str):
        self.p1, self.p2 = p1, p2
        self.snakes = {
            p1: {"body":[[5,15],[4,15],[3,15]],   "dir":"RIGHT","alive":True,"growth":0},
            p2: {"body":[[35,15],[36,15],[37,15]],"dir":"LEFT", "alive":True,"growth":0},
        }
        self.next_dir  = {p1:"RIGHT", p2:"LEFT"}
        self.health    = {p1:STARTING_HP, p2:STARTING_HP}
        self.scores    = {p1:0, p2:0}   # cumulative pie points only
        self.pies:      list = []
        self.obstacles: list = []
        self.time_left  = TIME_LIMIT
        self.running    = True

        for _ in range(MAX_OBS): self._spawn_obstacle()
        for _ in range(MAX_PIES): self._spawn_pie()

    # board helpers 
    def _occupied(self):
        cells = set()
        for s in self.snakes.values():
            for seg in s["body"]: cells.add(tuple(seg))
        for p in self.pies:      cells.add((p["x"],p["y"]))
        for o in self.obstacles: cells.add((o["x"],o["y"]))
        return cells

    def _free_cell(self):
        occupied = self._occupied()
        for _ in range(200):
            x,y = random.randint(1,BOARD_W-2), random.randint(1,BOARD_H-2)
            if (x,y) not in occupied: return x,y
        return None

    def _spawn_pie(self):
        c = self._free_cell()
        if c:
            pool = PIE_TYPES_EASY if self.time_left>80 else (PIE_TYPES_MED if self.time_left>40 else PIE_TYPES_HARD)
            t = random.choice(pool)
            self.pies.append({"x":c[0],"y":c[1],"type":t["type"],"hp":t["hp"]})

    def _spawn_obstacle(self):
        c = self._free_cell()
        if c:
            t = random.choice(OBS_TYPES)
            self.obstacles.append({"x":c[0],"y":c[1],"type":t["type"],"hp":t["hp"]})

    #  Input 
    def set_direction(self, player, direction):
        if direction != OPPOSITE.get(self.snakes[player]["dir"]):
            self.next_dir[player] = direction

    #  Tick 

    def tick(self):
        self.time_left -= 1
        if self.time_left <= 0:
            return self._end_by_time()

        for pname, snake in self.snakes.items():
            if not snake["alive"]: continue

            snake["dir"] = self.next_dir[pname]
            dx,dy = DELTA[snake["dir"]]
            nx,ny = snake["body"][0][0]+dx, snake["body"][0][1]+dy

            # Wall
            if nx<0 or nx>=BOARD_W or ny<0 or ny>=BOARD_H:
                self._hit(pname,-30); self._respawn(pname); continue
            # Obstacle
            obs = next((o for o in self.obstacles if o["x"]==nx and o["y"]==ny),None)
            if obs:
                self._hit(pname,obs["hp"]); self._respawn(pname); continue
            # Self
            if [nx,ny] in snake["body"][1:]:
                self._hit(pname,-30); self._respawn(pname); continue
            # Other snake
            opp = self.p2 if pname==self.p1 else self.p1
            if [nx,ny] in self.snakes[opp]["body"]:
                self._hit(pname,-30); self._respawn(pname); continue

            # Move
            snake["body"].insert(0,[nx,ny])

            # Pie
            pie = next((p for p in self.pies if p["x"]==nx and p["y"]==ny),None)
            if pie:
                self._hit(pname, pie["hp"])
                if pie["hp"]>0:
                    self.scores[pname] = self.scores.get(pname,0) + pie["hp"]
                    snake["growth"] += max(1, pie["hp"]//10)
                self.pies.remove(pie)
                self._spawn_pie()

            # tail
            if snake["growth"]>0: snake["growth"]-=1
            else: snake["body"].pop()

        # Death check
        for pname in [self.p1,self.p2]:
            if self.health[pname]<=0:
                self.running=False
                winner = self.p2 if pname==self.p1 else self.p1
                return {"type":"game_over","winner":winner,
                        "reason":"health_depleted",
                        "health":dict(self.health),"scores":dict(self.scores)}
        return None

    def _hit(self, player, delta):
        self.health[player] = max(0, self.health[player]+delta)

    def _respawn(self, player):
        c = self._free_cell()
        if c:
            x,y = c
            self.snakes[player].update({"body":[[x,y],[x-1,y],[x-2,y]],
                                        "dir":"RIGHT","growth":0})
            self.next_dir[player]="RIGHT"

    def _end_by_time(self):
        self.running=False
        h1,h2 = self.health[self.p1],self.health[self.p2]
        winner = self.p1 if h1>h2 else (self.p2 if h2>h1 else "draw")
        return {"type":"game_over","winner":winner,"reason":"time_limit",
                "health":dict(self.health),"scores":dict(self.scores)}

    def to_state_msg(self):
        elapsed = TIME_LIMIT-self.time_left
        diff = "easy" if elapsed<40 else ("medium" if elapsed<80 else "hard")
        return {
            "type":       "state",
            "snakes":     {p:{"body":s["body"],"dir":s["dir"],"alive":s["alive"]}
                           for p,s in self.snakes.items()},
            "pies":       self.pies,
            "obstacles":  self.obstacles,
            "health":     dict(self.health),
            "scores":     dict(self.scores),
            "time_left":  self.time_left,
            "difficulty": diff,
        }


#  sHARED SERVER STATE

lock          = threading.Lock()
clients:  dict = {}   # username → socket
roles:    dict = {}   # username → "player" | "spectator"
customs:  dict = {}   # username → {"color": (r,g,b), "hat": str}
game_active   = False
game_players: list = []
current_game  = None



#  BROADCAST HELPERS


def broadcast(data, exclude=None):
    with lock: targets = list(clients.items())
    for username, sock in targets:
        if username != exclude:
            send_msg(sock, data)

def broadcast_lobby():
    with lock: players = [u for u,r in roles.items() if r=="player"]
    broadcast({"type":"lobby","players":players})


#  CLIENT HANDLER THREAD

def handle_client(sock, addr):
    global game_active, game_players, current_game
    print(f"[+] Connection from {addr}")
    username = None

    try:
        #  Phase 1: join / username 
        while True:
            msg = recv_msg(sock)
            if msg is None: return

            if msg.get("type") != "join":
                send_msg(sock,{"type":"error","msg":"Send a join message first"}); continue

            name = msg.get("username","").strip()
            if not name:
                send_msg(sock,{"type":"error","msg":"Username cannot be empty"}); continue

            with lock: taken = name in clients
            if taken:
                send_msg(sock,{"type":"error","msg":"Username already taken"}); continue

            username = name
            with lock:
                clients[username] = sock
                role = "spectator" if game_active else "player"
                roles[username]   = role
                # Store snake customization (color + hat)
                customs[username] = {
                    "color": msg.get("color", None),
                    "hat":   msg.get("hat", "none"),
                }

            send_msg(sock,{"type":"join_ok","username":username,"role":role})
            print(f"[+] '{username}' joined as {role}")
            broadcast_lobby()

            # Spectator joining mid-game gets current state immediately
            if role=="spectator" and current_game:
                send_msg(sock,{"type":"game_start",
                               "player1":current_game.p1,"player2":current_game.p2,
                               "board_w":BOARD_W,"board_h":BOARD_H,"time_limit":TIME_LIMIT})
                send_msg(sock, current_game.to_state_msg())
            break

        #  Phase 2: main message loop 
        while True:
            msg = recv_msg(sock)
            if msg is None: break
            mtype = msg.get("type")

            if mtype == "challenge":
                with lock:
                    running = game_active
                    target  = msg.get("target")
                    t_exist = target in clients
                    t_role  = roles.get(target)=="player"
                    c_role  = roles.get(username)=="player"
                if running:
                    send_msg(sock,{"type":"error","msg":"A game is already in progress"})
                elif not t_exist:
                    send_msg(sock,{"type":"error","msg":"Player not found"})
                elif not t_role or not c_role:
                    send_msg(sock,{"type":"error","msg":"Both players must be in the lobby"})
                elif target==username:
                    send_msg(sock,{"type":"error","msg":"Cannot challenge yourself"})
                else:
                    start_game(username, target)

            elif mtype == "watch":
                with lock: roles[username]="spectator"
                send_msg(sock,{"type":"watch_ok","msg":"You are now spectating"})

            elif mtype == "update_custom":
                with lock:
                    customs[username] = {
                        "color": msg.get("color", None),
                        "hat":   msg.get("hat", "none"),
                    }

            elif mtype == "move":
                d = msg.get("dir","").upper()
                if d in ("UP","DOWN","LEFT","RIGHT"):
                    if current_game and username in current_game.snakes:
                        current_game.set_direction(username,d)
                else:
                    send_msg(sock,{"type":"error","msg":"Invalid direction"})

            elif mtype == "chat":
                target = msg.get("to")
                text   = str(msg.get("msg",""))[:300]
                with lock:
                    tsock  = clients.get(target)
                    ssock  = clients.get(username)
                if tsock: send_msg(tsock,{"type":"chat","from":username,"msg":text})
                elif ssock: send_msg(ssock,{"type":"error","msg":"Player not found"})

            else:
                send_msg(sock,{"type":"error","msg":f"Unknown type: {mtype}"})

    finally:
        if username:
            with lock:
                clients.pop(username,None)
                roles.pop(username,None)
                customs.pop(username,None)
            print(f"[-] '{username}' disconnected")
            broadcast_lobby()
            # Handle mid-game disconnect
            with lock:
                in_game = username in game_players
                gp      = list(game_players)
            if in_game:
                if current_game: current_game.running=False
                opponent = [p for p in gp if p!=username]
                with lock: game_active=False; game_players.clear()
                if opponent:
                    broadcast({"type":"game_over","winner":opponent[0],
                               "reason":"opponent_disconnected",
                               "health":current_game.health if current_game else {},
                               "scores":current_game.scores if current_game else {}})
        sock.close()



#  GAME LIFECYCLE

def start_game(player1, player2):
    global game_active, game_players, current_game
    with lock:
        game_active  = True
        game_players = [player1, player2]

    print(f"[GAME] {player1} vs {player2}")
    current_game = GameState(player1, player2)

    with lock:
        c1 = customs.get(player1, {"color": None, "hat": "none"})
        c2 = customs.get(player2, {"color": None, "hat": "none"})

    broadcast({"type":"game_start","player1":player1,"player2":player2,
               "board_w":BOARD_W,"board_h":BOARD_H,"time_limit":TIME_LIMIT,
               "customs":{player1: c1, player2: c2}})
    broadcast(current_game.to_state_msg())

    threading.Thread(target=game_loop, args=(current_game,), daemon=True).start()


def game_loop(game):
    global game_active, game_players, current_game
    print("[GAME] Loop started")

    while game.running:
        time.sleep(TICK_RATE)
        result = game.tick()
        broadcast(game.to_state_msg())
        if result:
            broadcast(result)
            print(f"[GAME] Over — {result.get('winner')} wins")
            break

    with lock:
        game_active  = False
        game_players = []
        current_game = None
    print("[GAME] Back to lobby")


#  ENTRY POINT

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 server.py <port>")
        sys.exit(1)

    port = int(sys.argv[1])
    srv  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen()
    print(f"[SERVER] Listening on port {port} ...")

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn,addr), daemon=True).start()

if __name__ == "__main__":
    main()
