import pygame
import sys
import math
import random
import numpy as np

# ==============================================================================
# SYSTEM CONFIGURATION
# ==============================================================================
WINDOW_TITLE = "ac's snake [my take] 0.1"
SNAKE_FILES_STATUS = "OFF"  # Procedural generation only, no external asset files

# Initialize Pygame
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# High-Resolution Display
WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.SCALED)
pygame.display.set_caption(WINDOW_TITLE)

clock = pygame.time.Clock()
TARGET_FPS = 120

# ==============================================================================
# COLOR PALETTE (Next-Gen Neon)
# ==============================================================================
C_BG = (12, 12, 18)
C_GRID = (30, 30, 40)
C_SNAKE_HEAD = (0, 255, 136)      # Neon Emerald
C_SNAKE_BODY = (0, 200, 100)      # Deep Emerald
C_FOOD = (255, 194, 10)           # Glowing Amber
C_TEXT = (240, 240, 250)
C_TEXT_DIM = (100, 100, 120)

# ==============================================================================
# PROCEDURAL AUDIO SYNTHESIS (Beeps n Boops)
# ==============================================================================
def play_tone(freq, duration, vol=0.3, wave_type='sine'):
    """Generates and plays a synthetic beep/boop without external files."""
    try:
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Envelope to prevent audio clicking (smooth attack/decay)
        envelope = np.ones_like(t)
        if wave_type == 'sine':
            wave = np.sin(2 * np.pi * freq * t)
            envelope = np.exp(-t * 4)  # Quick decay for "beep"
        else:
            wave = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(4 * np.pi * freq * t)
            envelope = np.exp(-t * 2)  # Longer decay for "boop"
            
        audio = wave * envelope * vol
        audio = (audio * 32767).astype(np.int16)
        audio = np.column_stack((audio, audio)) # Stereo
        
        sound = pygame.sndarray.make_sound(audio)
        sound.play()
    except Exception:
        pass # Fallback silently if numpy/audio fails

def sfx_move():
    play_tone(880, 0.05, 0.1, 'sine') # High, subtle beep

def sfx_eat():
    play_tone(440, 0.15, 0.4, 'saw')  # Warm, satisfying boop
    play_tone(880, 0.15, 0.2, 'sine') # Harmonic chime

def sfx_die():
    play_tone(150, 0.4, 0.5, 'saw')   # Low, descending boop

# ==============================================================================
# VISUAL EFFECTS HELPERS
# ==============================================================================
def draw_glow_circle(surface, color, pos, radius, intensity=3):
    """Simulates ray-traced bloom/glow using additive blending."""
    # Draw outer glow layers
    for i in range(intensity, 0, -1):
        glow_radius = radius * (1 + i * 0.6)
        glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        alpha = 40 // i
        pygame.draw.circle(glow_surface, (*color, alpha), (glow_radius, glow_radius), glow_radius)
        surface.blit(glow_surface, (pos[0] - glow_radius, pos[1] - glow_radius), special_flags=pygame.BLEND_RGB_ADD)
    
    # Draw solid core
    pygame.draw.circle(surface, color, (int(pos[0]), int(pos[1])), radius)

def draw_grid(surface):
    """Draws a subtle, high-end dot grid."""
    spacing = 40
    for x in range(0, WIDTH, spacing):
        for y in range(0, HEIGHT, spacing):
            pygame.draw.circle(surface, C_GRID, (x, y), 1.5)

# ==============================================================================
# GAME ENTITIES
# ==============================================================================
class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(2, 6)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = random.uniform(0.02, 0.05)
        self.size = random.uniform(2, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.95  # Friction
        self.vy *= 0.95
        self.life -= self.decay

    def draw(self, surface):
        if self.life > 0:
            alpha = int(self.life * 255)
            s = pygame.Surface((int(self.size*2), int(self.size*2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
            surface.blit(s, (int(self.x - self.size), int(self.y - self.size)))

class Snake:
    def __init__(self):
        self.grid_size = 40
        self.reset()
        
    def reset(self):
        self.body = [(10, 10), (9, 10), (8, 10)] # Grid coordinates
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.grow_pending = 0
        self.move_timer = 0
        self.move_interval = 0.12 # Seconds per move (smooth but responsive)
        
        # For smooth 120fps interpolation
        self.render_pos = [(x * self.grid_size + self.grid_size//2, y * self.grid_size + self.grid_size//2) for x, y in self.body]

    def handle_input(self, keys):
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            if self.direction != (0, 1): self.next_direction = (0, -1)
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            if self.direction != (0, -1): self.next_direction = (0, 1)
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            if self.direction != (1, 0): self.next_direction = (-1, 0)
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            if self.direction != (-1, 0): self.next_direction = (1, 0)

    def update(self, dt, food_pos):
        self.move_timer += dt
        
        # Smooth interpolation for rendering
        for i in range(len(self.body)):
            target_x = self.body[i][0] * self.grid_size + self.grid_size//2
            target_y = self.body[i][1] * self.grid_size + self.grid_size//2
            curr_x, curr_y = self.render_pos[i]
            # Lerp 15% per frame for buttery smooth motion
            self.render_pos[i] = (
                curr_x + (target_x - curr_x) * 0.15,
                curr_y + (target_y - curr_y) * 0.15
            )

        if self.move_timer >= self.move_interval:
            self.move_timer = 0
            self.direction = self.next_direction
            
            # Calculate new head position
            head_x, head_y = self.body[0]
            new_head = (head_x + self.direction[0], head_y + self.direction[1])
            
            # Wall Collision
            if new_head[0] < 0 or new_head[0] >= WIDTH // self.grid_size or \
               new_head[1] < 0 or new_head[1] >= HEIGHT // self.grid_size:
                return False # Dead
            
            # Self Collision
            if new_head in self.body:
                return False # Dead
                
            self.body.insert(0, new_head)
            self.render_pos.insert(0, (new_head[0] * self.grid_size + self.grid_size//2, 
                                       new_head[1] * self.grid_size + self.grid_size//2))
            
            sfx_move()
            
            # Check Food Collision
            food_grid_x = food_pos[0] // self.grid_size
            food_grid_y = food_pos[1] // self.grid_size
            
            if new_head == (food_grid_x, food_grid_y):
                self.grow_pending += 1
                sfx_eat()
                return "EAT"
                
            if self.grow_pending > 0:
                self.grow_pending -= 1
            else:
                self.body.pop()
                self.render_pos.pop()
                
        return True

    def draw(self, surface):
        # Draw body (tail to head so head renders on top)
        for i in range(len(self.body) - 1, -1, -1):
            pos = self.render_pos[i]
            is_head = (i == 0)
            color = C_SNAKE_HEAD if is_head else C_SNAKE_BODY
            radius = 16 if is_head else 14
            
            # Taper the tail
            if not is_head and i > len(self.body) - 4:
                radius = max(6, 14 - (len(self.body) - 1 - i) * 3)
                
            draw_glow_circle(surface, color, pos, radius, intensity=4 if is_head else 2)

class Food:
    def __init__(self, grid_size):
        self.grid_size = grid_size
        self.pos = (0, 0)
        self.pulse = 0
        
    def spawn(self, snake_body):
        while True:
            x = random.randint(0, (WIDTH // self.grid_size) - 1) * self.grid_size + self.grid_size//2
            y = random.randint(0, (HEIGHT // self.grid_size) - 1) * self.grid_size + self.grid_size//2
            grid_pos = (x // self.grid_size, y // self.grid_size)
            if grid_pos not in snake_body:
                self.pos = (x, y)
                break

    def update(self, dt):
        self.pulse += dt * 5

    def draw(self, surface):
        # Pulsing glow effect
        pulse_radius = 12 + math.sin(self.pulse) * 3
        draw_glow_circle(surface, C_FOOD, self.pos, pulse_radius, intensity=5)
        
        # Inner white core for "hot" look
        pygame.draw.circle(surface, (255, 255, 255), (int(self.pos[0]), int(self.pos[1])), 4)

# ==============================================================================
# MAIN GAME LOOP
# ==============================================================================
def main():
    font_title = pygame.font.SysFont("segoeui", 72, bold=True)
    font_subtitle = pygame.font.SysFont("consolas", 24)
    font_score = pygame.font.SysFont("consolas", 36, bold=True)
    
    snake = Snake()
    food = Food(snake.grid_size)
    food.spawn(snake.body)
    
    particles = []
    state = "MENU" # MENU, PLAYING, GAME_OVER
    score = 0
    high_score = 0
    
    while True:
        dt = clock.tick(TARGET_FPS) / 1000.0
        
        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if state == "MENU":
                    if event.key == pygame.K_SPACE:
                        state = "PLAYING"
                        sfx_eat() # Startup boop
                elif state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        snake.reset()
                        food.spawn(snake.body)
                        particles.clear()
                        score = 0
                        state = "PLAYING"
                        sfx_eat()
                elif state == "PLAYING":
                    snake.handle_input(pygame.key.get_pressed())

        keys = pygame.key.get_pressed()
        if state == "PLAYING":
            snake.handle_input(keys)

        # --- UPDATE ---
        if state == "PLAYING":
            result = snake.update(dt, food.pos)
            if result == "EAT":
                score += 10
                if score > high_score:
                    high_score = score
                # Spawn particles
                for _ in range(20):
                    particles.append(Particle(food.pos[0], food.pos[1], C_FOOD))
                    particles.append(Particle(food.pos[0], food.pos[1], C_SNAKE_HEAD))
                food.spawn(snake.body)
            elif result is False:
                state = "GAME_OVER"
                sfx_die()
                # Explosion of particles at head
                head_pos = snake.render_pos[0]
                for _ in range(40):
                    particles.append(Particle(head_pos[0], head_pos[1], C_SNAKE_HEAD))

        # Update particles
        particles = [p for p in particles if p.life > 0]
        for p in particles:
            p.update()
            
        food.update(dt)

        # --- DRAW ---
        screen.fill(C_BG)
        draw_grid(screen)
        
        # Draw Particles (behind entities)
        for p in particles:
            p.draw(screen)
            
        if state == "MENU":
            # Animated background snake for menu
            snake.update(dt, food.pos)
            snake.draw(screen)
            food.draw(screen)
            
            # UI
            title_surf = font_title.render("ac's snake", True, C_SNAKE_HEAD)
            title_rect = title_surf.get_rect(center=(WIDTH//2, HEIGHT//2 - 60))
            
            subtitle_surf = font_subtitle.render("[ my take ]  0.1", True, C_TEXT_DIM)
            subtitle_rect = subtitle_surf.get_rect(center=(WIDTH//2, HEIGHT//2))
            
            status_surf = font_subtitle.render(f"SYSTEM: Snake_Files = {SNAKE_FILES_STATUS}  |  Audio: Beeps_n_Boops  |  Render: Procedural Ultra", True, C_TEXT_DIM)
            status_rect = status_surf.get_rect(center=(WIDTH//2, HEIGHT//2 + 50))
            
            prompt_surf = font_subtitle.render("PRESS [SPACE] TO INITIALIZE", True, C_FOOD)
            prompt_rect = prompt_surf.get_rect(center=(WIDTH//2, HEIGHT//2 + 120))
            
            # Glow behind title
            draw_glow_circle(screen, C_SNAKE_HEAD, (WIDTH//2, HEIGHT//2 - 60), 100, intensity=5)
            
            screen.blit(title_surf, title_rect)
            screen.blit(subtitle_surf, subtitle_rect)
            screen.blit(status_surf, status_rect)
            screen.blit(prompt_surf, prompt_rect)
            
        elif state == "PLAYING" or state == "GAME_OVER":
            food.draw(screen)
            snake.draw(screen)
            
            # HUD
            score_surf = font_score.render(f"SCORE: {score}", True, C_TEXT)
            screen.blit(score_surf, (30, 30))
            
            hi_surf = font_subtitle.render(f"HIGH: {high_score}", True, C_TEXT_DIM)
            screen.blit(hi_surf, (30, 75))
            
            status_hud = font_subtitle.render(f"SNAKE_FILES: {SNAKE_FILES_STATUS}", True, (255, 80, 80))
            screen.blit(status_hud, (WIDTH - 250, 30))
            
            if state == "GAME_OVER":
                # Darken screen
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180))
                screen.blit(overlay, (0, 0))
                
                go_surf = font_title.render("SYSTEM FAILURE", True, (255, 80, 80))
                go_rect = go_surf.get_rect(center=(WIDTH//2, HEIGHT//2 - 40))
                
                retry_surf = font_subtitle.render("PRESS [R] TO REBOOT", True, C_TEXT)
                retry_rect = retry_surf.get_rect(center=(WIDTH//2, HEIGHT//2 + 30))
                
                screen.blit(go_surf, go_rect)
                screen.blit(retry_surf, retry_rect)

        pygame.display.flip()

if __name__ == "__main__":
    main()