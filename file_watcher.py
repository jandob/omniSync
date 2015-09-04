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
import os
import pyinotify

from utils.containers import OrderedSetQueue
from utils.log import log

EVENTS = [
    'MOVED_FROM',    # File was moved from X
    'MOVED_TO',      # File was moved to Y
    'CREATE',        # Subfile was created
    'DELETE',        # Subfile was deleted
    'DELETE_SELF',   # Self (watched item itself) was deleted
    'MOVE_SELF',     # Self (watched item itself) was moved
    'ATTRIB',        # Metadata changed
    'MODIFY',        # File was modified
    #'CLOSE_WRITE',   # Writable file was closed
    #'ACCESS',        # File was accessed
    #'CLOSE_NOWRITE', # Unwritable file closed
    #'OPEN',          # File was opened
]


class InotifyEvent():
    def __init__(self, event, watch_config):
        self._mask = event.mask
        self.file_name = event.name
        #self.base_path = event.path  # path without filename/foldername
        self.source_absolute = event.pathname  # path with filename/foldername
        self.isdir = event.dir
        self.target_dir = watch_config['target']  # target dir
        self.source_dir = watch_config['source']  # source dir
        self.syncers = watch_config['syncers']
        self.config = watch_config

        self.source_relative = os.path.join(
            os.path.relpath(self.source_absolute, self.source_dir)
        )
        self.target_absolute = os.path.join(
            self.target_dir, self.source_relative
        )
        self.moved_from_path = getattr(event, 'src_pathname', None)
        log.debug('EVENT %s (%s): %s ' % (
            self.type, self.syncers, self.source_absolute))

    @property
    def type(self):
        mask = self._mask
        if self.isdir:
            mask -= pyinotify.IN_ISDIR
        return pyinotify.EventsCodes.ALL_VALUES.get(mask, 'IN_UNDEFINED')[3:]

    def _key(self):
            return self.source_absolute + '__' + str(self.syncers)

    def __eq__(self, other):
            return self._key() == other._key()

    def __ne__(self, other):
            return self._key() != other._key()

    def __hash__(self):
            return hash(self._key())


class FileQueue(OrderedSetQueue):

    def save(self): raise NotImplementedError


class FileWatcher():

    def __init__(self, queue, watch_config):
        self.queue = queue
        self.watch_config = watch_config
        # Instanciate a new WatchManager (will be used to store watches).
        wm = pyinotify.WatchManager()
        # Associate this WatchManager with a Notifier (will be used to report
        # and process events).
        self.notifier = pyinotify.ThreadedNotifier(
            wm, self.process_event, read_freq=2)
        self.notifier.start()

        events = 0
        for e in map(lambda x: 'IN_' + x, EVENTS):
            events |= pyinotify.EventsCodes.ALL_FLAGS[e]

        wm.add_watch(
            self.watch_config['source'], events, rec=True, auto_add=True,
            proc_fun=self.process_event,
            exclude_filter=pyinotify.ExcludeFilter(
                self.watch_config.get('exclude', []))
        )

    def process_event(self, event):
        self.queue.put(InotifyEvent(event, self.watch_config))

    def stop(self):
        self.notifier.stop()


if __name__ == '__main__':
    import config
    q = FileQueue()
    for watch_config in config.data['watches']:
        if not watch_config.get('disabled'):
            FileWatcher(q, watch_config)
