#!/usr/bin/env python3
""" API to interface different file syncing methods.

Should support: google drive, dropbox, rsync


.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
import subprocess
import re
import os

from threading import Thread
from time import sleep
from utils.containers import OrderedSetQueue
from utils.log import log
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
        self.syncers = {}
        for syncerName in ['Dropbox', 'Rsync']:
            syncer = globals()[syncerName](
                progress_callback=self.handle_sync_progress)
            self.syncers[syncerName] = syncer
            syncer.start()
        self.start()

    def handle_sync_progress(self, syncer, file, progress):
        log.info("sync progress " + str(progress) + str(syncer))

    def stop(self):
        self.queue.stop()
        [s.stop() for s in self.syncers.values()]
        super().stop()

    def consume_item(self, event):
        self.syncers[event.info['syncer']].queue.put(event)


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
        self.progress_callback(self, event.pathname, 0.0)

        cmd = 'rsync ' + ' '.join([
            config.data['watches'][self.__class__.__name__]['arguments'],
            event.pathname, event.info['target']
        ])
        log.info(cmd)
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
                    self.progress_callback(
                        self, event.pathname, float(progress) / 100
                    )
                line = ''

import dropbox


class Dropbox(SyncBase):
    def __init__(self, *args, **kwargs):
        self.configuration = config.data['configuration'][
            self.__class__.__name__]
        super().__init__(*args, **kwargs)

    def run(self):
        try:
            with open(self.configuration['token_file']) as token_file:
                self.access_token = token_file.read()
        except IOError:
            self.access_token = None

        self.login()
        super().run()

    def authorize(self):
        flow = dropbox.client.DropboxOAuth2FlowNoRedirect(
            self.configuration['app_key'], self.configuration['app_secret'])
        authorize_url = flow.start()

        print('1. Go to: ' + authorize_url)
        print('2. Click "Allow" (you might have to log in first)')
        print('3. Copy the authorization code.')
        code = input("Enter the authorization code here: ").strip()

        # This will fail if the user enters an invalid authorization code
        self.access_token, user_id = flow.finish(code)

        # save token
        token_file = open(self.configuration['token_file'], 'w')
        token_file.write(self.access_token)
        token_file.close()

    def login(self):
        if not (self.access_token):
            self.authorize()
        self.client = dropbox.client.DropboxClient(self.access_token)
        log.debug('dropbox authorized: ' + self.client.account_info()['email'])

    def upload(self, event, dropbox_path):
        with open(event.pathname, 'rb') as file:
            size = os.stat(file.fileno()).st_size
            if size < 100:
                self.client.put_file(dropbox_path, file, overwrite=True)
            else:
                chunk_size = 1024 * 1024
                offset = 0
                upload_id = None
                last_block = None
                while offset < size:
                    next_chunk_size = min(chunk_size, size - offset)
                    if last_block is None:
                        last_block = file.read(next_chunk_size)
                    try:
                        (offset, upload_id) = self.client.upload_chunk(
                            last_block, next_chunk_size, offset, upload_id)
                        self.last_block = None
                        self.progress_callback(
                            self, event.pathname, min(offset, size) / size)
                    except dropbox.rest.ErrorResponse as e:
                        log.exception(e)
                self.client.commit_chunked_upload(
                    dropbox_path, upload_id, overwrite=True, parent_rev=None
                )

    def consume_item(self, event):
        dropbox_path = os.path.join(
            event.info['target'],
            os.path.relpath(event.pathname, event.info['source'])
        )
        log.info('uploading to Dropbox: ' + str(event.pathname) + ' -> ' +
                 dropbox_path)

        self.progress_callback(self, event.pathname, 0.0)
        try:
            self.upload(event, dropbox_path)
        except IOError as e:
            # file was deleted immediatily
            log.debug('upload failded' + str(e))
            self.progress_callback(self, event.pathname, 1.0)
