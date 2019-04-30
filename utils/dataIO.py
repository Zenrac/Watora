import json
import os
from random import randrange


class InvalidFileIO(Exception):
    pass


class DataIO():
    def __init__(self):
        pass

    def save_json(self, filename, data):
        """Saves json file and avoid Json issues."""
        rand = randrange(1000, 10000)
        path, ext = os.path.splitext(filename)
        tmp_file = "{}-{}.tmp".format(path, rand)
        self.really_save_json(tmp_file, data)
        try:
            self.read_json(tmp_file)
        except json.decoder.JSONDecodeError:
            return False
        os.replace(tmp_file, filename)
        return True

    def load_json(self, filename):
        return self.read_json(filename)

    def read_json(self, filename):
        with open(filename, encoding='utf-8-sig', mode="r") as f:
            data = json.load(f)
        return data

    def really_save_json(self, filename, data):
        with open(filename, encoding='utf-8', mode="w") as f:
            json.dump(data, f, indent=4, sort_keys=True,
                      separators=(',', ' : '))
        return data


dataIO = DataIO()
