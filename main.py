import sys
import pygame
import math
from vector import Vec
import util
from entity import *
from world import World, Spawner
from globals import Globals


pygame.init()
pygame.display.set_caption('lifesim')
pygame.key.set_repeat()
pygame.mouse.set_visible(False)

window = pygame.display.set_mode(Globals.SIZE.tuple(), pygame.DOUBLEBUF)
clock = pygame.time.Clock()


def screen_pos(v):
    return v + Globals.SIZE/2 - player.pos

def world_pos(v):
    return v - Globals.SIZE/2 + player.pos


import assets


def new_tree():
    return Entity("Tree", assets.IMG_TREE, 0.675, health=35, solid=True, size=Vec(50, 165), post_func=tree_death)

def new_rock():
    return Entity("Rock", assets.IMG_ROCK, 1, solid=True, size=Vec(85, 50))


def new_brawler():
    return AI_Entity("Brawler", assets.IMG_BRAWLER, 0.3, 0.5, ENEMY, 6, 1, 600, 0.1, 250, post_func=brawler_loot)

def new_brawler_boss():
    return AI_Entity("Brawler Boss", assets.IMG_BRAWLER_BOSS, 0.5, 0.75, ENEMY, 75, 4, 800, 0.04, 750, take_knockback=False, size=Vec(120, 120), post_func=brawler_boss_loot)


def new_apple_pickup():
    return Pickup("Apple", assets.IMG_APPLE, 0.2, lambda: player.heal(5), condition=player.can_heal)

def new_shotgun_pickup():
    return Pickup("Shotgun", assets.IMG_SHOTGUN, 0.2, lambda: gain_powerup(shotgun))

def new_speed_pickup():
    return Pickup("Apple", assets.IMG_SPEED_SHOES, 0.2, lambda: gain_powerup(speed_shoes))

def new_shield_pickup():
    return Pickup("Shield", assets.IMG_SHIELD, 0.2, lambda: player.raise_max_health(10))

def new_metalsuit_pickup():
    return Pickup("Metalsuit", assets.IMG_METALSUIT, 0.2, lambda: gain_powerup(metalsuit))


def new_bullet(parent, team, direction, range):
    return Projectile("Bullet", assets.IMG_BULLET, 1, 1.25, team, None, 2, direction, range, parent=parent, post_func=spawn_poof, blockable=True)


def single_shot(world, parent, team, direction):
    world.add(parent.pos, new_bullet(parent, team, direction, 450))

def shotgun_shot(world, parent, team, direction):
    spread = 30
    count = 3
    current_angle = -spread/2
    for i in range(count):
        new_direction = Vec.polar(1, current_angle - direction.angle())
        world.add(parent.pos, new_bullet(parent, team, new_direction, 250))
        current_angle += spread / (count - 1)


def spawn_grave(self, world, team):
    world.add(self.pos, Entity("Grave", assets.IMG_GRAVE, 0.35, health=25, team=team))

def spawn_poof(self, world, team):
    poof = Entity("Poof", assets.IMG_POOF, 1, 0.01, NEUTRAL, lifetime=100)
    poof.rotate(random.randint(0, 360))
    world.add(self.pos, poof)
    #world.add(self.pos, Projectile("Poof", assets.IMG_POOF, 0.25, 0.75, NEUTRAL, None, 0, self.vel, 20, blockable=False, parent=self, rotate=False))


def tree_death(self, world, team):
    if random.randint(0, 1):
        world.add(self.pos, new_apple_pickup())

def brawler_loot(self, world, team):
    if random.random() < 0.25:
        loot = random.choice((new_shotgun_pickup, new_speed_pickup))
        world.add(self.pos, loot())

def brawler_boss_loot(self, world, team):
    loot = random.choice((new_metalsuit_pickup, new_shield_pickup))
    world.add(self.pos, loot())



Globals.cursor_img = assets.IMG_CURSOR_TARGET


def draw_cursor(surface):
    size = Vec(58, 58)
    cursor = pygame.transform.scale(Globals.cursor_img, size.tuple())
    pos = MOUSE_POS

    if Globals.cursor_img == assets.IMG_CURSOR_ARROW:
        pos = Vec(MOUSE_POS + size / 2)

    rect = util.rect_center(pos, size)
    surface.blit(cursor, rect)


def render_overlay(surface):
    stats = [
        "Position: " + str(player.pos.rounded()),
        "World:  " + current_world.name,
        "Health:   " + str(max(0, round(player.health))) + "/" + str(max(0, round(player.max_health))),
    ]

    for powerup in powerups:
        if powerups[powerup] > -100:
            stats.append(powerup.name + ": " + str(powerups[powerup]))

    if Globals.debug_mode:
        stats.append("# Entities: " + str(len(current_world.entities)))
        stats.append("FPS: " + str(round(clock.get_fps(), 1)))


    util.draw_meter(surface, Vec(138, Globals.SIZE.y - 35*3 - 6), Vec(200, 33), player.health/player.max_health, (80, 130, 255), (0, 0, 0), center=False)

    stat_y = Globals.SIZE.y - 15  # - 35
    for stat in stats:
        stat_y -= 35
        util.write(surface, stat, assets.MAIN_FONT, 34, Vec(10, stat_y), (255, 255, 255))

    if player.health <= 0:
        util.write(surface, "Press R to restart", assets.MAIN_FONT, 45, Globals.SIZE/2, (255, 255, 255), center=True)


    x = 0
    y = 0
    for powerup in powerups:
        if powerups[powerup] > 0:
            image_pos = Vec(Globals.SIZE.x-95, 5) + (Vec(-x * 85, y * 85))
            surface.blit(powerup.image, image_pos.tuple())
            timer_value = min(powerups[powerup]/powerup.current_max, 1)
            util.draw_meter(surface, image_pos+Vec(42, 100), Vec(50, 6), timer_value, (255, 255, 255), (100, 100, 100), center = True)

            x += 1
            if x >= 3:
                x = 0
                y += 1


def set_world(new_world):
    global current_world
    current_world.remove(player)
    current_world = new_world
    new_world.add(Vec(new_world.size/2), player)


class Player(Entity):
    def __init__(self, name, image, image_scale, speed, team, health, post_func=None, hurt_func=None):
        super().__init__(name, image, image_scale, speed, team, health, post_func=post_func)
        self.hurt_func = hurt_func
        self.is_player = True

    def control(self, keys):
        horizontal = False
        vertical = False
        direction = Vec(0, 0)
        if keys[pygame.K_a]:
            direction -= Vec(1, 0)
            horizontal = True
        if keys[pygame.K_d]:
            direction += Vec(1, 0)
            horizontal = True
        if keys[pygame.K_w]:
            direction -= Vec(0, 1)
            vertical = True
        if keys[pygame.K_s]:
            direction += Vec(0, 1)
            vertical = True
        self.accel(direction.norm() * 0.095)
        if not (horizontal or vertical):
            self.vel *= 0.92

    def hurt(self, amount, world):
        super().hurt(amount, world)
        deplete_powerup(metalsuit, amount)

    def heal(self, amount):
        self.health += amount
        self.health = min(self.health, self.max_health)

    def can_heal(self):
        return self.health < self.max_health

    def raise_max_health(self, amount):
        self.max_health += amount


class Powerup:
    def __init__(self, name, image, gain_amount):
        self.name = name
        self.image = util.scale_image(image, 0.315)
        self.gain_amount = gain_amount
        self.current_max = gain_amount

# Add time/uses from powerup
def gain_powerup(powerup, amount=None):
    if amount is None:
        amount = powerup.gain_amount
    powerups[powerup] += amount
    #powerups[powerup] = min(powerups[powerup], powerup.gain_amount)
    powerup.current_max = powerups[powerup]


# Remove time/uses from powerup
def deplete_powerup(powerup, amount):
    if powerups[powerup] > 0:
        powerups[powerup] -= amount
        powerups[powerup] = max(powerups[powerup], 0)




def debug(key, mouse_world_pos):
    if key == pygame.K_p:
        spawn_poof(player, current_world, ALLY)
    elif key == pygame.K_j:
        current_world.add(mouse_world_pos, new_brawler())
    elif key == pygame.K_u:
        current_world.add(mouse_world_pos, new_brawler_boss())
    elif key == pygame.K_m:
        current_world.add(mouse_world_pos, new_apple_pickup())

    if key == pygame.K_i:
        current_world.add(mouse_world_pos, new_shotgun_pickup())
    #if key == pygame.K_p:
    #    current_world.add(mouse_world_pos, new_grenade_pickup())
    if key == pygame.K_l:
        current_world.add(mouse_world_pos, new_shield_pickup())
    if key == pygame.K_SEMICOLON:
        current_world.add(mouse_world_pos, new_metalsuit_pickup())

    elif key == pygame.K_t:
        powerups[shotgun] += 10
    elif key == pygame.K_y:
        powerups[speed_shoes] = 10000


    elif key == pygame.K_h:
        powerups[metalsuit] += 10

    elif key == pygame.K_v:
        Globals.debug_mode = not Globals.debug_mode

    elif key == pygame.K_b:
        index = worlds.index(current_world) - 1
        index = util.wraparound(index, 0, len(worlds) - 1)
        set_world(worlds[index])

    elif key == pygame.K_n:
        index = worlds.index(current_world) + 1
        index = util.wraparound(index, 0, len(worlds) - 1)
        set_world(worlds[index])


if __name__ == "__main__":
    while True:
        worlds = []

        shotgun = Powerup("Shotgun", assets.IMG_SHOTGUN, 10)
        speed_shoes = Powerup("Speed", assets.IMG_SPEED_SHOES, 5000)
        grenade = Powerup("Grenade", assets.IMG_GRENADE, 5)
        metalsuit = Powerup("Metalsuit", assets.IMG_METALSUIT, 20)

        # Amount of time/uses left for each powerup
        powerups = {
            shotgun: 0,
            speed_shoes: 0,
            metalsuit: 0
        }

        overworld = World("Overworld", Vec(2000, 2000), (220, 200, 140), (80, 170, 90))
        worlds.append(overworld)
        current_world = overworld

        city_world = World("City", Vec(2500, 2500), (112, 250, 160), image=assets.IMG_BG_CITY)
        worlds.append(city_world)

        player_speed = 0.65
        player = Player("Player", assets.IMG_PLAYER_ALIVE, 0.275, player_speed, ALLY, 20, post_func=spawn_grave)
        overworld.add(overworld.size/2, player)

        for i in range(16):
            overworld.add(overworld.rand_pos(), new_rock())
        overworld.add_spawner(Spawner(8000, new_tree, 10, radius=1.25, pre_spawned = 10))
        overworld.add_spawner(Spawner(3000, new_brawler, 7))
        overworld.add_spawner(Spawner(30000, new_brawler_boss, 1))


        frames = 0
        while True:
            frames += 1
            Globals.delta_time = clock.tick(Globals.FPS)

            keys = pygame.key.get_pressed()
            MOUSE_POS = Vec(pygame.mouse.get_pos())
            MOUSE_WORLD_POS = world_pos(MOUSE_POS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("Exited")
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if player.health > 0:
                        if event.button == 1:
                            default_gun = True

                            if powerups[shotgun] > 0:
                                shotgun_shot(current_world, player, ALLY, MOUSE_WORLD_POS - player.pos)
                                default_gun = False
                                deplete_powerup(shotgun, 1)

                            if default_gun:
                                single_shot(current_world, player, ALLY, MOUSE_WORLD_POS - player.pos)

                elif event.type == pygame.KEYDOWN:
                    debug(event.key, MOUSE_WORLD_POS)

            if keys[pygame.K_r]:
                break

            if powerups[speed_shoes] > 0:
                player.speed = player_speed * 1.5
                deplete_powerup(speed_shoes, Globals.delta_time)
            else:
                player.speed = player_speed

            if powerups[metalsuit] > 0:
                if player.image is assets.IMG_PLAYER_ALIVE:
                    player.set_image(assets.IMG_PLAYER_METALSUIT)
                player.invincible = True
            else:
                if player.image is assets.IMG_PLAYER_METALSUIT:
                    player.set_image(assets.IMG_PLAYER_ALIVE)
                player.invincible = False


            player.control(keys)

            for s in current_world.spawners:
                s.update(current_world)
            for e in current_world.entities:
                e.update(current_world)
            for e in current_world.entities:
                for other in current_world.entities:
                    if e is not other and e.colliding(other):
                        e.collide(other, current_world)
                        e.last_collisions.add(other)
                    else:
                        e.last_collisions.discard(other)

            window.fill(current_world.outer_color)
            current_world.fg_surface.fill((0, 0, 0, 0))
            current_world.entities.sort(key = lambda e: e.pos.y + e.size.y / 2)
            for e in current_world.entities:
                e.render(current_world.fg_surface)

            blit_pos = -player.pos + Globals.SIZE/2
            current_world.render(window, blit_pos)
            render_overlay(window)
            draw_cursor(window)

            pygame.display.flip()