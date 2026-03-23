import pygame
import sys
import random
import math

pygame.init()

# --- Constants ---
WIDTH, HEIGHT = 900, 550
FPS = 60
GRAVITY = 0.6
JUMP_FORCE = -14
PLAYER_SPEED = 4
TILE = 40

WHITE   = (255, 255, 255)
BLACK   = (0,   0,   0)
RED     = (220, 40,  40)
DARK_RED= (140, 10,  10)
ORANGE  = (255, 140, 0)
YELLOW  = (255, 230, 50)
GRAY    = (80,  80,  80)
DARK    = (20,  20,  28)
SPIKE_C = (200, 200, 220)
GOAL_C  = (80,  230, 120)
LAVA_C  = (255, 80,  0)
BG1     = (25,  10,  10)
BG2     = (40,  15,  5)
DEATH_RED=(255, 0,   0)
PLATFORM_C = (60, 40, 80)
PLATFORM_EDGE = (120, 80, 160)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("RAGE JUMP")
clock = pygame.time.Clock()

# Fonts
try:
    font_big   = pygame.font.SysFont("impact", 72)
    font_med   = pygame.font.SysFont("impact", 36)
    font_small = pygame.font.SysFont("impact", 22)
    font_tiny  = pygame.font.SysFont("arial", 16)
except:
    font_big   = pygame.font.Font(None, 72)
    font_med   = pygame.font.Font(None, 36)
    font_small = pygame.font.Font(None, 22)
    font_tiny  = pygame.font.Font(None, 16)

# ── Helper ────────────────────────────────────────────────────────────────────

def draw_text(surf, text, font, color, cx, cy, shadow=True):
    if shadow:
        s = font.render(text, True, (0,0,0))
        surf.blit(s, s.get_rect(center=(cx+2, cy+2)))
    t = font.render(text, True, color)
    surf.blit(t, t.get_rect(center=(cx, cy)))

def lerp_color(a, b, t):
    return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

# ── Particle System ───────────────────────────────────────────────────────────

particles = []

def spawn_particles(x, y, color, count=12, speed=4):
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        spd   = random.uniform(1, speed)
        particles.append({
            'x': x, 'y': y,
            'vx': math.cos(angle)*spd,
            'vy': math.sin(angle)*spd - random.uniform(0,2),
            'life': random.randint(20, 40),
            'max_life': 40,
            'color': color,
            'size': random.randint(3, 7)
        })

def update_draw_particles(surf):
    for p in particles[:]:
        p['x'] += p['vx']
        p['y'] += p['vy']
        p['vy'] += 0.15
        p['life'] -= 1
        t = p['life'] / p['max_life']
        c = lerp_color((40,40,40), p['color'], t)
        r = max(1, int(p['size'] * t))
        pygame.draw.circle(surf, c, (int(p['x']), int(p['y'])), r)
        if p['life'] <= 0:
            particles.remove(p)

# ── Screen shake ──────────────────────────────────────────────────────────────

shake_timer = 0
shake_intensity = 0

def trigger_shake(intensity=8, duration=12):
    global shake_timer, shake_intensity
    shake_timer = duration
    shake_intensity = intensity

def get_shake_offset():
    global shake_timer
    if shake_timer > 0:
        shake_timer -= 1
        mag = shake_intensity * (shake_timer / 12)
        return random.randint(-int(mag), int(mag)), random.randint(-int(mag), int(mag))
    return 0, 0

# ── Rage meter ────────────────────────────────────────────────────────────────

class RageMeter:
    def __init__(self):
        self.value = 0.0          # 0–100
        self.flash = 0

    def add(self, amount):
        self.value = min(100, self.value + amount)
        self.flash = 20
        if self.value >= 100:
            return True  # signal: rage is full
        return False
    
    def __init__(self):
        self.value = 0.0
        self.flash = 0
        self.inverted = 0  # countdown frames

    def add(self, amount):
        self.value = min(100, self.value + amount)
        self.flash = 20
        if self.value >= 100:
            self.inverted = 300  # 5 seconds at 60fps
            self.value = 0       # reset meter after triggering

    def update(self):
        if self.flash > 0:
            self.flash -= 1
        if self.inverted > 0:
            self.inverted -= 1
        self.value = max(0, self.value - 0.05)

    def update(self):
        if self.flash > 0:
            self.flash -= 1
        # Slowly drain
        self.value = max(0, self.value - 0.05)

    def draw(self, surf):
        bar_w = 200
        bar_h = 18
        x, y = WIDTH - bar_w - 20, 14
        # Label
        label = font_small.render("RAGE", True, RED if self.flash%4<2 else ORANGE)
        surf.blit(label, (x - label.get_width() - 8, y))
        # Background
        pygame.draw.rect(surf, (40,0,0), (x, y, bar_w, bar_h), border_radius=4)
        # Fill
        fill = int(bar_w * self.value / 100)
        t = self.value / 100
        col = lerp_color(ORANGE, DARK_RED, t)
        if fill > 0:
            pygame.draw.rect(surf, col, (x, y, fill, bar_h), border_radius=4)
        # Border
        pygame.draw.rect(surf, RED, (x, y, bar_w, bar_h), 2, border_radius=4)
        # Emoji hints
        if self.value > 90:
            draw_text(surf, "MAX RAGE!", font_small, YELLOW, x+bar_w//2, y+bar_h+14, shadow=True)

# ── Platform ──────────────────────────────────────────────────────────────────

class Platform:
    def __init__(self, x, y, w, h=12, moving=False, mx=0, my=0, move_range=0, crumble=False, invisible=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.moving   = moving
        self.crumble  = crumble
        self.invisible= invisible
        self.crumble_timer = 0
        self.crumbling = False
        self.gone = False
        self.ox   = x
        self.oy   = y
        self.mx   = mx
        self.my   = my
        self.move_range = move_range
        self.t    = 0.0

    def update(self):
        if self.moving:
            self.t += 0.02
            self.rect.x = int(self.ox + math.sin(self.t) * self.move_range * self.mx)
            self.rect.y = int(self.oy + math.sin(self.t) * self.move_range * self.my)
        if self.crumbling:
            self.crumble_timer -= 1
            if self.crumble_timer <= 0:
                self.gone = True

    def touch(self):
        if self.crumble and not self.crumbling:
            self.crumbling = True
            self.crumble_timer = 15

    def draw(self, surf, cam_x, cam_y):
        if self.gone:
            return
        rx = self.rect.x - cam_x
        ry = self.rect.y - cam_y
        alpha = 255
        if self.crumbling:
            alpha = int(255 * (self.crumble_timer / 40))
        if self.invisible:
            if self.invisible:
                alpha = 50
            return
        color = PLATFORM_C
        if self.crumble:
            color = (100, 50, 20)
        # Main body
        pygame.draw.rect(surf, color, (rx, ry, self.rect.w, self.rect.h))
        # Top highlight edge
        pygame.draw.rect(surf, PLATFORM_EDGE, (rx, ry, self.rect.w, 4))
        if self.crumbling:
            # crack lines
            for i in range(3):
                cx2 = rx + random.randint(10, self.rect.w-10)
                pygame.draw.line(surf, (200,150,100), (cx2, ry), (cx2+random.randint(-10,10), ry+self.rect.h), 1)

# ── Spike ─────────────────────────────────────────────────────────────────────

class Spike:
    def __init__(self, x, y, count=1, direction='up'):
        self.rects = []
        self.direction = direction
        for i in range(count):
            self.rects.append(pygame.Rect(x + i*TILE//2, y, TILE//2, TILE//2))

    def draw(self, surf, cam_x, cam_y):
        for r in self.rects:
            rx = r.x - cam_x
            ry = r.y - cam_y
            hw = r.w // 2
            if self.direction == 'up':
                pts = [(rx, ry+r.h), (rx+r.w, ry+r.h), (rx+hw, ry)]
            else:
                pts = [(rx, ry), (rx+r.w, ry), (rx+hw, ry+r.h)]
            pygame.draw.polygon(surf, SPIKE_C, pts)
            pygame.draw.polygon(surf, WHITE, pts, 1)

# ── Lava tile ─────────────────────────────────────────────────────────────────

class Lava:
    def __init__(self, x, y, w):
        self.rect  = pygame.Rect(x, y, w, 20)
        self.anim  = 0

    def update(self):
        self.anim += 1

    def draw(self, surf, cam_x, cam_y):
        rx = self.rect.x - cam_x
        ry = self.rect.y - cam_y
        # Base lava
        pygame.draw.rect(surf, LAVA_C, (rx, ry, self.rect.w, self.rect.h))
        # Animated waves
        for i in range(0, self.rect.w, 16):
            wave_y = ry + 4 + int(math.sin((i + self.anim*4)*0.2) * 4)
            pygame.draw.circle(surf, YELLOW, (rx+i+8, wave_y), 5)

# ── Goal ──────────────────────────────────────────────────────────────────────

class Goal:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 32, 48)
        self.anim = 0

    def update(self):
        self.anim += 1

    def draw(self, surf, cam_x, cam_y):
        rx = self.rect.x - cam_x
        ry = self.rect.y - cam_y
        # Glow
        glow_r = 30 + int(math.sin(self.anim * 0.1) * 8)
        glow_surf = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (80, 230, 120, 50), (glow_r, glow_r), glow_r)
        surf.blit(glow_surf, (rx + self.rect.w//2 - glow_r, ry + self.rect.h//2 - glow_r))
        # Flag pole
        pygame.draw.rect(surf, WHITE, (rx + 14, ry, 4, self.rect.h))
        # Flag wave
        for i in range(4):
            wave = int(math.sin((self.anim*0.15) + i*0.5) * 3)
            pygame.draw.rect(surf, GOAL_C, (rx+18+i*4, ry+wave, 4, 18))

# ── Player ────────────────────────────────────────────────────────────────────

class Player:
    def __init__(self, x, y):
        self.reset(x, y)

    def reset(self, x, y):
        self.rect    = pygame.Rect(x, y, 28, 36)
        self.vx      = 0.0
        self.vy      = 0.0
        self.on_ground = False
        self.jumps   = 0
        self.dead    = False
        self.anim    = 0
        self.facing  = 1
        self.coyote  = 0   # coyote time frames
        self.jump_buf= 0   # jump buffer frames

    def handle_input(self, keys, inverted=False):
        if inverted:
            going_left  = keys[pygame.K_RIGHT] or keys[pygame.K_d]
            going_right = keys[pygame.K_LEFT]  or keys[pygame.K_a]
        else:
            going_left  = keys[pygame.K_LEFT]  or keys[pygame.K_a]
            going_right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        if going_left:
            self.vx = -PLAYER_SPEED
            self.facing = -1
        elif going_right:
            self.vx = PLAYER_SPEED
            self.facing = 1
        else:
            self.vx *= 0.75

        if self.jump_buf > 0:
            self.jump_buf -= 1

        if self.on_ground:
            self.coyote = 8
        elif self.coyote > 0:
            self.coyote -= 1

        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]):
            if self.jump_buf == 0:
                self.jump_buf = 6
            if self.coyote > 0 or self.jumps < 2:
                pass

    def jump(self):
        if self.coyote > 0:
            self.vy = JUMP_FORCE
            self.coyote = 0
            self.jumps = 1
        elif self.jumps < 2:
            self.vy = JUMP_FORCE * 0.85
            self.jumps += 1

    def update(self, platforms, spikes, lavas):
        if self.dead:
            return

        self.vy += GRAVITY
        if self.vy > 20:
            self.vy = 20

        # Horizontal move
        self.rect.x += int(self.vx)
        for p in platforms:
            if not p.gone and self.rect.colliderect(p.rect):
                if self.vx > 0:
                    self.rect.right = p.rect.left
                elif self.vx < 0:
                    self.rect.left = p.rect.right
                self.vx = 0

        # Vertical move
        self.on_ground = False
        self.rect.y += int(self.vy)
        for p in platforms:
            if not p.gone and self.rect.colliderect(p.rect):
                if self.vy > 0:
                    self.rect.bottom = p.rect.top
                    self.on_ground = True
                    self.jumps = 0
                    self.vy = 0
                    p.touch()
                elif self.vy < 0:
                    self.rect.top = p.rect.bottom
                    self.vy = 2

        # Death by spikes
        for spike in spikes:
            for sr in spike.rects:
                if self.rect.colliderect(sr):
                    return True

        # Death by lava
        for lava in lavas:
            if self.rect.colliderect(lava.rect):
                return True

        # Death by falling
        if self.rect.y > HEIGHT + 200:
            return True

        self.anim += 1
        return False

    def draw(self, surf, cam_x, cam_y):
        rx = self.rect.x - cam_x
        ry = self.rect.y - cam_y

        # Body
        body_col = (220, 60, 60) if not self.dead else DARK_RED
        pygame.draw.rect(surf, body_col, (rx, ry, self.rect.w, self.rect.h), border_radius=6)

        # Face direction
        ex = rx + (self.rect.w - 8) if self.facing == 1 else rx + 2
        # Eye
        pygame.draw.circle(surf, WHITE, (ex + 3, ry + 10), 5)
        pygame.draw.circle(surf, BLACK, (ex + 4, ry + 11), 3)

        # Rage expression: angry eyebrow
        brow_y = ry + 4
        if self.facing == 1:
            pygame.draw.line(surf, BLACK, (ex, brow_y+3), (ex+7, brow_y), 2)
        else:
            pygame.draw.line(surf, BLACK, (ex, brow_y), (ex+7, brow_y+3), 2)

        # Legs (walking anim)
        leg_offset = int(math.sin(self.anim * 0.25) * 5) if abs(self.vx) > 0.5 else 0
        pygame.draw.rect(surf, DARK_RED, (rx+4, ry+self.rect.h, 8, 8 + leg_offset))
        pygame.draw.rect(surf, DARK_RED, (rx+self.rect.w-12, ry+self.rect.h, 8, 8 - leg_offset))


# ── Level definitions ─────────────────────────────────────────────────────────

def build_level(n):
    """Return (platforms, spikes, lavas, goal, spawn_x, spawn_y, name, taunt)"""
    platforms = []
    spikes    = []
    lavas     = []

    if n == 0:
        name  = "LEVEL 1: Tutorial... or is it?"
        taunt = "Easy peasy!"
        spawn = (60, 300)
        goal  = Goal(1400, 220)
        # Floor sections with a gap
        platforms = [
            Platform(0,    400, 300),
            Platform(340,  400, 200),
            Platform(600,  350, 100, moving=True, mx=1, move_range=80),
            Platform(780,  300, 160),
            Platform(1000, 250, 200),
            Platform(1260, 260, 200),
        ]
        spikes = [Spike(340, 360, 4)]
        lavas  = [Lava(560, 380, 40)]

    elif n == 1:
        name  = "LEVEL 2: Getting Spiky"
        taunt = "Thought that was hard? Heh."
        spawn = (60, 200)
        goal  = Goal(1600, 100)
        platforms = [
            Platform(0,    280, 200),
            Platform(260,  240, 80),
            Platform(400,  200, 80, moving=True, mx=1, move_range=100),
            Platform(560,  260, 60),
            Platform(680,  200, 120, crumble=True),
            Platform(860,  160, 80),
            Platform(1000, 200, 60, moving=True, mx=0, my=1, move_range=60),
            Platform(1120, 140, 140),
            Platform(1320, 120, 200),
            Platform(1520, 140, 160),
        ]
        spikes = [
            Spike(260, 200, 2),
            Spike(560, 220, 2),
            Spike(860, 120, 2),
            Spike(1120, 100, 3),
        ]
        lavas  = [Lava(420, 260, 380)]

    elif n == 2:
        name  = "LEVEL 3: INVISIBLE PLATFORMS?!"
        taunt = "You'll NEVER figure this out."
        spawn = (60, 150)
        goal  = Goal(1800, 60)
        platforms = [
            Platform(0,    220, 150),
            Platform(320,  200, 80),
            Platform(510,  160, 90, invisible=True),
            Platform(760,  180, 60, invisible=True),
            Platform(880,  140, 100),
            Platform(1040, 100, 60, invisible=True),
            Platform(1160, 120, 80, crumble=True),
            Platform(1300, 80,  100),
            Platform(1460, 60,  80, invisible=True),
            Platform(1600, 80,  140),
            Platform(1760, 100, 120),
        ]
        spikes = [
            Spike(320, 160, 2),
            Spike(880, 100, 2),
            Spike(1300, 40, 3),
        ]
        lavas  = [Lava(0, 240, 1900)]

    elif n == 3:
        name  = "LEVEL 4: THE FINAL RAGE"
        taunt = "If you beat this, you WIN!"
        spawn = (60, 100)
        goal  = Goal(2200, 20)
        platforms = [
            Platform(0,    160, 120),
            Platform(180,  120, 40, crumble=True),
            Platform(420,  140, 40, invisible=True),
            Platform(520,  100, 60, crumble=True),
            Platform(740,  120, 40, invisible=True),
            Platform(840,  80,  60),
            Platform(960,  60,  40, crumble=True),
            Platform(1060, 100, 40, moving=True, mx=0, my=1, move_range=60),
            Platform(1200, 80,  60),
            Platform(1320, 60,  40, invisible=True),
            Platform(1440, 40,  60, crumble=True),
            Platform(1560, 60,  80),
            Platform(1700, 40,  100, moving=True, mx=0, my=1, move_range=100),
            Platform(1880, 60,  140),
            Platform(2080, 40,  200),
        ]
        spikes = [
            Spike(180, 80, 1),
            Spike(520, 60, 1),
            Spike(840, 40, 2),
            Spike(1200, 40, 1),
            Spike(1560, 20, 2),
            Spike(1880, 20, 3),
        ]
        lavas  = [Lava(0, 180, 2300)]

    return platforms, spikes, lavas, goal, spawn, name, taunt

# ── Death messages ────────────────────────────────────────────────────────────

DEATH_MSGS = [
    "NICE TRY.", "YOU DIED AGAIN.", "SKILL ISSUE.",
    "MAYBE GIVE UP?", "ARE YOU OK?", "THAT WAS PAINFUL TO WATCH.",
    "REALLY?", "L + RATIO", "TOUCHING GRASS MIGHT HELP.",
    "INCREDIBLE. JUST INCREDIBLE.", "HOW?", "LOL.",
    "DO YOU EVEN GAME BRO?", "ALMOST! (NOT REALLY)", "WOW.",
]

# ── Game states ───────────────────────────────────────────────────────────────

STATE_MENU   = "menu"
STATE_PLAY   = "play"
STATE_DEAD   = "dead"
STATE_WIN    = "win"
STATE_THANKS = "thanks"

# ── Main game ─────────────────────────────────────────────────────────────────

def main():
    state      = STATE_MENU
    level_n    = 0
    death_count= 0
    rage       = RageMeter()
    death_msg  = ""
    win_timer  = 0
    menu_anim  = 0

    def load_level(n):
        nonlocal player, platforms, spikes, lavas, goal, level_name, level_taunt, cam_x, cam_y
        platforms, spikes, lavas, goal, spawn, level_name, level_taunt = build_level(n)
        player = Player(*spawn)
        cam_x  = 0
        cam_y  = 0

    platforms   = []
    spikes      = []
    lavas       = []
    goal        = None
    level_name  = ""
    level_taunt = ""
    cam_x       = 0.0
    cam_y       = 0.0
    player      = None

    # Background stars
    stars = [(random.randint(0, WIDTH), random.randint(0, HEIGHT//2), random.randint(1,2)) for _ in range(80)]

    while True:
        dt = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if state == STATE_MENU:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        state = STATE_PLAY
                        level_n = 0
                        death_count = 0
                        load_level(level_n)
                        particles.clear()

                elif state == STATE_PLAY:
                    if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                        player.jump()

                elif state == STATE_DEAD:
                    if event.key == pygame.K_r:
                        state = STATE_PLAY
                        load_level(level_n)
                        particles.clear()
                    if event.key == pygame.K_q:
                        state = STATE_MENU

                elif state == STATE_WIN:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        if level_n + 1 < 4:
                            level_n += 1
                            state = STATE_PLAY
                            load_level(level_n)
                            particles.clear()
                        else:
                            state = STATE_THANKS

                elif state == STATE_THANKS:
                    if event.key == pygame.K_RETURN:
                        state = STATE_MENU
                        death_count = 0

        # ── UPDATE ──────────────────────────────────────────────────────────

        menu_anim += 1
        rage.update()

        if state == STATE_PLAY:
            keys = pygame.key.get_pressed()
            player.handle_input(keys, inverted=(rage.inverted > 0))

            for p in platforms:
                p.update()
            for lava in lavas:
                lava.update()
            if goal:
                goal.update()

            died = player.update(platforms, spikes, lavas)

            if died:
                spawn_particles(player.rect.centerx, player.rect.centery, RED, 25, 6)
                trigger_shake(10, 18)
                rage.add(40)
                death_count += 1
                death_msg = random.choice(DEATH_MSGS)
                state = STATE_DEAD

            # Goal check
            if goal and player.rect.colliderect(goal.rect):
                spawn_particles(player.rect.centerx, player.rect.centery, GOAL_C, 30, 5)
                trigger_shake(4, 8)
                state = STATE_WIN
                win_timer = 0

            # Camera — smoothly follow player
            target_cx = player.rect.centerx - WIDTH // 2
            target_cy = player.rect.centery - HEIGHT // 2
            cam_x += (target_cx - cam_x) * 0.1
            cam_y += (target_cy - cam_y) * 0.1
            cam_y = max(0, cam_y)

        elif state == STATE_WIN:
            win_timer += 1

        # ── DRAW ────────────────────────────────────────────────────────────

        ox, oy = get_shake_offset()

        # Background gradient
        for row in range(HEIGHT):
            t = row / HEIGHT
            c = lerp_color(BG1, BG2, t)
            pygame.draw.line(screen, c, (0, row), (WIDTH, row))


        # Stars
        for sx, sy, sr in stars:
            twinkle = int(150 + 105 * math.sin(menu_anim*0.03 + sx))
            pygame.draw.circle(screen, (twinkle, twinkle//2, twinkle//3), (sx, sy), sr)

        if state == STATE_MENU:
            # Animated title
            ty = HEIGHT//2 - 80 + int(math.sin(menu_anim*0.05)*8)
            draw_text(screen, "RAGE", font_big, RED, WIDTH//2, ty)
            draw_text(screen, "A RAGE PLATFORMER", font_small, ORANGE, WIDTH//2, ty+70)
            draw_text(screen, "4 LEVELS OF PURE SUFFERING", font_small, YELLOW, WIDTH//2, ty+100)
            draw_text(screen, "PRESS ENTER TO BEGIN YOUR SUFFERING", font_small, WHITE, WIDTH//2, HEIGHT//2+80)
            draw_text(screen, "ARROW KEYS / WASD  ·  SPACE TO JUMP  ·  DOUBLE JUMP ALLOWED", font_tiny, GRAY, WIDTH//2, HEIGHT-40)

        elif state in (STATE_PLAY, STATE_DEAD, STATE_WIN):
            # World
            surf = screen

            for p in platforms:
                p.draw(surf, int(cam_x)+ox, int(cam_y)+oy)
            for s in spikes:
                s.draw(surf, int(cam_x)+ox, int(cam_y)+oy)
            for l in lavas:
                l.draw(surf, int(cam_x)+ox, int(cam_y)+oy)
            if goal:
                goal.draw(surf, int(cam_x)+ox, int(cam_y)+oy)

            if player:
                player.draw(surf, int(cam_x)+ox, int(cam_y)+oy)

            update_draw_particles(surf)

            if rage.inverted > 0:
                draw_text(screen, "CONTROLS INVERTED!", font_small, RED, WIDTH//2, 50)

            # HUD
            rage.draw(screen)
            draw_text(screen, f"DEATHS: {death_count}", font_small, WHITE, 80, 22)
            draw_text(screen, level_name, font_small, ORANGE, WIDTH//2, 22)

            # Taunt (bottom)
            draw_text(screen, f'"{level_taunt}"', font_tiny, (180,180,180), WIDTH//2, HEIGHT-18)

            if state == STATE_DEAD:
                # Dim overlay
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0,0,0,160))
                screen.blit(overlay, (0,0))
                draw_text(screen, "YOU DIED", font_big, DEATH_RED, WIDTH//2, HEIGHT//2-70)
                draw_text(screen, death_msg, font_med, ORANGE, WIDTH//2, HEIGHT//2)
                draw_text(screen, f"DEATH #{death_count}", font_small, WHITE, WIDTH//2, HEIGHT//2+50)
                draw_text(screen, "[R] RETRY   [Q] MENU", font_small, GRAY, WIDTH//2, HEIGHT//2+90)

            elif state == STATE_WIN:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                alpha = min(180, win_timer * 6)
                overlay.fill((0,0,0,alpha))
                screen.blit(overlay, (0,0))
                if win_timer > 10:
                    draw_text(screen, "LEVEL CLEAR!", font_big, GOAL_C, WIDTH//2, HEIGHT//2-60)
                    if level_n + 1 < 4:
                        draw_text(screen, "PRESS ENTER FOR MORE PAIN", font_med, YELLOW, WIDTH//2, HEIGHT//2+10)
                    else:
                        draw_text(screen, "PRESS ENTER TO SEE THE ENDING", font_med, YELLOW, WIDTH//2, HEIGHT//2+10)

        elif state == STATE_THANKS:
            draw_text(screen, "YOU ACTUALLY WON.", font_big, GOAL_C, WIDTH//2, HEIGHT//2-100)
            draw_text(screen, f"TOTAL DEATHS: {death_count}", font_med, WHITE, WIDTH//2, HEIGHT//2-20)
            rage_msg = "IMPRESSIVE CALMNESS" if death_count < 20 else ("THAT WAS ROUGH" if death_count < 60 else "YOUR KEYBOARD MUST HATE YOU")
            draw_text(screen, rage_msg, font_med, ORANGE, WIDTH//2, HEIGHT//2+40)
            draw_text(screen, "THANKS FOR PLAYING  ·  PRESS ENTER", font_small, GRAY, WIDTH//2, HEIGHT-50)
            # Rain particles
            if random.random() < 0.4:
                spawn_particles(random.randint(0,WIDTH), 0, GOAL_C, 1, 2)
            update_draw_particles(screen)
            if (pygame.key.get_pressed()[pygame.K_RETURN]):
                return(STATE_MENU)

        pygame.display.flip()

if __name__ == "__main__":
    main()
