#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.abspath(sys.path[0] + os.sep + '..'))

import dropbox

from sync_api import SyncBase
import config
from utils.log import log


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

    def _put_file(self, file, event, dropbox_path):
        size = os.stat(file.fileno()).st_size
        if size < 100:
            self.client.put_file(dropbox_path, file, overwrite=True)
            self.progress_callback(self, event.source_absolute, 1.0)
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
                        self, event.source_absolute, min(offset, size) / size)
                except dropbox.rest.ErrorResponse as e:
                    log.exception(e)
            self.client.commit_chunked_upload(
                dropbox_path, upload_id, overwrite=True, parent_rev=None
            )

    def upload(self, event, dropbox_path):
        if event.isdir:
            if event.type != 'CREATE': return
            try:
                self.client.file_create_folder(dropbox_path)
            except dropbox.rest.ErrorResponse as e:
                log.exception(e)
            finally: return

        with open(event.source_absolute, 'rb') as file:
            self._put_file(file, event, dropbox_path)

    def consume_item(self, event):
        log.info('uploading to Dropbox: %s -> %s' %
                 (event.source_absolute, event.target_absolute))

        self.progress_callback(self, event.source_absolute, 0.0)
        try:
            self.upload(event, event.target_absolute)
        except IOError as e:
            # file was deleted immediatily
            log.warning('upload failed' + str(e))
            self.progress_callback(self, event.source_absolute, 1.0)

    def pull():
        pass
