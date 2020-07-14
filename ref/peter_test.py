#!/usr/bin/env python3
# NeoPixel library strandtest example
# Author: Tony DiCola (tony@tonydicola.com)
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.

import time
from neopixel import *
import argparse
import pyaudio
import numpy as np
import matplotlib.pyplot as plt
import math
import colorsys
import collections
import random

# LED strip configuration:
LED_COUNT      = 300      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
#LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 127     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0      # set to '1' for GPIOs 13, 19, 41, 45 or 53

no_channels = 1
sample_rate = 48000
chunk = 1024 
device = 2 

p = pyaudio.PyAudio()
stream = p.open(format = pyaudio.paInt16,
                channels = no_channels,
                rate = sample_rate,
                input = True,
                frames_per_buffer = chunk,
                input_device_index = device)

stream.start_stream()

# log scale
mapping = np.log10(range(10,1200))/math.log10(1200)*443

# list of original bins mapped to each new bin
mapping_list = [None]*300

# offset index
offset = math.floor(mapping[0])

for idx, x in enumerate(mapping):
   curr_idx = int(math.floor(x) - offset)
   # Handle edge case of last element
   if(idx < len(mapping)-1):
      next_idx = int(math.floor(mapping[idx+1]) - offset)
   else:
      next_idx = curr_idx
   if mapping_list[curr_idx] == None:
      mapping_list[curr_idx] = []
   mapping_list[curr_idx].append(idx)
   # pad all bins without mappings to the closest one below it
   while curr_idx < next_idx - 1:
      curr_idx += 1
      if mapping_list[curr_idx] == None:
         mapping_list[curr_idx] = []
      mapping_list[curr_idx].append(idx)

bin_hts = [0]*300

# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, color)
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

def rainbow(strip, wait_ms=20, iterations=1):
    """Draw rainbow that fades across all pixels at once."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((i+j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def rainbow_scale(val):
    if val < 0.33:
        return Color(int(val*3*255), 255 - int(val*3*255), 0)
    elif val < 0.67:
        val -= 0.33
        return Color(255 - int(val*3*255), 0, int(val*3*255))
    else:
        val -= 0.67
        return Color(0, int(val*3*255), 255 - int(val*3*255))

def rainbowCycle(strip, wait_ms=20, iterations=5):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChaseRainbow(strip, wait_ms=50):
    """Rainbow movie theater light style chaser animation."""
    for j in range(256):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, wheel((i+j) % 255))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def hsv_to_color(h,s,v):
    rgb = colorsys.hsv_to_rgb(h,s,v)
    return Color(int(255*rgb[1]), int(255*rgb[0]), int(255*rgb[2]))


averages = collections.deque()
cum_sum = 0
WINDOW_LENGTH = 50.0
def calculate_moving_average(new_value):
	global cum_sum
	if len(averages) >= WINDOW_LENGTH:
		cum_sum -= averages.popleft()
		cum_sum += new_value
		averages.append(new_value)
		return cum_sum / WINDOW_LENGTH
	averages.append(new_value)
	cum_sum += new_value
	return cum_sum / float(len(averages))


# Main program logic follows:
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    # Create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    print ('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')

    THRESHOLD = 1.6
    average_energy = 0
    ctr = 0
    last_change = 0
    prev_rand = 0
    try:
        # strip.setPixelColor(150, Color(0, 255, 0))
        while True:
            try:
                raw_data = stream.read(chunk)
            except IOError:
                print("input overflow")
                continue
			
            audio_data = np.fromstring(raw_data, np.int16)
            fourier = abs(np.fft.rfft(audio_data))
            #fourier = np.delete(fourier, len(fourier)-1)

            ave = sum(fourier)/len(fourier)/100000
            rand = random.randint(0, 100)
            if ave > average_energy * THRESHOLD and ctr > (last_change + 5):
				print 'change', ctr
				for i in range(strip.numPixels()):
					strip.setPixelColor(i, hsv_to_color(rand/100.0, 1, 1))
				strip.show()
				last_change = ctr
			
            #if ave > 1:
                #ave = 1
            #for i in range(300):
                #norm_amp = bin_hts[i]/100000
                #if norm_amp > 1:
                    #norm_amp = 1
                #strip.setPixelColor(i, hsv_to_color((1-norm_amp)*0.75, 1, ave))
            #strip.show()
            average_energy = calculate_moving_average(ave)
            ctr += 1
            prev_rand = rand

    except KeyboardInterrupt:
        if args.clear:
            for i in range(strip.numPixels()):
				strip.setPixelColor(i, Color(0,0,0))
            strip.show()
