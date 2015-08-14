#!/usr/bin/env python3
""" API to interface different file syncing methods.

Should support: google drive, dropbox, rsync


.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
from threading import Thread
from time import sleep


class SyncBase(Thread):
    def __init__(self, queue, progress_callback=None):
        """
        Args:
            queue (queue.Queue): Queue with files to sync.
            progress_callback (callable):
                Is called regularly with the progress of the syncing process.
                Range: 0.0 - 1.0
        """
        super().__init__()
        self.queue = queue
        self.progress_callback = progress_callback

    def run(self):
        while True:
            file = self.queue.get()
            if file is None:  # trick to break out of while
                break
            self.sync(file)
            self.queue.task_done()

    def stop(self):
        #self.queue.save()  # TODO handle cancellation
        self.queue.put(None)  # trick to break out of while
        print("rsync stopped")

    def sync(self, file): raise NotImplementedError


class Rsync(SyncBase):
    def sync(self, file):
        self.progress_callback(0.0)
        print("rsync ", file)  # TODO
        sleep(1)
        self.progress_callback(0.5)
        sleep(1)
        self.progress_callback(1.0)
