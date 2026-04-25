

import pygame
import socket
import threading
import json
import sys
import math
import os

#  COLORS

BG = (10,   8,  30)
PANEL = (30,  20,  70)
DARK_GRAY = (45,  30,  80)
HIGHLIGHT = (80,  50, 140)
ACCENT = (240, 220,   0)   # yellow
ACCENT2 = (140,  80, 220)   # purple
GOLD = (240, 220,   0)
WHITE = (240, 240, 240)
GRAY = (160, 140, 200)
ERROR_COL = (220,  70,  70)
GREEN = (60,  180,  80)
SNAKE_COLORS = {"player1": (240, 220, 0), "player2": (140, 80, 220)}
PIE_COLORS = {"gold": (255, 200, 60), "silver": (
    180, 180, 180), "poison": (180, 60, 200)}
OBS_COLORS = {"spike": (220, 80, 80), "wall": (100, 100, 120)}

# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

WIDTH, HEIGHT = 900, 600
FPS = 60
CELL = 16

SCREEN_SPLASH = "splash"
SCREEN_LOGIN = "login"
SCREEN_LOBBY = "lobby"
SCREEN_WAIT  = "wait"    # challenger waits for accept before customizing
SCREEN_CUSTOM = "custom"
SCREEN_MAP = "map"
SCREEN_GAME = "game"
SCREEN_END = "end"

# Your 10 tile-based themes
THEMES = {
    "stone_gray":  {"tile": "stone_gray.png",  "label": "Stone",       "line": (20, 20, 20)},
    "brick_red":   {"tile": "brick_red.png",   "label": "Brick",       "line": (15, 10, 10)},
    "tile_blue":   {"tile": "tile_blue.png",   "label": "Blue Tiles",  "line": (10, 15, 25)},
    "cobble_dark": {"tile": "cobble_dark.png", "label": "Cobblestone", "line": (10, 10, 10)},
    "ice_crack":   {"tile": "ice_crack.png",   "label": "Ice",         "line": (20, 30, 35)},
    "sand_yellow": {"tile": "sand_yellow.png", "label": "Sand",        "line": (30, 25, 10)},
    "wood_brown":  {"tile": "wood_brown.png",  "label": "Wood",        "line": (20, 12,  8)},
    "slate_dark":  {"tile": "slate_dark.png",  "label": "Slate",       "line": (12, 12, 12)},
    "air_marble":  {"tile": "air_marble.png",  "label": "Marble",      "line": (30, 30, 30)},
    "jungle_rock": {"tile": "jungle_rock.png", "label": "Jungle",      "line": (10, 20, 10)},
}
THEME_KEYS = list(THEMES.keys())

_tile_cache:  dict = {}
_board_cache: dict = {}
_bg_cache:    dict = {}

SNAKE_PALETTE = [
    ((240, 220,  0), "Yellow"),
    ((140, 80, 220), "Purple"),
    ((80, 200, 120), "Green"),
    ((100, 140, 255), "Blue"),
    ((220, 80, 80), "Red"),
    ((255, 140,  0), "Orange"),
    ((255, 105, 180), "Pink"),
    ((0, 210, 210), "Cyan"),
]

HAT_OPTIONS = ["none", "crown", "tophat", "halo", "party", "cowboy"]


# ═══════════════════════════════════════════
#  SOUND
# ═══════════════════════════════════════════

_snd_game_over = None
_snd_you_win = None
_end_sound_played = False


def init_sounds():
    global _snd_game_over, _snd_you_win
    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        go = os.path.join("resources", "sounds", "game_over.wav")
        if os.path.exists(go):
            _snd_game_over = pygame.mixer.Sound(go)
            _snd_game_over.set_volume(0.7)
            print("[SOUND] game_over.wav loaded OK")
        else:
            print(f"[SOUND] file not found: {go}")
        win = os.path.join("resources", "sounds", "you_win.mp3")
        if os.path.exists(win):
            _snd_you_win = pygame.mixer.Sound(win)
            _snd_you_win.set_volume(0.7)
            print("[SOUND] you_win.mp3 loaded OK")
        else:
            print(f"[SOUND] file not found: {win}")
    except Exception as e:
        print(f"[SOUND] error: {e}")


def play_bg_music():
    try:
        p = os.path.join("resources", "sounds", "bg_music.mp3")
        if os.path.exists(p):
            pygame.mixer.music.load(p)
            pygame.mixer.music.set_volume(0.4)
            pygame.mixer.music.play(-1)
    except Exception as e:
        print(f"[MUSIC] {e}")


def stop_bg_music():
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass


def play_end_sound(i_won: bool):
    global _end_sound_played
    if _end_sound_played:
        return
    _end_sound_played = True
    if i_won:
        try:
            p = os.path.join("resources", "sounds", "you_win.mp3")
            if os.path.exists(p):
                pygame.mixer.music.load(p)
                pygame.mixer.music.set_volume(0.8)
                pygame.mixer.music.play(0)
        except Exception as e:
            print(f"[SOUND] you_win error: {e}")
    else:
        if _snd_game_over:
            _snd_game_over.play()


def reset_end_sound():
    global _end_sound_played
    _end_sound_played = False


# ═══════════════════════════════════════════
#  NETWORK
# ═══════════════════════════════════════════

class Network:
    def __init__(self):
        self.sock = None
        self.connected = False
        self._buf = b""
        self._lock = threading.Lock()
        self._inbox = []

    def connect(self, host, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            self.connected = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return None
        except Exception as e:
            return str(e)

    def send(self, data):
        if not self.connected:
            return
        try:
            self.sock.sendall((json.dumps(data)+"\n").encode())
        except:
            self.connected = False

    def poll(self):
        with self._lock:
            msgs = list(self._inbox)
            self._inbox.clear()
        return msgs

    def _recv_loop(self):
        while self.connected:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.connected = False
                    break
                self._buf += chunk
                while b"\n" in self._buf:
                    line, self._buf = self._buf.split(b"\n", 1)
                    try:
                        with self._lock:
                            self._inbox.append(json.loads(line.decode()))
                    except:
                        pass
            except:
                self.connected = False
                break


# ═══════════════════════════════════════════
#  UI WIDGETS
# ═══════════════════════════════════════════

class InputBox:
    def __init__(self, x, y, w, h, placeholder=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.placeholder = placeholder
        self.text = ""
        self.active = False
        self.font = pygame.font.SysFont("monospace", 20)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                if len(self.text) < 32:
                    self.text += event.unicode

    def draw(self, surf, transparent=False):
        if not transparent:
            bg = ACCENT if self.active else DARK_GRAY
            brd = ACCENT if self.active else GRAY
            pygame.draw.rect(surf, bg, self.rect, border_radius=8)
            pygame.draw.rect(surf, brd, self.rect, 2, border_radius=8)
        else:
            if self.active:
                pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=4)
        display = self.text or self.placeholder
        color = WHITE if self.text else (200, 180, 220)
        txt = self.font.render(display, True, color)
        surf.blit(txt, (self.rect.x+12, self.rect.y +
                  self.rect.h//2-txt.get_height()//2))


def draw_button(surf, rect, text, font, color=None, text_color=BG, hover=False):
    c = color or ACCENT
    if hover:
        c = tuple(min(255, v+30) for v in c)
    pygame.draw.rect(surf, c, rect, border_radius=8)
    lbl = font.render(text, True, text_color)
    surf.blit(lbl, (rect.centerx-lbl.get_width()//2,
                    rect.centery-lbl.get_height()//2))


def draw_text(surf, text, font, color, x, y, center=False):
    lbl = font.render(text, True, color)
    surf.blit(lbl, (x-lbl.get_width()//2 if center else x, y))


# ═══════════════════════════════════════════
#  GAME RENDERER
# ═══════════════════════════════════════════

def _load_bg(filename: str) -> pygame.Surface | None:
    if filename in _bg_cache:
        return _bg_cache[filename]
    path = os.path.join("resources", "backgrounds", filename)
    if os.path.exists(path):
        try:
            img = pygame.image.load(path).convert()
            img = pygame.transform.scale(img, (WIDTH, HEIGHT))
            _bg_cache[filename] = img
            return img
        except Exception as e:
            print(f"[BG] {e}")
    _bg_cache[filename] = None
    return None


def _get_tile(theme_key: str):
    if theme_key in _tile_cache:
        return _tile_cache[theme_key]
    fname = THEMES.get(theme_key, {}).get("tile", "")
    path = os.path.join("resources", "tilesets", fname)
    surf = None
    if os.path.exists(path):
        try:
            surf = pygame.image.load(path).convert()
            surf = pygame.transform.scale(surf, (CELL*2, CELL*2))
        except Exception as e:
            print(f"[TILE] {e}")
    _tile_cache[theme_key] = surf
    return surf


def _get_board_surf(theme_key: str, board_w: int, board_h: int):
    cache_key = f"{theme_key}_{board_w}_{board_h}"
    if cache_key in _board_cache:
        return _board_cache[cache_key]
    bw, bh = board_w*CELL, board_h*CELL
    board = pygame.Surface((bw, bh))
    tile = _get_tile(theme_key)
    if tile:
        tw, th = tile.get_size()
        for tx in range(0, bw, tw):
            for ty in range(0, bh, th):
                board.blit(tile, (tx, ty))
        lc = THEMES.get(theme_key, {}).get("line", (0, 0, 0))
        for c in range(board_w+1):
            pygame.draw.line(board, lc, (c*CELL, 0), (c*CELL, bh), 1)
        for r in range(board_h+1):
            pygame.draw.line(board, lc, (0, r*CELL), (bw, r*CELL), 1)
    else:
        board.fill((20, 15, 35))
    _board_cache[cache_key] = board
    return board


def draw_board(surf, board_w, board_h, theme):
    bx, by = 10, 50
    board_surf = _get_board_surf(theme, board_w, board_h)
    surf.blit(board_surf, (bx, by))
    pygame.draw.rect(surf, ACCENT, (bx, by, board_w*CELL, board_h*CELL), 2)


def draw_snake(surf, body, col, dead, hat="none"):
    if not body:
        return
    dc = GRAY if dead else col
    dk = tuple(max(0, c-70) for c in dc)
    lt = tuple(min(255, c+60) for c in dc)
    bx, by = 10, 50
    r = CELL//2-1
    for i in range(len(body)-1, 0, -1):
        cx = bx+body[i][0]*CELL+CELL//2
        cy = by+body[i][1]*CELL+CELL//2
        nx = bx+body[i-1][0]*CELL+CELL//2
        ny = by+body[i-1][1]*CELL+CELL//2
        pygame.draw.line(surf, dc, (cx, cy), (nx, ny), r*2-2)
        pygame.draw.circle(surf, dc if i % 2 == 0 else dk, (cx, cy), r)
        pygame.draw.circle(surf, dk, (cx, cy), r, 1)
    hx = bx+body[0][0]*CELL+CELL//2
    hy = by+body[0][1]*CELL+CELL//2
    hr = r+3
    pygame.draw.circle(surf, dc, (hx, hy), hr)
    pygame.draw.circle(surf, dk, (hx, hy), hr, 2)
    pygame.draw.circle(surf, lt, (hx, hy), hr//2)
    if not dead:
        for ex, ey in [(-3, -3), (3, -3)]:
            pygame.draw.circle(surf, WHITE, (hx+ex, hy+ey), 2)
            pygame.draw.circle(surf, (10, 10, 10), (hx+ex, hy+ey), 1)
        pygame.draw.line(surf, ERROR_COL, (hx, hy+hr), (hx, hy+hr+4), 1)
        pygame.draw.line(surf, ERROR_COL, (hx, hy+hr+4), (hx-3, hy+hr+7), 1)
        pygame.draw.line(surf, ERROR_COL, (hx, hy+hr+4), (hx+3, hy+hr+7), 1)
        draw_hat(surf, hat, hx, hy, dc)


def draw_pie(surf, pie, tick):
    bx, by = 10, 50
    cx = bx+pie["x"]*CELL+CELL//2
    cy = by+pie["y"]*CELL+CELL//2
    col = PIE_COLORS.get(pie.get("type", "silver"), GOLD)
    r = max(3, CELL//2-2+int(2*math.sin(tick*0.15+pie["x"]+pie["y"])))
    pygame.draw.circle(surf, tuple(min(255, c+50)
                       for c in col), (cx, cy), r+2, 1)
    pygame.draw.circle(surf, col, (cx, cy), r)
    pygame.draw.circle(surf, WHITE, (cx-2, cy-2), 1)


def draw_obstacle(surf, obs):
    bx, by = 10, 50
    col = OBS_COLORS.get(obs.get("type", "wall"), GRAY)
    dk = tuple(max(0, c-40) for c in col)
    x = bx+obs["x"]*CELL+1
    y = by+obs["y"]*CELL+1
    w = CELL-2
    if obs.get("type") == "spike":
        pygame.draw.line(surf, col, (x, y), (x+w, y+w), 3)
        pygame.draw.line(surf, col, (x+w, y), (x, y+w), 3)
        pygame.draw.rect(surf, dk, (x, y, w, w), 1)
    else:
        pygame.draw.rect(surf, col, (x, y, w, w), border_radius=2)
        pygame.draw.rect(surf, dk, (x, y, w, w), 1, border_radius=2)
        pygame.draw.line(surf, dk, (x+w//2, y), (x+w//2, y+w//2), 1)
        pygame.draw.line(surf, dk, (x, y+w//2), (x+w, y+w//2), 1)


def draw_hud_player(surf, x, y, name, hp, score, col, font_sm, is_me):
    draw_text(surf, f"{name}{' (you)' if is_me else ''}", font_sm, col, x, y)
    bar_w = 220
    filled = min(bar_w, max(0, int(bar_w*hp/200)))
    bar_col = col if hp > 30 else ERROR_COL
    pygame.draw.rect(surf, DARK_GRAY, (x, y+20, bar_w, 14), border_radius=4)
    if filled:
        pygame.draw.rect(surf, bar_col, (x, y+20, filled, 14), border_radius=4)
    draw_text(surf, f"{hp} HP", font_sm, WHITE, x+bar_w+6, y+20)
    draw_text(surf, f"Score: {score}", font_sm,
              GOLD if is_me else GRAY, x, y+38)


def draw_game_screen(surf, state, my_name, p1, p2,
                     font_sm, font_med, time_left, chat_log, theme, tick,
                     customs=None):
    surf.fill(BG)
    bw = state.get("board_w", 40)
    bh = state.get("board_h", 30)
    draw_board(surf, bw, bh, theme)
    for obs in state.get("obstacles", []):
        draw_obstacle(surf, obs)
    for pie in state.get("pies", []):
        draw_pie(surf, pie, tick)

    health = state.get("health", {})
    scores = state.get("scores", health)
    customs = customs or {}

    for pname, sdata in state.get("snakes", {}).items():
        c_info = customs.get(pname, {})
        raw_col = c_info.get("color", None)
        if raw_col:
            col = tuple(raw_col)
        else:
            col = SNAKE_COLORS["player1"] if pname == p1 else SNAKE_COLORS["player2"]
        hat = c_info.get("hat", "none")
        draw_snake(surf, sdata.get("body", []), col,
                   not sdata.get("alive", True), hat=hat)

    hx = 10+bw*CELL+16
    draw_text(surf, "SNAKE BATTLE", font_med, ACCENT, hx, 8)
    draw_text(surf, f"Time: {time_left}s", font_sm,
              ERROR_COL if time_left < 30 else WHITE, hx, 38)

    elapsed = 120-time_left
    diff, dc = ("EASY", (80, 200, 80)) if elapsed < 40 else (
        ("MEDIUM", (240, 180, 0)) if elapsed < 80 else ("HARD", (220, 60, 60)))
    draw_text(surf, f"[ {diff} ]", font_sm, dc, hx, 56)

    def _pcol(pname):
        raw = customs.get(pname, {}).get("color", None)
        if raw:
            return tuple(raw)
        return SNAKE_COLORS["player1"] if pname == p1 else SNAKE_COLORS["player2"]

    h1 = health.get(p1, 100)
    s1 = scores.get(p1, h1)
    draw_hud_player(surf, hx, 88, p1, h1, s1,
                    _pcol(p1), font_sm, p1 == my_name)
    pygame.draw.line(surf, DARK_GRAY, (hx, 154), (hx+260, 154), 1)
    h2 = health.get(p2, 100)
    s2 = scores.get(p2, h2)
    draw_hud_player(surf, hx, 164, p2, h2, s2,
                    _pcol(p2), font_sm, p2 == my_name)

    pygame.draw.line(surf, DARK_GRAY, (hx, 220), (hx+260, 220), 1)
    draw_text(surf, "Pies", font_sm, GRAY, hx, 226)
    for i, (lbl, col) in enumerate([("gold   +30 pts +3 len", PIE_COLORS["gold"]),
                                    ("silver +20 pts +2 len",
                                     PIE_COLORS["silver"]),
                                    ("poison -10 pts",        PIE_COLORS["poison"])]):
        pygame.draw.circle(surf, col, (hx+7, 244+i*22), 6)
        draw_text(surf, lbl, font_sm, WHITE, hx+18, 237+i*22)

    pygame.draw.line(surf, DARK_GRAY, (hx, 308), (hx+260, 308), 1)
    draw_text(surf, "Obstacles", font_sm, GRAY, hx, 314)
    for i, (lbl, col) in enumerate([("spike  -20 pts", OBS_COLORS["spike"]),
                                    ("wall   -30 pts", OBS_COLORS["wall"])]):
        pygame.draw.rect(surf, col, (hx+1, 332+i*22, 12, 12), border_radius=2)
        draw_text(surf, lbl, font_sm, WHITE, hx+18, 332+i*22)

    pygame.draw.line(surf, DARK_GRAY, (hx, 382), (hx+260, 382), 1)
    draw_text(surf, "Chat", font_sm, GRAY, hx, 388)
    for i, line in enumerate(chat_log[-6:]):
        draw_text(surf, line[:32], font_sm, WHITE, hx, 406+i*20)

    draw_text(surf, "Arrows/WASD: move", font_sm, GRAY, hx, 530)
    draw_text(surf, "T: chat   M: map",  font_sm, GRAY, hx, 548)


# ═══════════════════════════════════════════
#  SCREENS
# ═══════════════════════════════════════════

def draw_splash(surf, font_sm, font_med):
    """First screen — background image + START GAME hover highlight."""
    bg = _load_bg("firstpage.png")
    if bg:
        surf.blit(bg, (0, 0))
    else:
        surf.fill(BG)
        lbl = font_med.render("SNAKE BATTLE", True, ACCENT)
        surf.blit(lbl, (WIDTH//2 - lbl.get_width()//2, HEIGHT//2 - 40))

    mx, my = pygame.mouse.get_pos()
    btn = pygame.Rect(288, 483, 325, 36)
    if btn.collidepoint(mx, my):
        glow = pygame.Surface((btn.w, btn.h), pygame.SRCALPHA)
        glow.fill((255, 255, 255, 45))
        surf.blit(glow, btn.topleft)


def draw_login(surf, font_sm, font_med, font_lg, inp_host, inp_port, inp_user, error):
    """Login screen — background image with inputs overlaid on the purple boxes."""
    bg = _load_bg("loginpage.png")
    if bg:
        surf.blit(bg, (0, 0))
    else:
        surf.fill(BG)

    for box in (inp_host, inp_port, inp_user):
        box.draw(surf, transparent=True)

    if error:
        e = font_sm.render(error, True, ERROR_COL)
        shadow = font_sm.render(error, True, (0, 0, 0))
        ex = WIDTH//2 - e.get_width()//2
        surf.blit(shadow, (ex+1, 430))
        surf.blit(e,      (ex,   429))

    mx, my = pygame.mouse.get_pos()
    btn = pygame.Rect(288, 481, 325, 36)
    if btn.collidepoint(mx, my):
        glow = pygame.Surface((btn.w, btn.h), pygame.SRCALPHA)
        glow.fill((255, 255, 255, 45))
        surf.blit(glow, btn.topleft)


# Lobby layout constants (from his client)
_L_X = 50
_L_W = 390
_R_X = 465
_R_W = 420
_ROW_H = 44
_ROW_GAP = 52
_LIST_Y = 155


def _lobby_player_rect(i):
    return pygame.Rect(_L_X, _LIST_Y + i*_ROW_GAP, _L_W, _ROW_H)


def _lobby_watch_rect(i):
    gy = _LIST_Y + i*_ROW_GAP
    return pygame.Rect(_R_X + _R_W - 82, gy + 4, 74, _ROW_H - 8)


def _lobby_challenge_btn():
    return pygame.Rect(_L_X, 510, 260, 44)


def _challenge_overlay_rects():
    cx, cy = WIDTH//2, HEIGHT//2
    accept = pygame.Rect(cx - 170, cy + 30, 150, 46)
    decline = pygame.Rect(cx + 20, cy + 30, 150, 46)
    return accept, decline


def draw_lobby(surf, font_sm, font_med, font_lg,
               my_name, players, selected, error,
               active_games=None,
               incoming_challenge="", challenge_sent_to=""):
    surf.fill(BG)
    CX = WIDTH//2

    title = font_lg.render("L O B B Y", True, ACCENT)
    surf.blit(title, (CX-title.get_width()//2, 28))
    me = font_sm.render(f"Logged in as:  {my_name}", True, GRAY)
    surf.blit(me, (CX-me.get_width()//2, 76))

    mx, my_pos = pygame.mouse.get_pos()

    pygame.draw.line(surf, DARK_GRAY, (_R_X-10, 105), (_R_X-10, 570), 1)

    hdr_l = font_sm.render("Online players — select to challenge:", True, GRAY)
    surf.blit(hdr_l, (_L_X, 110))

    others = [p for p in players if p != my_name]
    if not others:
        w = font_sm.render("No other players online...", True, GRAY)
        surf.blit(w, (_L_X, _LIST_Y))
    else:
        for i, name in enumerate(others):
            r = _lobby_player_rect(i)
            sel = name == selected
            bg = ACCENT if sel else (
                HIGHLIGHT if r.collidepoint(mx, my_pos) else PANEL)
            pygame.draw.rect(surf, bg, r, border_radius=8)
            pygame.draw.rect(surf, DARK_GRAY, r, 1, border_radius=8)
            lbl = font_med.render(name, True, BG if sel else WHITE)
            surf.blit(lbl, (r.x+12, r.centery-lbl.get_height()//2))

    if challenge_sent_to:
        waiting = font_sm.render(
            f"Waiting for {challenge_sent_to} to accept...", True, ACCENT)
        surf.blit(waiting, (_L_X, 514))
    else:
        btn = _lobby_challenge_btn()
        en = selected is not None
        draw_button(surf, btn, f"CHALLENGE  {selected or '...'}", font_sm,
                    color=ACCENT if en else DARK_GRAY,
                    hover=en and btn.collidepoint(mx, my_pos))

    hdr_r = font_sm.render("Active Battles:", True, GRAY)
    surf.blit(hdr_r, (_R_X, 110))

    if not active_games:
        no_b = font_sm.render("No active battles right now", True, DARK_GRAY)
        surf.blit(no_b, (_R_X, _LIST_Y))
    else:
        for i, gentry in enumerate(active_games):
            gy = _LIST_Y + i*_ROW_GAP
            row = pygame.Rect(_R_X, gy, _R_W, _ROW_H)
            pygame.draw.rect(surf, PANEL, row, border_radius=8)
            pygame.draw.rect(surf, DARK_GRAY, row, 1, border_radius=8)
            vs = font_sm.render(
                f"{gentry['player1']}  vs  {gentry['player2']}", True, WHITE)
            surf.blit(vs, (row.x+10, row.centery-vs.get_height()//2))
            wb = _lobby_watch_rect(i)
            draw_button(surf, wb, "WATCH", font_sm,
                        color=ACCENT2, hover=wb.collidepoint(mx, my_pos))

    if error:
        e = font_sm.render(error, True, ERROR_COL)
        surf.blit(e, (CX-e.get_width()//2, 572))

    # Challenge notification overlay
    if incoming_challenge:
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        surf.blit(ov, (0, 0))

        cx, cy = WIDTH//2, HEIGHT//2
        panel = pygame.Rect(cx-220, cy-90, 440, 210)
        pygame.draw.rect(surf, PANEL, panel, border_radius=14)
        pygame.draw.rect(surf, ACCENT, panel, 2, border_radius=14)

        msg_lbl = font_med.render(
            f"{incoming_challenge}  challenged you!", True, WHITE)
        surf.blit(msg_lbl, (cx-msg_lbl.get_width()//2, cy-70))
        sub_lbl = font_sm.render(
            "Do you want to accept the battle?", True, GRAY)
        surf.blit(sub_lbl, (cx-sub_lbl.get_width()//2, cy-30))

        accept_r, decline_r = _challenge_overlay_rects()
        draw_button(surf, accept_r,  "ACCEPT",  font_med,
                    color=GREEN,     hover=accept_r.collidepoint(mx, my_pos),
                    text_color=WHITE)
        draw_button(surf, decline_r, "DECLINE", font_med,
                    color=ERROR_COL, hover=decline_r.collidepoint(mx, my_pos),
                    text_color=WHITE)


def draw_map_picker(surf, font_sm, font_med, font_lg, selected_theme):
    surf.fill(BG)
    CX = WIDTH // 2
    title = font_lg.render("CHOOSE YOUR MAP", True, ACCENT)
    surf.blit(title, (CX - title.get_width()//2, 22))
    sub = font_sm.render("Pick a background for the match", True, GRAY)
    surf.blit(sub, (CX - sub.get_width()//2, 68))

    cols = 5
    pw, ph = 156, 90
    gap = 10
    total_w = cols*(pw+gap) - gap
    sx = CX - total_w//2
    sy = 96
    mx, my = pygame.mouse.get_pos()

    for i, (tkey, tcfg) in enumerate(THEMES.items()):
        ci = i % cols
        ri = i // cols
        px = sx + ci*(pw+gap)
        py = sy + ri*(ph+34)

        board_s = _get_board_surf(tkey, pw//CELL + 1, ph//CELL + 1)
        preview = pygame.transform.scale(board_s, (pw, ph))
        surf.blit(preview, (px, py))

        sel = tkey == selected_theme
        hov = pygame.Rect(px, py, pw, ph).collidepoint(mx, my)
        bc = ACCENT if sel else (ACCENT2 if hov else GRAY)
        pygame.draw.rect(surf, bc, (px, py, pw, ph), 3 if sel else 1)

        lbl = font_sm.render((">> " if sel else "") + tcfg["label"],
                             True, ACCENT if sel else WHITE)
        surf.blit(lbl, (px + pw//2 - lbl.get_width()//2, py + ph + 4))

    btn = pygame.Rect(CX-140, 510, 280, 44)
    draw_button(surf, btn,
                f"PLAY ON  {THEMES[selected_theme]['label'].upper()}",
                font_med, hover=btn.collidepoint(mx, my))
    hint = font_sm.render(
        "Click a map then press PLAY  |  ESC: back", True, GRAY)
    surf.blit(hint, (CX - hint.get_width()//2, 562))


def draw_hat(surf, hat, hx, hy, col, size=1.0):
    if hat == "crown":
        pts = [(hx-10, hy-4), (hx-10, hy-12), (hx-6, hy-8),
               (hx, hy-14), (hx+6, hy-8), (hx+10, hy-12), (hx+10, hy-4)]
        pygame.draw.polygon(surf, (255, 200, 0), pts)
        pygame.draw.polygon(surf, (200, 150, 0), pts, 1)
    elif hat == "tophat":
        pygame.draw.rect(surf, (20, 20, 20), (hx-10, hy-18, 20, 14))
        pygame.draw.rect(surf, (20, 20, 20), (hx-13, hy-5, 26, 4))
        pygame.draw.rect(surf, (180, 20, 20), (hx-10, hy-7, 20, 2))
    elif hat == "halo":
        pygame.draw.ellipse(surf, (255, 220, 0), (hx-10, hy-18, 20, 8))
        pygame.draw.ellipse(surf, (200, 160, 0), (hx-10, hy-18, 20, 8), 2)
    elif hat == "party":
        pts = [(hx, hy-20), (hx-8, hy-4), (hx+8, hy-4)]
        pygame.draw.polygon(surf, (255, 80, 200), pts)
        pygame.draw.polygon(surf, (255, 220, 0), pts, 1)
        for dx, dy, dc in [(-2, -10, (255, 255, 0)), (2, -14, (0, 255, 255)), (0, -7, (255, 100, 0))]:
            pygame.draw.circle(surf, dc, (hx+dx, hy+dy), 2)
    elif hat == "cowboy":
        # brim
        pygame.draw.ellipse(surf, (139, 90, 43), (hx-16, hy-8, 32, 8))
        pygame.draw.ellipse(surf, (101, 60, 20), (hx-16, hy-8, 32, 8), 1)
        # crown
        pygame.draw.rect(surf, (139, 90, 43), (hx-9, hy-20, 18, 13), border_radius=3)
        pygame.draw.rect(surf, (101, 60, 20), (hx-9, hy-20, 18, 13), 1, border_radius=3)
        # band
        pygame.draw.line(surf, (80, 40, 10), (hx-9, hy-9), (hx+9, hy-9), 2)


def draw_wait_screen(surf, font_sm, font_med, font_lg, target, tick):
    """Challenger waits here after sending challenge, before opponent accepts."""
    surf.fill(BG)
    CX, CY = WIDTH//2, HEIGHT//2

    title = font_lg.render("CHALLENGE SENT!", True, ACCENT)
    surf.blit(title, (CX - title.get_width()//2, CY - 120))

    sub = font_med.render(f"Waiting for  {target}  to accept...", True, WHITE)
    surf.blit(sub, (CX - sub.get_width()//2, CY - 60))

    # Animated dots
    dots = "." * (1 + (tick // 20) % 3)
    anim = font_med.render(dots, True, ACCENT)
    surf.blit(anim, (CX - anim.get_width()//2, CY - 10))

    hint = font_sm.render("ESC to cancel challenge", True, GRAY)
    surf.blit(hint, (CX - hint.get_width()//2, CY + 60))


def draw_custom_screen(surf, font_sm, font_med, font_lg, my_color, my_hat):
    surf.fill(BG)
    CX = WIDTH//2
    title = font_lg.render("DESIGN YOUR SNAKE", True, ACCENT)
    surf.blit(title, (CX-title.get_width()//2, 40))
    sub = font_sm.render("Choose your color and accessory", True, GRAY)
    surf.blit(sub, (CX-sub.get_width()//2, 90))

    draw_text(surf, "Snake Color", font_med, GRAY, 100, 180)
    for i, (col, name) in enumerate(SNAKE_PALETTE):
        r = pygame.Rect(100+i*80, 220, 60, 60)
        pygame.draw.rect(surf, col, r, border_radius=8)
        if col == my_color:
            pygame.draw.rect(surf, WHITE, r, 3, border_radius=8)
            tick = font_sm.render(">>", True, WHITE)
            surf.blit(tick, (r.centerx-tick.get_width()//2,
                             r.centery-tick.get_height()//2))
        else:
            pygame.draw.rect(surf, DARK_GRAY, r, 1, border_radius=8)
        lbl = font_sm.render(name, True, GRAY)
        surf.blit(lbl, (r.centerx-lbl.get_width()//2, r.bottom+4))

    draw_text(surf, "Accessory", font_med, GRAY, 60, 305)
    mx2, my2 = pygame.mouse.get_pos()
    hat_btn_w = 120
    hat_gap   = 10
    hat_total = len(HAT_OPTIONS) * (hat_btn_w + hat_gap) - hat_gap
    hat_sx    = CX - hat_total // 2
    for i, hat in enumerate(HAT_OPTIONS):
        r = pygame.Rect(hat_sx + i*(hat_btn_w+hat_gap), 340, hat_btn_w, 44)
        sel = hat == my_hat
        hover = r.collidepoint(mx2, my2)
        bg = ACCENT if sel else (HIGHLIGHT if hover else PANEL)
        pygame.draw.rect(surf, bg, r, border_radius=8)
        pygame.draw.rect(surf, DARK_GRAY, r, 1, border_radius=8)
        lbl = font_sm.render(hat.capitalize(), True, BG if sel else WHITE)
        surf.blit(lbl, (r.centerx-lbl.get_width()//2,
                        r.centery-lbl.get_height()//2))

    draw_text(surf, "Preview", font_med, GRAY, 650, 180)
    px, py = 720, 310
    dk = tuple(max(0, c-70) for c in my_color)
    lt = tuple(min(255, c+60) for c in my_color)
    for i, bx in enumerate([px-40, px-26, px-12]):
        pygame.draw.circle(surf, my_color if i % 2 == 0 else dk, (bx, py), 7)
    pygame.draw.circle(surf, my_color, (px, py), 10)
    pygame.draw.circle(surf, dk, (px, py), 10, 2)
    pygame.draw.circle(surf, lt, (px, py), 5)
    pygame.draw.circle(surf, WHITE, (px-3, py-3), 2)
    pygame.draw.circle(surf, (10, 10, 10), (px-3, py-3), 1)
    pygame.draw.circle(surf, WHITE, (px+3, py-3), 2)
    pygame.draw.circle(surf, (10, 10, 10), (px+3, py-3), 1)
    pygame.draw.line(surf, ERROR_COL, (px, py+10), (px, py+14), 1)
    pygame.draw.line(surf, ERROR_COL, (px, py+14), (px-3, py+17), 1)
    pygame.draw.line(surf, ERROR_COL, (px, py+14), (px+3, py+17), 1)
    draw_hat(surf, my_hat, px, py, my_color)

    btn = pygame.Rect(300, 460, 300, 48)
    draw_button(surf, btn, "NEXT: CHOOSE MAP", font_med,
                hover=btn.collidepoint(mx2, my2))
    hint = font_sm.render("ESC to go back", True, GRAY)
    surf.blit(hint, (CX-hint.get_width()//2, 524))


def draw_end(surf, font_sm, font_med, font_lg,
             my_name, winner, health, reason, p1, p2, scores=None):
    surf.fill(BG)
    CX = WIDTH//2

    won = (winner == my_name)
    msg = "YOU WIN!" if won else (
        f"{winner} wins!" if winner != "draw" else "DRAW!")
    title = font_lg.render(msg, True, GOLD if won else ERROR_COL)
    surf.blit(title, (CX-title.get_width()//2, 100))

    reason_map = {"health_depleted": "A player ran out of HP",
                  "time_limit":      "Time limit reached",
                  "opponent_disconnected": "Opponent disconnected"}
    rsn = font_sm.render(reason_map.get(reason, reason), True, GRAY)
    surf.blit(rsn, (CX-rsn.get_width()//2, 160))

    y = 210
    for name, hp in health.items():
        col = SNAKE_COLORS["player1"] if name == p1 else SNAKE_COLORS["player2"]
        sc = (scores or {}).get(name, hp)
        card = pygame.Rect(CX-200, y, 400, 80)
        pygame.draw.rect(surf, PANEL, card, border_radius=10)
        pygame.draw.rect(surf, col, card, 2, border_radius=10)
        nl = font_med.render(
            f"{name}{'  *** WINNER ***' if name == winner else ''}", True, col)
        surf.blit(nl, (CX-nl.get_width()//2, y+10))
        surf.blit(font_sm.render(f"HP: {hp}", True, WHITE), (CX-100, y+48))
        surf.blit(font_sm.render(f"Score: {sc}", True, GOLD), (CX+20, y+48))
        y += 96

    mx, my = pygame.mouse.get_pos()

    # Replay button
    replay_btn = pygame.Rect(CX-310, y+20, 260, 48)
    draw_button(surf, replay_btn, "WATCH REPLAY", font_sm,
                color=ACCENT2, hover=replay_btn.collidepoint(mx, my))

    # Back to lobby button
    lobby_btn = pygame.Rect(CX+50, y+20, 260, 48)
    draw_button(surf, lobby_btn, "BACK TO LOBBY", font_sm,
                hover=lobby_btn.collidepoint(mx, my))

    return replay_btn, lobby_btn


# ═══════════════════════════════════════════
#  APPLICATION
# ═══════════════════════════════════════════

class App:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        init_sounds()
        self.surf = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake Battle")
        self.clock = pygame.time.Clock()

        self.font_sm = pygame.font.SysFont("monospace", 16)
        self.font_med = pygame.font.SysFont("monospace", 22, bold=True)
        self.font_lg = pygame.font.SysFont("monospace", 36, bold=True)

        self.net = Network()
        self.screen = SCREEN_SPLASH
        self.error = ""
        self.my_name = ""

        # Input boxes positioned over the purple rectangles in loginpage.png
        self.inp_host = InputBox(288, 179, 325, 36, placeholder="127.0.0.1")
        self.inp_port = InputBox(288, 247, 325, 36, placeholder="5000")
        self.inp_user = InputBox(288, 315, 325, 36, placeholder="snake_king")
        self.inp_host.text = "127.0.0.1"
        self.inp_port.text = "5000"

        # Lobby state
        self.lobby_players = []
        self.selected_player = None
        self.active_games = []    # [{game_id, player1, player2}, ...]
        self.incoming_challenge = ""    # username who challenged us
        self.challenge_sent_to = ""    # username we challenged (waiting)

        # Snake customization
        self.my_color = SNAKE_PALETTE[0][0]
        self.my_hat = "none"
        self.customs = {}

        # Game state
        self.my_game_id = ""
        self.game_state = {}
        self.game_p1 = ""
        self.game_p2 = ""
        self.time_left = 120
        self.chat_log = []
        self.chat_input = ""
        self.chat_active = False
        self.tick = 0
        self.theme = "stone_gray"

        # End screen
        self.end_winner = ""
        self.end_health = {}
        self.end_scores = {}
        self.end_reason = ""
        self._end_btns = (None, None)   # (replay_btn, lobby_btn) rects

        # Replay
        self.replay_frames = []   # list of state snapshots during game
        self.replay_index = 0
        self.replay_mode = False
        self.replay_timer = 0
        self.replay_paused = False

        pygame.key.set_repeat(120, 60)

    def run(self):
        while True:
            self.clock.tick(FPS)
            self.tick += 1
            self._process_network()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                self._handle_event(event)
            self._draw()
            pygame.display.flip()

    # ── Network ────────────────────────────────────────────────────────────

    def _process_network(self):
        for msg in self.net.poll():
            t = msg.get("type")

            if t == "join_ok":
                self.my_name = msg["username"]
                self.screen = SCREEN_LOBBY

            elif t == "error":
                self.error = msg.get("msg", "Unknown error")

            elif t == "lobby":
                self.lobby_players = msg.get("players", [])
                self.active_games = msg.get("active_games", [])

            elif t == "game_start":
                self.my_game_id = msg.get("game_id", "")
                self.game_p1 = msg["player1"]
                self.game_p2 = msg["player2"]
                self.time_left = msg.get("time_limit", 120)
                self.customs = msg.get("customs", {})
                self.game_state = {
                    "board_w":   msg.get("board_w", 40),
                    "board_h":   msg.get("board_h", 30),
                    "snakes":    {},
                    "pies":      [],
                    "obstacles": [],
                    "health":    {self.game_p1: 100, self.game_p2: 100},
                    "difficulty": "easy",
                }
                self.challenge_sent_to = ""
                self.incoming_challenge = ""
                self.replay_frames = []   # reset replay buffer
                self.replay_paused = False
                play_bg_music()
                self.screen = SCREEN_GAME

            elif t == "state":
                self.game_state.update(msg)
                if "time_left" in msg:
                    self.time_left = msg["time_left"]
                # Record frame for replay
                import copy
                self.replay_frames.append(copy.deepcopy(self.game_state))

            elif t == "game_over":
                if self.screen == SCREEN_GAME:
                    self.end_winner = msg.get("winner", "")
                    self.end_health = msg.get("health", {})
                    self.end_scores = msg.get("scores", self.end_health)
                    self.end_reason = msg.get("reason", "")
                    stop_bg_music()
                    play_end_sound(self.end_winner == self.my_name)
                    self.screen = SCREEN_END

            elif t == "challenge_request":
                self.incoming_challenge = msg.get("from", "")

            elif t == "challenge_sent":
                self.challenge_sent_to = msg.get("to", "")

            elif t == "challenge_accepted":
                # Opponent accepted — now challenger customizes their snake
                self.challenge_sent_to = ""
                if self.screen == SCREEN_WAIT:
                    self.screen = SCREEN_CUSTOM

            elif t == "challenge_declined":
                self.challenge_sent_to = ""
                self.error = f"{msg.get('by', '?')} declined your challenge"
                if self.screen == SCREEN_WAIT:
                    self.screen = SCREEN_LOBBY

            elif t == "challenge_cancelled":
                by = msg.get("by", "")
                if by == self.incoming_challenge:
                    self.incoming_challenge = ""
                if by == self.challenge_sent_to:
                    self.challenge_sent_to = ""
                    self.error = f"{by} is no longer available"
                if self.screen in (SCREEN_WAIT, SCREEN_CUSTOM, SCREEN_MAP):
                    self.screen = SCREEN_LOBBY

            elif t == "chat":
                self.chat_log.append(
                    f"{msg.get('from', '?')}: {msg.get('msg', '')}")

    # ── Events ─────────────────────────────────────────────────────────────

    def _handle_event(self, event):
        {SCREEN_SPLASH: self._ev_splash,
         SCREEN_LOGIN:  self._ev_login,
         SCREEN_LOBBY:  self._ev_lobby,
         SCREEN_WAIT:   self._ev_wait,
         SCREEN_CUSTOM: self._ev_custom,
         SCREEN_MAP:    self._ev_map,
         SCREEN_GAME:   self._ev_game,
         SCREEN_END:    self._ev_end}[self.screen](event)

    def _ev_splash(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            btn = pygame.Rect(288, 483, 325, 36)
            if btn.collidepoint(event.pos):
                self.screen = SCREEN_LOGIN
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.screen = SCREEN_LOGIN

    def _ev_login(self, event):
        for b in (self.inp_host, self.inp_port, self.inp_user):
            b.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._connect()
        if event.type == pygame.MOUSEBUTTONDOWN:
            btn = pygame.Rect(288, 481, 325, 36)
            if btn.collidepoint(event.pos):
                self._connect()

    def _connect(self):
        host = self.inp_host.text.strip() or "127.0.0.1"
        user = self.inp_user.text.strip()
        try:
            port = int(self.inp_port.text.strip() or "5000")
        except:
            self.error = "Port must be a number"
            return
        if not user:
            self.error = "Please enter a username"
            return
        self.error = ""
        err = self.net.connect(host, port)
        if err:
            self.error = f"Connection failed: {err}"
            return
        self.net.send({"type": "join", "username": user,
                       "color": list(self.my_color), "hat": self.my_hat})

    def _ev_lobby(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN:
            return

        # Challenge overlay takes priority
        if self.incoming_challenge:
            accept_r, decline_r = _challenge_overlay_rects()
            if accept_r.collidepoint(event.pos):
                self.net.send({"type": "challenge_accept"})
                self.incoming_challenge = ""
                self.screen = SCREEN_CUSTOM   # challenged player now customizes too
            elif decline_r.collidepoint(event.pos):
                self.net.send({"type": "challenge_decline"})
                self.incoming_challenge = ""
            return

        # WATCH buttons (right column)
        for i, gentry in enumerate(self.active_games):
            if _lobby_watch_rect(i).collidepoint(event.pos):
                self.net.send({"type": "watch", "game_id": gentry["game_id"]})
                return

        # Player list + challenge button (left column)
        if not self.challenge_sent_to:
            others = [p for p in self.lobby_players if p != self.my_name]
            for i, name in enumerate(others):
                if _lobby_player_rect(i).collidepoint(event.pos):
                    self.selected_player = name
                    self.error = ""
            if (self.selected_player
                    and _lobby_challenge_btn().collidepoint(event.pos)):
                self.net.send({"type": "challenge", "target": self.selected_player})
                self.screen = SCREEN_WAIT

    def _ev_wait(self, event):
        # ESC cancels the pending challenge and goes back to lobby
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.net.send({"type": "challenge_cancel"})
            self.challenge_sent_to = ""
            self.selected_player   = None
            self.screen = SCREEN_LOBBY

    def _ev_custom(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            for i, (col, _) in enumerate(SNAKE_PALETTE):
                if pygame.Rect(100+i*80, 220, 60, 60).collidepoint(mx, my):
                    self.my_color = col
            hat_btn_w = 120
            hat_gap   = 10
            hat_total = len(HAT_OPTIONS) * (hat_btn_w + hat_gap) - hat_gap
            hat_sx    = WIDTH//2 - hat_total // 2
            for i, hat in enumerate(HAT_OPTIONS):
                if pygame.Rect(hat_sx + i*(hat_btn_w+hat_gap), 340, hat_btn_w, 44).collidepoint(mx, my):
                    self.my_hat = hat
            if pygame.Rect(300, 460, 300, 48).collidepoint(mx, my):
                self.net.send({"type": "update_custom",
                               "color": list(self.my_color), "hat": self.my_hat})
                self.screen = SCREEN_MAP
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.screen = SCREEN_LOBBY

    def _ev_map(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            CX = WIDTH // 2
            cols = 5
            pw, ph = 156, 90
            gap = 10
            sx = CX - (cols*(pw+gap) - gap)//2
            sy = 96
            for i, tkey in enumerate(THEME_KEYS):
                ci = i % cols
                ri = i // cols
                px = sx + ci*(pw+gap)
                py = sy + ri*(ph+34)
                if pygame.Rect(px, py, pw, ph).collidepoint(event.pos):
                    self.theme = tkey
            if pygame.Rect(CX-140, 510, 280, 44).collidepoint(event.pos):
                self.net.send({"type": "player_ready",
                               "color": list(self.my_color), "hat": self.my_hat})
                self.screen = SCREEN_LOBBY
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.screen = SCREEN_LOBBY

    def _ev_game(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m and not self.chat_active:
                self.theme = THEME_KEYS[(THEME_KEYS.index(
                    self.theme)+1) % len(THEME_KEYS)]
                return
            if event.key == pygame.K_t and not self.chat_active:
                self.chat_active = True
                self.chat_input = ""
                return

        if self.chat_active:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if self.chat_input.strip():
                        target = self.game_p2 if self.my_name == self.game_p1 else self.game_p1
                        self.net.send(
                            {"type": "chat", "to": target, "msg": self.chat_input})
                        self.chat_log.append(f"me: {self.chat_input}")
                    self.chat_active = False
                elif event.key == pygame.K_ESCAPE:
                    self.chat_active = False
                elif event.key == pygame.K_BACKSPACE:
                    self.chat_input = self.chat_input[:-1]
                elif len(self.chat_input) < 60:
                    self.chat_input += event.unicode
            return

        if event.type == pygame.KEYDOWN:
            km = {pygame.K_UP: "UP", pygame.K_w: "UP",
                  pygame.K_DOWN: "DOWN", pygame.K_s: "DOWN",
                  pygame.K_LEFT: "LEFT", pygame.K_a: "LEFT",
                  pygame.K_RIGHT: "RIGHT", pygame.K_d: "RIGHT"}
            if event.key in km:
                self.net.send({"type": "move", "dir": km[event.key]})

    def _ev_end(self, event):
        if self.replay_mode:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.replay_mode = False
                elif event.key == pygame.K_SPACE:
                    self.replay_paused = not self.replay_paused
                elif event.key == pygame.K_RIGHT:
                    # +5 seconds: server runs at ~6.67 ticks/s, client records each tick
                    # 5 seconds ≈ 33 frames
                    self.replay_index = min(
                        len(self.replay_frames)-1, self.replay_index + 33)
                elif event.key == pygame.K_LEFT:
                    self.replay_index = max(0, self.replay_index - 33)
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            replay_btn, lobby_btn = self._end_btns
            if replay_btn and replay_btn.collidepoint(event.pos):
                if self.replay_frames:
                    self.replay_mode = True
                    self.replay_index = 0
                    self.replay_timer = 0
            elif lobby_btn and lobby_btn.collidepoint(event.pos):
                self.screen = SCREEN_LOBBY
                self.game_state = {}
                self.selected_player = None
                self.chat_log = []
                self.error = ""
                self.my_game_id = ""
                self.incoming_challenge = ""
                self.challenge_sent_to = ""
                self.replay_frames = []
                self.replay_mode = False
                self.replay_paused = False
                reset_end_sound()

    # ── Draw ───────────────────────────────────────────────────────────────

    def _draw(self):
        if self.screen == SCREEN_SPLASH:
            draw_splash(self.surf, self.font_sm, self.font_med)

        elif self.screen == SCREEN_LOGIN:
            draw_login(self.surf, self.font_sm, self.font_med, self.font_lg,
                       self.inp_host, self.inp_port, self.inp_user, self.error)

        elif self.screen == SCREEN_LOBBY:
            draw_lobby(self.surf, self.font_sm, self.font_med, self.font_lg,
                       self.my_name, self.lobby_players, self.selected_player, self.error,
                       active_games=self.active_games,
                       incoming_challenge=self.incoming_challenge,
                       challenge_sent_to=self.challenge_sent_to)

        elif self.screen == SCREEN_WAIT:
            draw_wait_screen(self.surf, self.font_sm, self.font_med, self.font_lg,
                             self.selected_player or "opponent", self.tick)

        elif self.screen == SCREEN_CUSTOM:
            draw_custom_screen(self.surf, self.font_sm, self.font_med, self.font_lg,
                               self.my_color, self.my_hat)

        elif self.screen == SCREEN_MAP:
            draw_map_picker(self.surf, self.font_sm,
                            self.font_med, self.font_lg, self.theme)

        elif self.screen == SCREEN_GAME:
            draw_game_screen(self.surf, self.game_state, self.my_name,
                             self.game_p1, self.game_p2,
                             self.font_sm, self.font_med,
                             self.time_left, self.chat_log,
                             self.theme, self.tick, customs=self.customs)
            if self.chat_active:
                ov = pygame.Surface((WIDTH, 40), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 160))
                self.surf.blit(ov, (0, HEIGHT-44))
                p = self.font_sm.render(
                    f"Chat > {self.chat_input}_", True, ACCENT)
                self.surf.blit(p, (12, HEIGHT-36))

        elif self.screen == SCREEN_END:
            if self.replay_mode:
                self._draw_replay()
            else:
                self._end_btns = draw_end(
                    self.surf, self.font_sm, self.font_med, self.font_lg,
                    self.my_name, self.end_winner, self.end_health,
                    self.end_reason, self.game_p1, self.game_p2,
                    scores=self.end_scores)

    def _draw_replay(self):
        """Draw replay with pause (SPACE) and seek (LEFT/RIGHT arrows = ±5s)."""
        if not self.replay_paused:
            self.replay_timer += 1
            if self.replay_timer >= 9:
                self.replay_timer = 0
                self.replay_index += 1
                if self.replay_index >= len(self.replay_frames):
                    self.replay_index = len(self.replay_frames) - 1
                    self.replay_paused = True   # pause at end instead of auto-exit

        frame = self.replay_frames[self.replay_index]
        draw_game_screen(self.surf, frame, self.my_name,
                         self.game_p1, self.game_p2,
                         self.font_sm, self.font_med,
                         frame.get("time_left", 0),
                         [], self.theme, self.tick,
                         customs=self.customs)

        # Replay HUD — solid bar at the bottom so it never covers the game
        bar_h = 44
        bar_y = HEIGHT - bar_h
        pygame.draw.rect(self.surf, (10, 8, 30), (0, bar_y, WIDTH, bar_h))
        pygame.draw.line(self.surf, ACCENT, (0, bar_y), (WIDTH, bar_y), 1)

        total = len(self.replay_frames)
        status = "[PAUSED]" if self.replay_paused else "[REPLAY]"
        info = (f"{status}  {self.replay_index+1}/{total}  "
                f"LEFT/RIGHT: +-5s   SPACE: pause   ESC: exit")
        lbl = self.font_sm.render(info, True, ACCENT)
        self.surf.blit(lbl, (WIDTH//2 - lbl.get_width()//2, bar_y + 14))


# ═══════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════

if __name__ == "__main__":
    App().run()
