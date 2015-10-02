#!/usr/bin/env python3
""" API to interface different file syncing methods.

Should support: google drive, dropbox, rsync


.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
from builtins import super

from threading import Thread
from importlib import import_module
import pkgutil
import pyclbr

import syncers
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
        self.progress = 1.0
        def send_progress(syncer, event, progress):
            self.progress = progress
            progress_callback(syncer, event, progress)
        self.send_progress = send_progress


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
        self.start_syncers()
        self.start()

    def _find_modules_with_super_class(self, pkg, super_class):
        found_classes = {}
        for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            if ispkg:
                log.info(
                    'Found package in syncers plugin directory, skipping!')
                continue
            import_path = "%s.%s" % (pkg.__name__, modname)
            module = pyclbr.readmodule(import_path)
            for item, val in module.items():
                if super_class.__name__ in val.super:
                    found_classes[item] = import_path
        return found_classes

    def start_syncers(self):
        # Import syncers from 'syncers' package and start them.
        # Does something like: from syncers.dropbox import Dropbox
        self.syncers = {}
        syncers_lists = [x['syncers'] for x in filter(
            lambda x: not x.get('disabled'), config.data['watches']
        )]
        # flatten list of lists and make vals unique via set comprehension
        # (start only one instance for every syncer)
        enabled_syncers = {val for sublist in syncers_lists for val in sublist}

        # find classes inside syncers package that have the superclass SyncBase
        available_syncers = self._find_modules_with_super_class(
                syncers, SyncBase)
        log.debug('available_syncers: %s' % available_syncers)

        for syncer in enabled_syncers:
            syncer_instance = getattr(
                import_module(available_syncers[syncer]), syncer
            )(progress_callback=self.handle_sync_progress)
            self.syncers[syncer] = syncer_instance
            syncer_instance.start()

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
