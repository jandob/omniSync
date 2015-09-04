#!/usr/bin/env python3
""" API to interface different file syncing methods.

Should support: google drive, dropbox, rsync


.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""

from threading import Thread
from importlib import import_module

from utils.containers import OrderedSetQueue
from utils.log import log
from utils.strings import underscore
import config


class QueueConsumer(Thread):
    def __init__(self, queue=None):
        self.queue = queue or OrderedSetQueue()
        super().__init__()
        log.debug(self.__class__.__name__ + " init")

    def run(self):
        log.debug(self.__class__.__name__ + " running")
        while True:
            item = self.queue.get()
            if item is None:  # trick to break out of while
                break
            self.consume_item(item)
            # TODO what if a file gets added again while syncing in progress?
            self.queue.task_done()

    def stop(self):
        self.queue.put(None)  # trick to break out of while
        log.debug(self.__class__.__name__ + " stopped")

    def consume_item(self, item): raise NotImplementedError


class SyncBase(QueueConsumer):
    def __init__(self, progress_callback=None):
        """
        Args:
            progress_callback (callable):
                Is called regularly with the progress of the syncing process.
                Range: 0.0 - 1.0
        """
        super().__init__()
        self.name = self.__class__.__name__
        self.progress_callback = progress_callback

    def fullsync(self, pull=False):
        """
            pull==True pull from target (overwriting source)
        """
        raise NotImplementedError


class SyncManager(QueueConsumer):
    """ Manages the different file uploaders.
    """
    def __init__(self, file_queue, progress_callback=None):
        """
        Args:
            file_queue (queue.Queue): Queue with files to sync.
        """
        super().__init__(queue=file_queue)
        self.progress_callback = progress_callback
        self.start_syncers()
        self.start()

    def start_syncers(self):
        # Import syncers from 'syncers' package and start them.
        # e.g. from syncers.dropbox import Dropbox
        # module: underscore
        # class: camelcase
        self.syncers = {}
        syncers_lists = [x['syncers'] for x in filter(
            lambda x: not x.get('disabled'), config.data['watches']
        )]
        # flatten list of lists and make vals unique via set comprehension
        # (start only one instance for every syncer)
        enabled_syncers = {val for sublist in syncers_lists for val in sublist}
        for syncer in enabled_syncers:
            syncer_instance = getattr(
                import_module('syncers.' + underscore(syncer)),
                syncer)(progress_callback=self.handle_sync_progress)
            self.syncers[syncer] = syncer_instance
            syncer_instance.start()

    def handle_sync_progress(self, syncer, file, progress):
        log.info("%s: %s %s" % (syncer.name, progress, file))
        self.progress_callback(syncer, file, progress)

    def stop(self):
        [s.stop() for s in self.syncers.values()]
        super().stop()

    def fullsync(self, pull=False):
        for syncer in self.syncers.values():
            syncer.fullsync()

    def consume_item(self, event):
        for syncer in event.syncers:
            self.syncers[syncer].queue.put(event)
