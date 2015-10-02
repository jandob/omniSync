#!/usr/bin/env python3
""" API to interface different file syncing methods.

Should support: google drive, dropbox, rsync


.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
from builtins import super
import builtins

from threading import Thread
from importlib import import_module
import pkgutil
import pyclbr

import syncers
from utils.packages import find_modules_with_super_class
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
    def __init__(self):
        super().__init__()
        self.name = self.__class__.__name__
        self.progress = 1.0
        self.progress_callbacks = []

    def register_progress_callback(self, callback):
        """
        Args:
            callback (callable):
                Is called regularly with the progress of the syncing process.
                Range: 0.0 - 1.0
        """
        self.progress_callbacks.append(callback)

    def send_progress(self, event, progress):
        self.progress = progress
        for callback in self.progress_callbacks:
            callback(self, event, progress)


    @staticmethod
    def event_hash_function(event):
        return None

    def init(self):
        raise NotImplementedError

    def fullsync(self, pull=False):
        """
            pull==True pull from target (overwriting source)
        """
        raise NotImplementedError

    def walk(self, remote_path):
        """
        Return list of all files/folders under given remote_path
        """
        raise NotImplementedError

    def rm(self, remote):
        raise NotImplementedError

    def download(self, local, remote):
        """
        Download a single file
        """
        raise NotImplementedError

    def upload(self, local, remote):
        """
        Upload a single file
        """
        raise NotImplementedError

    def pull(self, local, remote):
        """

        """
        raise NotImplementedError

    def push(self, local, remote):
        raise NotImplementedError

    def fullsync(self, local, remote):
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

        def syncer_is_enabled(syncer):
            for watch in config.data['watches']:
                if not watch.get('disabled', False) and \
                        syncer in watch['syncers']:
                    return True
            return False
        self.syncers = self.get_syncer_instances(filter=syncer_is_enabled)

        for syncer in self.syncers.values():
            syncer.start()
            syncer.register_progress_callback(self.handle_sync_progress)
        self.start()

    @staticmethod
    def get_syncer_instances(filter=lambda: True):
        # Import syncers from 'syncers' package and start them.
        # Does something like: from syncers.dropbox import Dropbox
        syncer_instances = {}
        # find classes inside syncers package that have the superclass SyncBase
        available_syncers = dict(find_modules_with_super_class(
                syncers, SyncBase))
        log.debug('available_syncers: %s' % list(available_syncers.keys()))

        for syncer in builtins.filter(filter, available_syncers.keys()):
            syncer_instances[syncer] = getattr(
                import_module(available_syncers[syncer]), syncer)()
        return syncer_instances

    def handle_sync_progress(self, syncer, file, progress):
        log.info("%s: %s %s" % (syncer.name, progress, file))
        self.progress_callback(syncer, file, progress)

    def stop(self):
        [s.stop() for s in self.syncers.values()]
        super().stop()

    def fullsync(self):
        for syncer in self.syncers.values():
            syncer.fullsync()

    def consume_item(self, event):
        for syncer in event.syncers:
            if self.syncers[syncer].event_hash_function(event) is not None:
                # monkey patch the event hash function
                event.__hash__ = self.syncers[syncer].event_hash_function
            self.syncers[syncer].queue.put(event)
