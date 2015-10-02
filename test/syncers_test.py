import sys
import os
import time
import string
import random
import tempfile
import shutil
import filecmp

import pkgutil
from importlib import import_module

import pytest

sys.path.append(os.path.abspath(sys.path[0] + os.sep + '..'))
from utils.strings import camelize
from utils.files import write_random_file
import config
from sync_api import SyncManager
from file_watcher import InotifyEvent


REMOTE_ROOT = '/omniSyncTest'

def make_test_file(path, size):
    if size is None:
        os.makedirs(path)
    else:
        head, tail = os.path.split(path)
        if not os.path.isdir(head):
            os.makedirs(head)
        write_random_file(path, size)

def random_string(length):
    return ''.join(random.choice(
        string.ascii_letters + string.digits) for _ in range(length))


@pytest.fixture()
def temp_dir(request):
    temp_dir = tempfile.mkdtemp()
    # make sure temp files are cleaned.
    request.addfinalizer(lambda: shutil.rmtree(temp_dir))
    return temp_dir

@pytest.fixture(scope="module")
def local_temp_filesystem(request):
    temp_root = tempfile.mkdtemp()
    # make sure temp files are cleaned.
    request.addfinalizer(lambda: shutil.rmtree(temp_root))

    test_files = [(os.path.join(temp_root, file), size) for file, size in [
        ('1/2/', None),     # folder
        ('1/a', 50),        # file
        ('1/b', 150),
        ('1/1/a', 1500),
    ]]

    for path, size in test_files:
        make_test_file(path, size)
    return {'files': [file for file, size in test_files], 'root': temp_root}

@pytest.fixture(scope='class', params=['GoogleDrive', 'Dropbox'])
#@pytest.fixture(scope='class', params=['Dropbox'])
def syncer(request):
    syncer = SyncManager.get_syncer_instances(
            filter=lambda syncer: syncer == request.param)[request.param]
    syncer.init()
    syncer.rm(REMOTE_ROOT, trash=False)

    def clean():
        print('removing remote')
        syncer.rm(REMOTE_ROOT, trash=False)
    request.addfinalizer(clean)
    return syncer


class TestSyncer():
    def generate_test_events(self, syncer, filesystem, types):
        for f in filesystem['files']:
            for t in types:
                yield InotifyEvent(
                    None,
                    {'source': filesystem['root'],
                    'syncers': [syncer.__class__.__name__],
                    'target': REMOTE_ROOT},
                    file_name=os.path.basename(f),
                    base_path=os.path.dirname(f),
                    source_absolute=f,
                    isdir=os.path.isdir(f),
                    type=t,
                )

    def test_upload(self, syncer, local_temp_filesystem):
        for event in self.generate_test_events(
                syncer, local_temp_filesystem, ['CREATE']):
            syncer.consume_item(event)
        local_files = [
            os.path.relpath(x, local_temp_filesystem['root']) for x in
            local_temp_filesystem['files']
        ]
        remote_files = [
            os.path.relpath(x, REMOTE_ROOT) for x in
            syncer.walk(start=REMOTE_ROOT)
        ]
        for file in local_files:
            assert file in remote_files

    def test_download(self, syncer, temp_dir):
        local_file = os.path.join(temp_dir, 'up')
        local_file_downloaded = os.path.join(temp_dir, 'down')
        remote_file = 'omniSyncTest' + random_string(10)

        write_random_file(local_file, 100)
        syncer.upload(local=local_file, remote=remote_file)

        syncer.download(local=local_file_downloaded, remote=remote_file)
        assert filecmp.cmp(local_file, local_file_downloaded)


if __name__ == "__main__":
    unittest.main()
