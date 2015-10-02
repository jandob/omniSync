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

    # region overrides
    def run(self):
        self.login()
        super().run()

    def init(self):
        self.login()

    def consume_item(self, event):
        log.info('uploading to Dropbox: %s -> %s' %
                 (event.source_absolute, event.target_absolute))

        self.send_progress(event.source_absolute, 0.0)
        try:
            self._upload(event, event.target_absolute)
        except IOError as e:
            # file was deleted immediatily
            log.warning('upload failed' + str(e))
            self.send_progress(event.source_absolute, 1.0)

    def walk(self, start='/'):
        response = self.client.delta(cursor=None, path_prefix=start)
        files = [x[1]['path'] for x in response['entries']]
        while response['has_more']:
            response = self.client.delta(
                    cursor=response['cursor'], path_prefix=start
            )
            files.append([x[1]['path'] for x in response['entries']])
        return files

    def rm(self, path, *args, **kwargs):
        if path == '/':
            log.critical('prevented delete / (root)')
            return
        try:
            self.client.file_delete(path)
        except dropbox.rest.ErrorResponse as e:
            log.debug('Delete failed: %s (%s)' % (e.reason, path))
            if not e.reason == 'Not Found':
                raise e

    def download(self, local, remote):
        out = open(local, 'wb')
        with self.client.get_file(
            remote, rev=None, start=None, length=None
        ) as file:
            out.write(file.read())

    def upload(self, local, remote):
        with open(local, 'rb') as file:
            self._put_file(file, local, remote)

    # endregion

    # region authorization
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
        token_file = os.path.expanduser(self.configuration['token_file'])
        token_dir = os.path.dirname(token_file)
        if not os.path.exists(token_dir):
            os.makedirs(token_dir)
        try:
            with open(token_file) as token:
                self.access_token = token.read()
        except IOError:
            self.access_token = None
        if not (self.access_token):
            self.authorize()
        self.client = dropbox.client.DropboxClient(self.access_token)
        log.debug('dropbox authorized: ' + self.client.account_info()['email'])
    # endregion

    # region file operations
    def _put_file(self, file, local_path, dropbox_path):
        size = os.stat(file.fileno()).st_size
        if size < 1000: # kb
            self.client.put_file(dropbox_path, file, overwrite=True)
            self.send_progress(local_path, 1.0)
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
                    self.send_progress(local_path, min(offset, size) / size)
                except dropbox.rest.ErrorResponse as e:
                    log.exception(e)
            self.client.commit_chunked_upload(
                'auto' + dropbox_path, upload_id,
                overwrite=True, parent_rev=None
            )

    def _upload(self, event, dropbox_path):
        if event.isdir:
            if event.type != 'CREATE': return
            try:
                self.client.file_create_folder(dropbox_path)
            except dropbox.rest.ErrorResponse as e:
                log.exception(e)
            finally: return

        with open(event.source_absolute, 'rb') as file:
            self._put_file(file, event.source_absolute, dropbox_path)
    # endregion

if __name__ == '__main__':
    sys.path = sys.path[1:]
    import dropbox
    remote = Dropbox(
        progress_callback=lambda syncer, path, progress:
        log.info("%s: %s %s" % (syncer.name, progress, path))
    )
    remote.init()
    remote.walk('/')


# region modline

# vim: set tabstop=4 shiftwidth=4 expandtab:
# vim: foldmethod=marker foldmarker=region,endregion:

# endregion
