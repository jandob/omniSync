#!/usr/bin/env python3
""" Different methods to watch for file changes.

Should support:
    - unix(inotify)
    - windows(https://msdn.microsoft.com/en-us/library/aa365261(VS.85).aspx)
    - mac(fsevents)
    - polling?


.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
import random
from utils.containers import OrderedSetQueue
from utils.log import log
import pyinotify
import config
from functools import partial


EVENTS = [
    'IN_MOVED_FROM',    # File was moved from X
    'IN_MOVED_TO',      # File was moved to Y
    'IN_CREATE',        # Subfile was created
    'IN_DELETE',        # Subfile was deleted
    'IN_DELETE_SELF',   # Self (watched item itself) was deleted
    'IN_MOVE_SELF',     # Self (watched item itself) was moved
    #'IN_MODIFY',        # File was modified
    'IN_ATTRIB',        # Metadata changed
    #'IN_CLOSE_WRITE',   # Writable file was closed
    #'IN_ACCESS',        # File was accessed
    #'IN_CLOSE_NOWRITE', # Unwritable file closed
    #'IN_OPEN',          # File was opened
]


class FileQueue(OrderedSetQueue):
    def __init__(self):
        super().__init__()
        # Instanciate a new WatchManager (will be used to store watches).
        wm = pyinotify.WatchManager()
        # Associate this WatchManager with a Notifier (will be used to report
        # and process events).
        self.notifier = pyinotify.ThreadedNotifier(wm)
        self.notifier.start()

        events = 0
        for e in EVENTS:
            events |= pyinotify.EventsCodes.ALL_FLAGS[e]

        # Add watches

        config.load()
        #config.save()
        for watch in config.data['watches']:
            if not watch.get('disabled'):
                watch_descriptors = wm.add_watch(
                    watch['source'], events,
                    rec=True, auto_add=True,
                    proc_fun=partial(self.process_event, {
                        'syncer': watch['syncer'],
                        'target': watch['target'],
                        'source': watch['source']
                    }),
                    exclude_filter=pyinotify.ExcludeFilter(watch['exclude'])
                )

    def process_event(self, event_info, event):
        #file_name = event.name
        #isdir = event.dir
        event_type = event.maskname
        path = event.pathname
        event.info = event_info
        log.debug(path + ': ' + event_type)
        self.put(event)

    def stop(self):
        self.notifier.stop()

    def save(self): raise NotImplementedError
