#!/usr/bin/env python3
""" API to interface different file syncing methods.

Should support: google drive, dropbox, rsync


.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
import subprocess
import re
import sys

from threading import Thread
from time import sleep
from utils import OrderedSetQueue


class QueueConsumer(Thread):
    def __init__(self, queue=None):
        self.queue = queue or OrderedSetQueue()
        super().__init__()
        print(self.__class__.__name__ + " init")

    def run(self):
        print(self.__class__.__name__ + " running")
        while True:
            item = self.queue.get()
            if item is None:  # trick to break out of while
                break
            self.consume_item(item)
            # TODO what if a file gets added again while syncing in progress?
            self.queue.task_done()

    def stop(self):
        self.queue.put(None)  # trick to break out of while
        print(self.__class__.__name__ + " stopped")

    def consume_item(self, item): raise NotImplementedError


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
        self.syncers = []
        for syncerName in ['Dropbox', 'Rsync']:
            syncer = globals()[syncerName](
                progress_callback=self.handle_sync_progress)
            self.syncers.append(syncer)
            syncer.start()
        self.start()

    def handle_sync_progress(self, syncer, event, progress):
        print("handle sync progress ", progress, syncer)

    def stop(self):
        self.queue.stop()
        [s.stop() for s in self.syncers]
        super().stop()

    def consume_item(self, item):
        for syncer in self.syncers:
            # TODO exclude files for syncers
            syncer.queue.put(item)


class SyncBase(QueueConsumer):
    def __init__(self, progress_callback=None):
        """
        Args:
            progress_callback (callable):
                Is called regularly with the progress of the syncing process.
                Range: 0.0 - 1.0
        """
        super().__init__()
        self.progress_callback = progress_callback


class Rsync(SyncBase):
    def consume_item(self, event):
        print("rsync ", event)  # TODO
        self.progress_callback(self, event, 0.0)
        cmd = 'rsync --progress --archive --bwlimit=30000 ' + event + ' /home/h4ct1c/omnisync/remote/'
        print(cmd)
        process = subprocess.Popen(
            cmd, shell=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )

        # parse rsync output
        line = ''
        while process.poll() is None:
            byte = process.stdout.read(1)
            line += byte.decode('utf-8')
            if byte == b'\r' or byte == b'\n':
                progress = next(iter(re.findall(r'(\d+)%', line)), None)
                #speed = next(iter(re.findall(r'\S*/s', line)), None)
                if progress:
                    self.progress_callback(self, event, float(progress) / 100)
                line = ''

import dropbox


class Dropbox(SyncBase):
    # Get your app key and secret from the Dropbox developer website
    APP_KEY = 'hrdd29m6nc8u2sy'
    APP_SECRET = '175c646bfl1csbu'
    TOKEN_FILE = 'dropbox_token.txt'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        try:
            with open(self.TOKEN_FILE) as token_file:
                self.access_token = token_file.read()
        except IOError:
            self.access_token = None

        self.login()
        super().run()

    def authorize(self):
        flow = dropbox.client.DropboxOAuth2FlowNoRedirect(
            self.APP_KEY, self.APP_SECRET)
        authorize_url = flow.start()

        print('1. Go to: ' + authorize_url)
        print('2. Click "Allow" (you might have to log in first)')
        print('3. Copy the authorization code.')
        code = input("Enter the authorization code here: ").strip()

        # This will fail if the user enters an invalid authorization code
        self.access_token, user_id = flow.finish(code)

        # save token
        token_file = open(self.TOKEN_FILE, 'w')
        token_file.write(self.access_token)
        token_file.close()

    def login(self):
        if not (self.access_token):
            self.authorize()
        client = dropbox.client.DropboxClient(self.access_token)
        print('linked account: ', client.account_info())

    def consume_item(self, event):
        pass
        #self.progress_callback(self, event, 0.0)
        #print("dropbox ", event)  # TODO
        #sleep(1)
        #self.progress_callback(self, event, 0.5)
        #sleep(1)
        #self.progress_callback(self, event, 1.0)
