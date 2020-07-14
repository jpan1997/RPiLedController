import pyaudio
import numpy as np
import random
import threading
import time

NO_CHANNELS= 1
SAMPLE_RATE = 48000
CHUNK = 2048
FORMAT = pyaudio.paInt16
DEVICE = 2

# Not Configurable
Z_THRESH = 1.8
WEIGHT_ENABLED = True
WEIGHT_SLOPE = 0.4 # 0-1, 0 = no weight distribution, 1 = maxiumal weight distribution

def amp_to_saturation_value(amp):
    if amp < 0.5:
        saturation = 1
        value = amp*2
    else:
        saturation = 1 - (amp-0.5)*2
        value = 1

    return saturation, value

class MusicVis:

    def __init__(self, strip):
        
        self.pyAudio = pyaudio.PyAudio()

        for i in range(self.pyAudio.get_device_count()):
            print(str(i) + ": " + self.pyAudio.get_device_info_by_index(i).get('name'))

        self.input_stream = self.pyAudio.open(format = FORMAT,
                channels = NO_CHANNELS,
                rate = SAMPLE_RATE,
                input = True,
                frames_per_buffer = CHUNK,
                input_device_index = DEVICE)
        # self.output_stream = self.pyAudio.open(format = FORMAT,
        #         channels = NO_CHANNELS,
        #         rate = SAMPLE_RATE,
        #         output = True,
        #         frames_per_buffer = CHUNK,
        #         input_device_index = DEVICE)
        self.strip = strip
        self.mw_calib = []
        self.mw_smooth = []

        self.debounce = 0

        self.stop = False
    
    def run(self):
        while not self.stop:
            try:
                data = self.input_stream.read(CHUNK)
            except IOError:
                # noisy
                # print("input overflow")
                continue

            ## Doesn't work in sudo mode
            # self.output_stream.write(data)

            fourier = abs(np.fft.rfft(np.fromstring(data, np.int16)))
            ave = sum(fourier)/len(fourier)/1000
            log_ave = np.log10(ave)

            a = 1
            b = -0.8 # mute threshold: + less sound let through, - more sound let through
            mapped_log_ave = a*(log_ave - b)

            with self.strip.lock:
                music_smooth = self.strip.music_smooth
                music_calibration_sec = self.strip.music_calibration_sec

            while len(self.mw_smooth) >= music_smooth:
                self.mw_smooth.pop(0)
            self.mw_smooth.append(mapped_log_ave)
            mapped_log_ave = sum(self.mw_smooth)/len(self.mw_smooth)

            if mapped_log_ave < 0:
                mapped_log_ave = 0

            calibration_len = int(1.0*music_calibration_sec / CHUNK * SAMPLE_RATE)
            while len(self.mw_calib) >= calibration_len:
                self.mw_calib.pop(0)
            self.mw_calib.append(mapped_log_ave)

            #
            # Normalize using calibration window
            # 

            if WEIGHT_ENABLED:
                w_func = lambda i, size: 1
            else:
                # linear weighting
                w_func = lambda i, size: WEIGHT_SLOPE*1.0*i/size + ((1 - WEIGHT_SLOPE) / 2.0)
            weights = [w_func(i, len(self.mw_calib)) for i,_ in enumerate(self.mw_calib)]

            mu = np.average(self.mw_calib, weights=weights)
            std = np.sqrt(np.average((self.mw_calib - mu)**2, weights=weights))

            mw_calib_min = mu - Z_THRESH*std
            mw_calib_max = mu + Z_THRESH*std

            if mw_calib_min < min(self.mw_calib):
                mw_calib_min = min(self.mw_calib)
            if mw_calib_max > max(self.mw_calib):
                mw_calib_max = max(self.mw_calib)

            # clip
            if mapped_log_ave < mw_calib_min:
                mapped_log_ave = mw_calib_min
            elif mapped_log_ave > mw_calib_max:
                mapped_log_ave = mw_calib_max

            if max(self.mw_calib) == 0 or mw_calib_min == mw_calib_max:
                mapped2_log_ave = 0.5
            else:
                mapped2_log_ave = (mapped_log_ave - mw_calib_min) / (mw_calib_max - mw_calib_min)

            # print(int(mapped2_log_ave*100))

            amp = mapped2_log_ave

            #
            # Animation logic:
            #

            with self.strip.lock:
                colors = list(self.strip.colors)
                music_brightness_enable = self.strip.music_brightness_enable
                music_brightness_min = self.strip.music_brightness_min
                music_brightness_max = self.strip.music_brightness_max
                music_color_enable = self.strip.music_color_enable
                music_color_debounce = self.strip.music_color_debounce
                music_color_thresh = self.strip.music_color_thresh

            
            if amp > music_color_thresh and music_color_enable and self.debounce == 0 :
                for i in range(len(colors)):
                    offset = random.randint(0, 100) / 100.0
                    colors[i] = ((colors[i][0] + offset) % 1, colors[i][1], colors[i][2])
                self.strip.update_settings({"colors": colors})
                self.debounce = music_color_debounce

            if self.debounce > 0:
                self.debounce -= 1

            if music_brightness_enable:
                if music_brightness_max < music_brightness_min:
                    music_brightness_max = music_brightness_min
                adjusted_amp = amp*(music_brightness_max - music_brightness_min) + music_brightness_min
                saturation, value = amp_to_saturation_value(adjusted_amp)
                self.strip.update_settings({"music_saturation":saturation, "music_value":value})
    
    def kill(self):
        self.stop = True


if __name__ == '__main__':
    musicVis = MusicVis(None)
    musicThread = threading.Thread(target=musicVis.run)

    try:
        musicThread.start()
        while True:
            time.sleep(60)
    except:
        musicVis.kill()
    
    musicThread.join()
    