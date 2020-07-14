import json
import threading

class PresetsManager:
    def __init__(self, strip, filename="/home/pi/led_presets.json"):
        self.lock = threading.Lock()
        self.filename = filename
        self.strip = strip
    
    # Private helpers
    def read_presets(self):
        with self.lock:
            try:
                with open(self.filename ,"r") as f:
                    presets = json.load(f)
            # IOError for open(), ValueError for json.load()
            except (ValueError, IOError):
                presets = {}
        return presets

    def write_presets(self, presets):
        with self.lock:
            # will create file if doesn't exist
            with open(self.filename, "w") as f:  
                json.dump(presets, f)

    # Public methods
    def get_presets_list(self): 
        presets_list = []
        presets = self.read_presets()
        for preset_name in presets:
            presets_list.append(preset_name)
        presets_list.sort() # alphabetize
        return presets_list

    def add_preset(self, name):
        presets = self.read_presets()
        presets[name] = self.strip.get_settings()
        self.write_presets(presets)

    def load_preset(self, name):
        presets = self.read_presets()
        if name in presets:
            self.strip.update_settings(presets[name])

    def save_preset(self, name):
        presets = self.read_presets()
        presets[name] = self.strip.get_settings()
        self.write_presets(presets)

    def remove_preset(self, name):
        presets = self.read_presets()
        if name in presets:
            del presets[name]
            self.write_presets(presets)