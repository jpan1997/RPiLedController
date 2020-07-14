import argparse
import colorsys
import math
import neopixel
import time
import threading
import traceback

from datetime import datetime

# LED Parameters
LED_COUNT      = 300     # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 127     # Set to 0 for darkest and 255 for brightest, only use 255 if 2 power supplies
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

# Animation Parameters
PERIOD_TIME_SEC     = 60            # seconds, speed is a multiplier on PERIOD_TIME
ANIMATION_FRAME_DURATION_MS = 20     # ms

# Enums
BOUNDARY_CONTINUOUS = 0
BOUNDARY_DISCRETE = 1

ARRANGEMENT_SOLID = 0
ARRANGEMENT_SEGMENT = 1

def hsv_to_color(hsv):
    rgb = colorsys.hsv_to_rgb(hsv[0], hsv[1], hsv[2])
    return neopixel.Color(int(255*rgb[1]), int(255*rgb[0]), int(255*rgb[2]))

def adjust_color(color, s, v):
    return (color[0], color[1]*s, color[2]*v)

def hue_fade(start, end, percentage):
    diff = min((start - end) % 1, (end - start) % 1)
    if (start + diff) % 1 == end:
        direction = 1
    else:
        direction = -1
    return (start + diff * percentage * direction) % 1

def saturation_fade(start, end, percentage):
    diff = abs(start - end)
    if start + diff == end:
        direction = 1
    else:
        direction = -1
    return (start + diff * percentage * direction)

def value_fade(start, end, percentage):
    diff = abs(start - end)
    if start + diff == end:
        direction = 1
    else:
        direction = -1
    return (start + diff * percentage * direction)

# start,end: (h,s,v)
# percentage: float 0-1
def color_fade(start, end, percentage):
    h = hue_fade(start[0], end[0], percentage)
    s = saturation_fade(start[1], end[1], percentage)
    v = value_fade(start[2], end[2], percentage)
    return (h, s, v)

class Strip:
    def __init__(self):
        self.stop = False
        self.lock = threading.Lock()
        
        self.strip = neopixel.Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        self.strip.begin()
       
        self.reset_settings()

    def reset_settings(self):
        with self.lock:
            # Parameters
            self.power = True
            self.colors = [(0,1,1)]                         # list of Colors,(h,s,v)
            self.saturation = 1                             # float 0 - 1 (brightness)
            self.value = 1                                  # float 0 - 1 (darkness)
            self.boundary = BOUNDARY_DISCRETE               # Boundary enum
            self.arrangement = ARRANGEMENT_SEGMENT          # Arrangement enum
            self.speed = 0                                  # float 0 - 1
            self.direction = 0                              # animation direction, {-1, 0, 1}
            self.pos = 0                                    # float 0 - 1, current animation period progress

            self.history_enable = False
            self.history_speed = 1                          # num of pixels to update each frame
            self.history_pos = 0                            # float 0 - 1, position of history playback
            self.history_size = 0                           # float 0 - 1, size of history origin playback

            self.music_smooth = 5                           # int, # of samples
            self.music_calibration_sec = 5                  # float, # of seconds
            self.music_brightness_enable = False
            self.music_brightness_min = 0                   # float 0 - 1
            self.music_brightness_max = 0.5                 # float 0 - 1
            self.music_color_enable = False
            self.music_color_debounce = 6                   # int, num chunks
            self.music_color_thresh = 0.9                   # float 0 - 1

            # Internals
            self.music_saturation = 1
            self.music_value = 1
            self.pixels = [0]*self.strip.numPixels()        # list of colors, length LED_COUNT

    
    # Shows self.pixels on the strip
    def show(self):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, self.pixels[i])
        self.strip.show()

    def clear(self):
        for i in range(self.strip.numPixels()):
            self.pixels[i] = 0
    
    def clear_and_show(self):
        self.clear()
        self.show()

    # Updates self.pixels using parameters and pos
    def update(self):
        if not self.power:
            self.clear()
            return

        with self.lock:
            colors = list(self.colors)
            saturation = self.saturation
            value = self.value
            boundary = self.boundary
            arrangement = self.arrangement
            pos = self.pos
            
            music_brightness_enable = self.music_brightness_enable
            music_saturation = self.music_saturation
            music_value = self.music_value

            if music_brightness_enable:
                saturation = music_saturation
                value = music_value

            history_enable = self.history_enable
            history_speed = self.history_speed
            history_pos = self.history_pos
            history_size = self.history_size


        # Default to black when no colors present
        if len(colors) == 0:
            colors = [(0,0,0)]

        if arrangement is ARRANGEMENT_SOLID:
            color = colors[0]
            if boundary is BOUNDARY_DISCRETE:
                color_idx = int(1.0 * pos * len(colors))
                color = colors[color_idx]
            elif boundary is BOUNDARY_CONTINUOUS:
                section_float = (1.0 * pos * len(colors) - 0.5) % len(colors)
                section_int = int(section_float) % len(colors)
                color_pair = (colors[section_int], colors[(section_int+1) % len(colors)])

                fade_percentage = section_float % 1
                color = color_fade(color_pair[0], color_pair[1], fade_percentage)

        offset = int(1.0 * pos * self.strip.numPixels())
        for i in range(self.strip.numPixels()):

            # ARRANGEMENT
            if arrangement is ARRANGEMENT_SEGMENT:
                pattern_idx = (i + offset) % self.strip.numPixels()

                # BOUNDARY
                color = colors[0]
                if boundary is BOUNDARY_DISCRETE:
                    color_idx = int(1.0 * pattern_idx / self.strip.numPixels() * len(colors))
                    color = colors[color_idx]
                elif boundary is BOUNDARY_CONTINUOUS:
                    section_float = (1.0 * pattern_idx / self.strip.numPixels() * len(colors) - 0.5) % len(colors)
                    section_int = int(section_float)
                    color_pair = (colors[section_int], colors[(section_int+1) % len(colors)])

                    fade_percentage = section_float % 1
                    color = color_fade(color_pair[0], color_pair[1], fade_percentage)

            pixel = hsv_to_color(adjust_color(color, saturation, value))

            # HISTORY
            if history_enable:
                left_boundary = int(self.strip.numPixels()*(history_pos - history_size))
                right_boundary = int(self.strip.numPixels()*(history_pos + history_size))

                if left_boundary < 0:
                    left_boundary = 0
                if right_boundary > self.strip.numPixels():
                    right_boundary = self.strip.numPixels()

                left_pixels = self.pixels[:left_boundary]
                middle_pixels = self.pixels[left_boundary:right_boundary]
                right_pixels = self.pixels[right_boundary:]

                for i in range(len(middle_pixels)):
                    middle_pixels[i] = pixel

                for i in range(history_speed):
                    if len(left_pixels) > 0:
                        left_pixels.pop(0)
                        left_pixels.append(pixel)
                    if len(right_pixels) > 0:
                        right_pixels.pop(-1)
                        right_pixels.insert(0, pixel)

                self.pixels = left_pixels + middle_pixels + right_pixels
                break
            else:
                self.pixels[i] = pixel



    def animate(self):
        while not self.stop:
            start = datetime.now()
            self.update()
            mid = datetime.now()
            self.show()
            end = datetime.now()

            
            time.sleep(ANIMATION_FRAME_DURATION_MS / 1000.0)
            
            with self.lock:
                if self.speed != 0:
                    progress = ANIMATION_FRAME_DURATION_MS / 1000.0 / (PERIOD_TIME_SEC * self.speed)
                    self.pos += self.direction * progress
                    if self.pos >= 1 or self.pos < 0:
                        self.pos = self.pos % 1
                        # print(datetime.strftime(datetime.now(), "%H:%M:%S.%f"))
            
            # print("update():", mid - start)
            # print("show():", end - mid)
    
    def kill(self):
        self.stop = True

    def update_settings(self, settings):
        with self.lock:
            if "power" in settings:
                self.power = settings["power"]
            if "colors" in settings:
                self.colors = settings["colors"]
                # convert colors to (h,s,v) if necessary
                for i in range(len(self.colors)):
                    # given as number
                    if type(self.colors[i]) == float or type(self.colors[i]) == int:
                        self.colors[i] = (self.colors[i], 1, 1) # default s,v = 1
                    # given as list, expected length = 3
                    elif type(self.colors[i]) == list:
                        self.colors[i] = (self.colors[i][0], self.colors[i][1], self.colors[i][2])
                
            if "saturation" in settings:
                self.saturation = settings["saturation"]
            if "value" in settings:
                self.value = settings["value"]
            if "boundary" in settings:
                self.boundary = settings["boundary"]
            if "arrangement" in settings:
                self.arrangement = settings["arrangement"]
            if "speed" in settings:
                self.speed = settings["speed"]
            if "direction" in settings:
                self.direction = settings["direction"]
            if "pos" in settings:
                self.pos = settings["pos"]
            if "history_enable" in settings:
                self.history_enable = settings["history_enable"]
            if "history_speed" in settings:
                self.history_speed = settings["history_speed"]
            if "history_pos" in settings:
                self.history_pos = settings["history_pos"]
            if "history_size" in settings:
                self.history_size = settings["history_size"]
            if "music_smooth" in settings:
                self.music_smooth = settings["music_smooth"]
            if "music_calibration_sec" in settings:
                self.music_calibration_sec = settings["music_calibration_sec"]
            if "music_brightness_enable" in settings:
                self.music_brightness_enable = settings["music_brightness_enable"]
            if "music_saturation" in settings:
                self.music_saturation = settings["music_saturation"]
            if "music_value" in settings:
                self.music_value = settings["music_value"]
            if "music_brightness_min" in settings:
                self.music_brightness_min = settings["music_brightness_min"]
            if "music_brightness_max" in settings:
                self.music_brightness_max = settings["music_brightness_max"]
            if "music_color_enable" in settings:
                self.music_color_enable = settings["music_color_enable"]
            if "music_color_debounce" in settings:
                self.music_color_debounce = settings["music_color_debounce"]
            if "music_color_thresh" in settings:
                self.music_color_thresh = settings["music_color_thresh"]

    def get_settings(self):
        settings = {}
        settings["power"] = self.power
        settings["colors"] = self.colors
        settings["saturation"] = self.saturation
        settings["value"] = self.value
        settings["boundary"] = self.boundary
        settings["arrangement"] = self.arrangement
        settings["speed"] = self.speed
        settings["direction"] = self.direction
        settings["pos"] = self.pos
        settings["history_enable"] = self.history_enable
        settings["history_speed"] = self.history_speed
        settings["history_pos"] = self.history_pos
        settings["history_size"] = self.history_size
        settings["music_smooth"] = self.music_smooth
        settings["music_calibration_sec"] = self.music_calibration_sec
        settings["music_brightness_enable"] = self.music_brightness_enable
        settings["music_saturation"] = self.music_saturation
        settings["music_value"] = self.music_value
        settings["music_brightness_min"] = self.music_brightness_min
        settings["music_brightness_max"] = self.music_brightness_max
        settings["music_color_enable"] = self.music_color_enable
        settings["music_color_debounce"] = self.music_color_debounce
        settings["music_color_thresh"] = self.music_color_thresh
        return settings

if __name__ == '__main__':
    s = Strip()

    # s.colors = [(0.67, 1, 0), (0.13, 0.5, 1), (0.13, 0.5, 1), (0.13, 0.5, 1), (0.67, 1, 0)]
    # s.saturation = 1
    # s.value = 0.75
    # s.boundary = BOUNDARY_DISCRETE
    # s.arrangement = ARRANGEMENT_SEGMENT
    # s.speed = 0

    s.colors = [0.16, 0.5]
    s.saturation = 1
    s.value = 1
    s.boundary = BOUNDARY_CONTINUOUS
    s.arrangement = ARRANGEMENT_SEGMENT
    s.speed = 0.1
    s.direction = 1

    animateThread = threading.Thread(target=s.animate)
    animateThread.start()

    try:
        while True:
            time.sleep(1)
            s.update_settings({"arrangement": ARRANGEMENT_SEGMENT})
            time.sleep(1)
            s.update_settings({"arrangement": ARRANGEMENT_SOLID})
    except KeyboardInterrupt:
        s.kill()
        animateThread.join()
        s.clear()
    except:
        traceback.print_exc()
        s.kill()
        animateThread.join()
        s.clear()

