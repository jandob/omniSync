#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.abspath(sys.path[0] + os.sep + '..'))
import time
import mimetypes
import httplib2

# google drive stuff
from apiclient import discovery
import oauth2client
from argparse import ArgumentParser
from oauth2client.client import OAuth2WebServerFlow
from apiclient.http import MediaFileUpload
from apiclient.http import MediaIoBaseUpload

import config
from utils.log import log
from sync_api import SyncBase

SCOPES = 'https://www.googleapis.com/auth/drive'
APPLICATION_NAME = 'omniSync'
MIME_FOLDER = "application/vnd.google-apps.folder"


class GoogleDrive(SyncBase):

    def __init__(self, *args, **kwargs):
        self.configuration = config.data['configuration'][
            self.__class__.__name__]
        self.service = None
        super().__init__(*args, **kwargs)

    # region overrides
    def run(self):
        self.get_credentials()
        self.authorize()
        # TODO cache services? (files(), children() etc)
        super().run()

    def init(self):
        self.get_credentials()
        self.authorize()

    def consume_item(self, event):
        log.info('uploading to GoogleDrive: %s -> %s' %
                 (event.source_absolute, event.target_absolute))

        self.send_progress(event.source_absolute, 0.0)
        # TODO handle dir/file removal
        try:
            if event.isdir:
                self._path_to_ids(event.target_absolute, create_missing=True)
            else:
                self._put_file(event.source_absolute, event.target_absolute)
        except IOError as e:
            # file was deleted immediatily?
            log.warning('upload failed' + str(e))
        finally:
            self.send_progress(event.source_absolute, 1.0)

    def walk(self, start='/'):
        return (x['path'] + x['title'] for x in self._walk(start=start))

    def rm(self, path, trash=True):
        path_ids = self._path_to_ids(path)
        if not path_ids:
            return
        if trash:
            self.service.files().trash(fileId=path_ids[-1]).execute()
        else:
            self.service.files().delete(fileId=path_ids[-1]).execute()

    def download(self, local, remote):
        url = self._get_file(remote)['downloadUrl']
        resp, content = self.service._http.request(url)
        if resp.status == 200:
            with open(local, 'wb') as file:
                file.write(content)
        else:
            raise IOError

    def upload(self, local, remote):
        self._put_file(local, remote)

    # endregion

    # region authorization
    def authorize(self):
        self.service = discovery.build(
            'drive', 'v2',
            http=self.credentials.authorize(httplib2.Http())
        )

    def get_credentials(self):
        """Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.

        """

        token_file = os.path.expanduser(self.configuration['token_file'])
        token_dir = os.path.dirname(token_file)
        if not os.path.exists(token_dir):
            os.makedirs(token_dir)

        store = oauth2client.file.Storage(token_file)
        credentials = store.get()
        if not credentials or credentials.invalid:
            client_config = self.configuration['client_config']
            flow = OAuth2WebServerFlow(
                client_config['client_id'],
                client_config['client_secret'],
                SCOPES,
                redirect_uris=client_config['redirect_uris'],
                auth_uri=client_config['auth_uri'],
                token_uri=client_config['token_uri'])
            flow.user_agent = APPLICATION_NAME
            credentials = oauth2client.tools.run_flow(
                flow, store,
                ArgumentParser(
                    parents=[oauth2client.tools.argparser]).parse_args()
            )
            print('Storing credentials to ' + token_file)

        self.credentials = credentials
    # endregion authorization

    # region file operations
    def _put_file(self, source_absolute, target_absolute):
        mimetype = mimetypes.guess_type(source_absolute)[0]
        mimetype = mimetype or 'application/octet-stream'
        #media = MediaFileUpload(
            #source_absolute,
            #mimetype=mimetype,
            #chunksize=1024 * 1024, resumable=True
        #)
        media = MediaIoBaseUpload(
            open(source_absolute, 'rb'), mimetype,
            chunksize=1024 * 1024, resumable=True
        )
        file = self._get_file(target_absolute)
        if file:
            self.service.files().update(
                fileId=file['id'], media_body=media).execute()
        else:
            basedir, file_name = os.path.split(target_absolute)
            folder_ids = self._path_to_ids(basedir, create_missing=True)
            self.service.files().insert(
                body={
                    'title': file_name,
                    'parents': [{'id': folder_ids[-1]}]
                },
                media_body=media
            ).execute()

    def _create_folder(self, folder_name, parent_id=None):
        body = {
            'title': folder_name,
            'mimeType': MIME_FOLDER
        }
        if parent_id:
            body['parents'] = [{'id': parent_id}]
        response = self.service.files().insert(
            body=body
        ).execute()
        return response['id']

    def _get_file(self, target_absolute):
        file_ids = self._path_to_ids(target_absolute)
        if file_ids is not None:
            return self.service.files().get(fileId=file_ids[-1]).execute()
        else:
            return None
    # endregion

    # region helpers
    def _walk(self, start='/', _folder_id=None):
        if not start.endswith('/'):
            start += '/'
        if _folder_id is None:
            _folder_id = self._path_to_ids(start)[-1]
        files = self._list_folder(_folder_id)
        for file in files:
            file['path'] = start
            yield file
            if file['mimeType'] == MIME_FOLDER:
                yield from self._walk(
                    start=start + file['title'] + '/',
                    _folder_id=file['id'],
                )

    def _path_to_ids(self, path, create_missing=False):
        """
        Note: If create_missing is set all parts of path are created as folder
        """
        # '/path/to/folder/' -> ['path', 'to', 'folder']
        # '/path/to/folder/file' -> ['path', 'to', 'folder', 'file']
        folder_list = list(filter(
            lambda x: x != '', path.strip(os.sep).split(os.sep)))
        id_list = ['root']
        #if folder_list == ['']:
            #return id_list
        for folder in folder_list:
            response = self.service.children().list(
                folderId=id_list[-1],
                q='title = "%s" and trashed = false' % (folder)
            ).execute()['items']
            if len(response) is 1:
                id_list.append(response[0]['id'])
            elif len(response) is 0:
                if create_missing:
                    print('creating folder: ', folder)
                    id_list.append(self._create_folder(
                        folder, parent_id=id_list[-1]))
                else:
                    return None  # folder not found
            else:
                # TODO handle cases of file in multiple folders or files with
                # same name
                raise IOError  # TODO make custom exception
        return id_list

    def _list_folder(self, folder_id='root'):
        results = self.service.files().list(
            maxResults=None,
            q='"%s" in parents and trashed = false' % (folder_id),
        ).execute()
        return results.get('items', [])
    # endregion

if __name__ == '__main__':
    from file_watcher import InotifyEvent
    test_file_name = '/home/h4ct1c/omnisync/local/test2'
    test_event = InotifyEvent(
        None,
        {'source': '/home/h4ct1c/omnisync/local/',
         'syncers': ['GoogleDrive'],
         'target': '/omniSync'},
        mask=None,
        file_name=os.path.basename(test_file_name),
        base_path=os.path.dirname(test_file_name),
        source_absolute=test_file_name,
        isdir=False
    )

    drive = GoogleDrive(
        progress_callback=lambda syncer, file, progress:
        log.info("%s: %s %s" % (syncer.name, progress, file))
    )
    drive.get_credentials()
    drive.authorize()
    for item in drive.walk():
        print(item)
    #drive.consume_item(test_event)
    #drive._create_folder('omniSync')
    #drive._path_to_ids('/omniSync/', create_missing=True)
    #drive._get_file('omnisync')

# region modline

# vim: set tabstop=4 shiftwidth=4 expandtab:
# vim: foldmethod=marker foldmarker=region,endregion:

# endregion
