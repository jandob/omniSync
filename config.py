import os
import yaml

_config_filename = "config.yaml"
_config_path = os.path.dirname(os.path.realpath(__file__))
data = None


def load():
    global data
    try:
        with open(_config_filename, 'r') as stream:
            # Note: The ability to construct an arbitrary Python object may be
            # dangerous. The function `yaml.safe_load` limits this ability to
            # simple Python objects like integers or lists.
            data = yaml.safe_load(stream)
    except IOError:
        with open(os.path.join(_config_path, _config_filename), 'r') as stream:
            data = yaml.safe_load(stream)



def save():
    with open(_config_filename, 'w') as stream:
        yaml.dump(data, stream)

load()

if __name__ == '__main__':
    """ reads and saves the config (sorts keys etc.)
    Note: does not preserve comments"""
    save()

## json
#import json
#with open('config.json', 'r') as f:
    #config = json.load(f)

##edit the data
#config['key3'] = 'value3'

##write it back to the file
#with open('config.json', 'w') as f:
    #json.dump(config, f)
