import logging
import logging.handlers

from logutils.colorize import ColorizingStreamHandler


class ColorHandler(ColorizingStreamHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.level_map = {
            # Provide you custom coloring information here
            logging.DEBUG: (None, 'blue', False),
            logging.INFO: (None, 'green', False),
            logging.WARNING: (None, 'yellow', False),
            logging.ERROR: (None, 'red', False),
            logging.CRITICAL: ('red', 'white', True),
        }


#log = logging.getLogger('mainLogger')
log = logging.getLogger()
log.setLevel(logging.DEBUG)

log.addHandler(ColorHandler())
