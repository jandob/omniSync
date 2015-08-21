import yaml
data = None
_config_filename = "config.yaml"


def load():
    with open(_config_filename, 'r') as stream:
        # Note: The ability to construct an arbitrary Python object may be
        # dangerous. The function `yaml.safe_load` limits this ability to
        # simple Python objects like integers or lists.
        global data
        data = yaml.safe_load(stream)


def save():
    with open(_config_filename, 'w') as stream:
        yaml.dump(data, stream)


## json
#import json
#with open('config.json', 'r') as f:
    #config = json.load(f)

##edit the data
#config['key3'] = 'value3'

##write it back to the file
#with open('config.json', 'w') as f:
    #json.dump(config, f)
