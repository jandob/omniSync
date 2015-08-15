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
        print(self.__class__.__name__ + " stopped")

    def sync(self, file): raise NotImplementedError


class Rsync(SyncBase):
    def sync(self, file):
        self.progress_callback(0.0)
        print("rsync ", file)  # TODO
        sleep(1)
        self.progress_callback(0.5)
        sleep(1)
        self.progress_callback(1.0)


import dropbox


class Dropbox(SyncBase):
    # Get your app key and secret from the Dropbox developer website
    APP_KEY = 'hrdd29m6nc8u2sy'
    APP_SECRET = '175c646bfl1csbu'
    TOKEN_FILE = 'dropbox_token.txt'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            with open(self.TOKEN_FILE) as token_file:
                self.access_token = token_file.read()
        except IOError:
            self.access_token = None

        self.login()

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

    def sync(self, file):
        pass
