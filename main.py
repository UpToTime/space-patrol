from __future__ import division


#kivy modules 
from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.base import EventLoop
from kivy.core.window import Window
from kivy.core.image import Image
from kivy.graphics.instructions import RenderContext
from kivy.graphics import Mesh
from kivy.uix.label import Label
from kivy.uix.image import Image as Im
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import NumericProperty,ListProperty,ObjectProperty
from kivy.uix.widget import Widget
from kivy import platform
from kivy.utils import get_color_from_hex
from kivy.core.audio import SoundLoader


#python modules 
from collections import namedtuple
import json
import math
from random import randint, random

#--------part one game sound ------------
#although it was implemented the as the last step 

class MultiAudio:
    _next = 0

    def __init__(self, filename, count):
        self.buf = [SoundLoader.load(filename)
                    for i in range(count)]

    def play(self):
        self.buf[self._next].play()
        self._next = (self._next + 1) % len(self.buf)

sndfx_hit = MultiAudio('sound/hit.wav', 5)
sndfx_laser = MultiAudio('sound/laser.wav', 5)
sndfx_game = MultiAudio('sound/amb-1.wav', 7)
sndfx_home = MultiAudio('sound/amb2.wav', 3)
sndfx_player_hit= MultiAudio('sound/die.wav', 4)





#----------- part 2 particles builder and shader implementation----
#the first step done during development
UVMapping = namedtuple('UVMapping', 'u0 v0 u1 v1 su sv')


def load_atlas(atlas_name):
    with open(atlas_name, 'rb') as f:
        atlas = json.loads(f.read().decode('utf-8'))

    tex_name, mapping = atlas.popitem()
    tex = Image(tex_name).texture
    tex_width, tex_height = tex.size

    uvmap = {}
    for name, val in mapping.items():
        x0, y0, w, h = val
        x1, y1 = x0 + w, y0 + h
        uvmap[name] = UVMapping(
            x0 / tex_width, 1 - y1 / tex_height,
            x1 / tex_width, 1 - y0 / tex_height,
            0.5 * w, 0.5 * h)

    return tex, uvmap


class Particle:
    x = 0
    y = 0
    size = 1

    def __init__(self, parent, i):
        self.parent = parent
        self.vsize = parent.vsize
        self.base_i = 4 * i * self.vsize
        self.reset(created=True)

    def update(self):
        for i in range(self.base_i,
                       self.base_i + 4 * self.vsize,
                       self.vsize):
            self.parent.vertices[i:i + 3] = (
                self.x, self.y, self.size)

    def reset(self, created=False):
        raise NotImplementedError()

    def advance(self, nap):
        raise NotImplementedError()


class PSWidget(Widget):
    indices = []
    vertices = []
    particles = []

    def __init__(self, **kwargs):
        Widget.__init__(self, **kwargs)
        self.canvas = RenderContext(use_parent_projection=True)
        self.canvas.shader.source = self.glsl
        #Clochedule_interval(self.update_glsl, 60 ** -1)
        
        self.vfmt = (
            (b'vCenter', 2, 'float'),
            (b'vScale', 1, 'float'),
            (b'vPosition', 2, 'float'),
            (b'vTexCoords0', 2, 'float'),
        )

        self.vsize = sum(attr[1] for attr in self.vfmt)

        self.texture, self.uvmap = load_atlas(self.atlas)

    def make_particles(self, Cls, num):
        count = len(self.particles)
        uv = self.uvmap[Cls.tex_name]

        for i in range(count, count + num):
            j = 4 * i
            self.indices.extend((
                j, j + 1, j + 2, j + 2, j + 3, j))

            self.vertices.extend((
                0, 0, 1, -uv.su, -uv.sv, uv.u0, uv.v1,
                0, 0, 1,  uv.su, -uv.sv, uv.u1, uv.v1,
                0, 0, 1,  uv.su,  uv.sv, uv.u1, uv.v0,
                0, 0, 1, -uv.su,  uv.sv, uv.u0, uv.v0,
            ))

            p = Cls(self, i)
            self.particles.append(p)

    def update_glsl(self, nap):
        for p in self.particles:
            p.advance(nap)
            p.update()

        self.canvas.clear()

        with self.canvas:
            Mesh(fmt=self.vfmt, mode='triangles',
                 indices=self.indices, vertices=self.vertices,
                 texture=self.texture)

# blue objects created resemble bckgrnd desgin particles
class Star(Particle):
    plane = 1
    tex_name = 'b'

    def reset(self, created=False):
        self.plane = randint(1, 3)

        if created:
            self.x = random() * self.parent.width
        else:
            self.x = self.parent.width

        self.y = random() * self.parent.height
        self.size = 0.1 * self.plane

    def advance(self, nap):
        self.x -= 20 * self.plane * nap
        if self.x < 0:
            self.reset()
            
            
            
            
#player object
#position by touch and reset pos is size of the parent widget (100,100)
class Player(Particle):
    tex_name = 'yship'

    def reset(self, created=False):
        self.x = self.parent.player_x
        self.y = self.parent.player_y
        self.size = 0.18

    advance = reset


#player object trail
class Trail(Particle):
    tex_name = 'fl'

    def reset(self, created=False):
        self.x = self.parent.player_x  #x pos is on player x center
        self.y = self.parent.player_y - randint(75, 85)# minus to position the trail behind player object

        if created:
            self.size = 0
        else:
            self.size = random() + 0.5

    def advance(self, nap):
        self.size -= nap
        if self.size <= 0.1:
            self.reset()
        else:
            self.y  -= 120 * nap
            # minus the y position to move downwards


#player bullets 
class Bullet(Particle):
    active = False
    tex_name = 'mis'

    def reset(self, created=False):
        self.active = False
        self.x = -100
        self.y = -100
        self.size= 0.5

    def advance(self, nap):
        if self.active:
            self.y += 250 * nap
            if self.y > self.parent.height:
                self.reset()

        elif (self.parent.firing and
              self.parent.fire_delay <= 0):
            sndfx_laser.play()

            self.active = True
            self.x = self.parent.player_x 
            self.y = self.parent.player_y
            self.parent.fire_delay += 0.4 #0.3333

#enemy object created 
class Enemy(Particle):
    active = False
    tex_name = 'en'
    v = 0 #vector variable to enable rotation to offset object back to game screen i.e creating boundary/border

    def reset(self, created=False):
        self.active = False
        self.x = self.parent.gamescrn.width /2
        self.y = self.parent.gamescrn.height + 100#hide the enemy objects off screen
        self.v = 0

    def advance(self, nap):
        if self.active:
            if self.check_hit_bullet():
                self.parent.scored = True
                self.parent.score += 10
                #if enemy shot add score
                sndfx_hit.play()
                self.reset()
                
            elif self.y < self.parent.player_y and self.y > 1:
                self.parent.scored= True
                self.parent.score -= 2
                self.reset()
                
            elif self.check_hit():
                self.parent.scored = True
                self.parent.score -= 5
                #if player collide with enemy minus score
                sndfx_player_hit.play()

                self.reset()
                return

            self.y  -= 200 * nap #downwards movement speed of 200 pixel
            if self.y < 0:
                self.reset()
                return

            self.x += self.v * nap
            if self.x <= 20:
                self.v = abs(self.v)
            elif self.x >= self.parent.gamescrn.width-20:#move away from edge
                self.v = -abs(self.v)

        elif self.parent.spawn_delay <= 0:
            self.active = True
            self.y = self.parent.gamescrn.height + 50
            self.x = self.parent.gamescrn.width * random()
            self.v = randint(-100, 100)
            self.parent.spawn_delay += 1 #0.4#decrease the spawn delay for enemy object creation



#check collision with player 1st 
    def check_hit(self):
        if math.hypot(self.parent.player_x - self.x,
                      self.parent.player_y - self.y) < 60:
            return True
            
            
            
     #check collision with the bullet
    def check_hit_bullet(self):
        #iterate bullet particles and chck for collision then reset bullet
        for b in self.parent.bullets:
            if not b.active:
                continue
            if math.hypot(b.x - self.x, b.y - self.y) < 30:
                b.reset()
                return True

#main game playing widget, subclass off the shader and particle
class GamePlay(PSWidget):
    glsl = 'spacept.glsl'
    atlas = 'spacepartrol1.atlas'
    gamescrn= ObjectProperty(None)
    firing = False
    fire_delay = 0
    spawn_delay = 1
    scored = False
    score= NumericProperty(0)
    level= NumericProperty(1)
    use_mouse = platform not in ('ios', 'android')
    
    def initialize(self):
        #App.get_running_app().root.current = "game_scrn"
        self.gamescrn= App.get_running_app().root.get_screen("game_scrn")

        self.player_x, self.player_y = self.gamescrn.width/2, self.gamescrn.height / 2#widget width and height is 100,100 by default but changed to acces gamescreen width  and height , playerx&y are used for bullet ans player pos
        sndfx_home.play()
        self.score = 0
        scoring1=self.gamescrn.ids["score"]
        scoring1.text = "scored: %s" %(self.score)
        self.level = 1
        level1=self.gamescrn.ids["level"]
        level1.text = "Level: %s" %(self.level)

        self.make_particles(Star, 250)
        self.make_particles(Trail, 200)
        self.make_particles(Player, 1)
        self.make_particles(Enemy, 50)
        self.make_particles(Bullet, 25)

        self.bullets = self.particles[-25:]
        #slice the particles list to get the last 25 items i.e bullets
        
        
        
        
        
    def update_glsl(self, nap):
        if self.use_mouse:
            self.player_x, self.player_y = Window.mouse_pos
            
        if self.scored: #scoring created and turned true on collision
            self.gamescrn= App.get_running_app().root.get_screen("game_scrn")
            scoring=self.gamescrn.ids["score"]
            scoring.text = "scored: %s" %(self.score)
            levels=self.gamescrn.ids["level"]
            
            
            #juicyfy the game 
            if self.score <= 0:
                self.gameOver()
                
            if self.score < 1000:
                self.level = 1
                levels.text = "level: %s" %(self.level)
            elif self.score > 1000 and  self.score <= 2000:
                self.level = 2
                
                levels.text = "level: %s" %(self.level)                
            elif self.score > 2000 and  self.score <= 3000:
                self.level = 3
                levels.text = "level: %s" %(self.level)

            elif self.score > 3000 and  self.score <= 4000:
                self.level = 4
                levels.text = "level: %s" %(self.level)
                                                
            elif self.score > 5000 and  self.score <= 6000:
                self.level = 5
                levels.text = "level: %s" %(self.level)                                                         
            elif self.score > 6000:
                self.level = randint(6,9)
                levels.text = "Final level: %s" %(self.level)
            
                                                                                              
        if self.firing:
            self.fire_delay -= nap #* self.level/6

        self.spawn_delay -= nap * self.level #make the enemies spwan fast by multipling with level

        PSWidget.update_glsl(self, nap)

    def on_touch_down(self, touch):
        self.player_x, self.player_y = touch.pos
        self.firing = True
        self.fire_delay = 0

    def on_touch_move(self, touch):
        self.player_x, self.player_y = touch.pos

    def on_touch_up(self, touch):
        self.firing = False
        
                
    def Restart(self,*args):
        self.particles=[]
        Clock.unschedule(self.update_glsl)
        App.get_running_app().root.current="game_scrn"
        
    def gameOver(self,*args):
        Clock.unschedule(self.update_glsl)
        self.particles=[]
        self.score= 0
        self.level=1
        App.get_running_app().root.current = "gameover_scrn"
                
#----------------- screens----- part 4 game ui design---------------
class Manager(ScreenManager):
    pass
     
class Menu(Screen):
    
    def animate(self,instance):
        Animation.cancel_all(instance,"x")
        anim=Animation(x= self.width/3 , t='in_out_bounce')
        anim += Animation(x=self.width - 300,t='out_bounce')
        anim.start(instance)
        
        
class Game(Screen):
    
    def on_enter(self, *args):
        self.gaming= self.ids.gameplay
        self.gaming.initialize()
        Clock.schedule_interval(self.gaming.update_glsl, 60 ** -1)
        #sndfx_game.play()
        #previous sound to heavy loads slow 
        
            
    def on_pre_enter(self, *args):
        self.gaming= self.ids.gameplay
        self.particles= self.gaming.particles
        self.particles=[]
        
                   
                                         
class GameOver(Screen):
    def on_enter(self,*args):
        self.gamescrn=App.get_running_app().root.get_screen("game_scrn")
        self.myscore=self.ids.final_score
        scored=self.gamescrn.ids.score.text
        leveled=self.gamescrn.ids.level.text
        self.myscore.text=str(scored)+ "\n"+ str(leveled)
        
        
    def on_restart(self,*args):
        self.gamescrn=App.get_running_app().root.get_screen("game_scrn")
        self.gaming=self.gamescrn.ids.gameplay
        self.gaming.Restart()
        
    
class SpacePatrolApp(App):
    EventLoop.ensure_window()
    
    #main game functions 
    #def on_start(self,*args):
        #EventLoop.ensure_window()
        #self.game_scrn = self.root.ids["game_scrn"]
        #self.gaming= self.game_scrn.ids["gameplay"]
        #self.gaming.initialize()
        #Clock.schedule_interval(self.gaming.update_glsl, 60 ** -1)
        #self.scrn_mngr=self.root.ids["manager"]
        #self.scrn_mngr.current = "menu_scrn"
#        if self.scrn_mngr.current== "game_scrn":
#            self.gaming= self.gm_scrn.ids["gameplay"]
#            self.gaming.initialize()
#            Clock.schedule_interval(self.gaming.update_glsl, 60 ** -1)
#        else:
#            Clock.unschedule(self.gaming.update_glsl)
        
    def change_screen(self,screen_name):
        screen_manager=self.root.ids["manager"]
        screen_manager.current=screen_name
        #to be used for next levels 
        
        
        
        
if __name__=='__main__':
    SpacePatrolApp().run()
        
    
    