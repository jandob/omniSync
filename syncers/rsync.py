#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.abspath(sys.path[0] + os.sep + '..'))
import subprocess
import re

from sync_api import SyncBase
import config
from utils.log import log


class Rsync(SyncBase):
    def __init__(self, progress_callback=None):
        super().__init__(progress_callback)
        self.fullsync()

    def push(self, event):
        self.progress_callback(self, event.source_absolute, 0.0)
        cmd = ' '.join([
            'cd', event.source_dir, '&&', 'rsync',
            '--relative',
            config.data['configuration'][self.class_name]['arguments'],
            event.source_relative, event.target_dir
        ])
        log.info(cmd)
        process = subprocess.Popen(
            cmd, shell=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )
        self.parse_output(process, event.source_absolute)

    def parse_output(self, process, name):
        # parse rsync output
        line = ''
        while process.poll() is None:
            byte = process.stdout.read(1)
            line += byte.decode('utf-8')
            if byte == b'\r' or byte == b'\n':
                #speed = next(iter(re.findall(r'\S*/s', line)), None)
                #files = next(iter(re.findall(r'(\d)/(\d+)', line)), None)
                progress = next(iter(re.findall(r'(\d+)%', line)), None)
                if progress:
                    self.progress_callback(
                        self, name, float(progress) / 100)
                line = ''

    def delete(self, event):
        self.progress_callback(self, event.source_absolute, 0.0)
        cmd = ' '.join([
            'rm', os.path.join(event.target_dir, event.source_relative)
        ])
        log.info(cmd)
        subprocess.check_call(cmd, shell=True)
        self.progress_callback(self, event.source_absolute, 1.0)

    def consume_item(self, event):
        if event.type in ['delete', 'moved_from']:
            self.delete(event)
        else:
            self.push(event)

    def fullsync(self, pull=False):
        """
            pull==True pull from target (overwriting source)
        """
        for watch_config in filter(
            lambda x: x['syncer'] == self.class_name and not x.get('disabled'),
            config.data['watches']
        ):
            self.progress_callback(self, watch_config['source'], 0.0)
            excludes = ' '.join(
                ['--exclude=' + x for x in watch_config['exclude']])
            cmd = ' '.join([
                'rsync', '--info=progress2', excludes,
                config.data['configuration'][self.class_name]['arguments']
            ]) + ' '
            if pull:
                cmd += ' '.join([
                    watch_config['target'], watch_config['source']
                ])
            else:
                cmd += ' '.join([
                    watch_config['source'], watch_config['target']
                ])
            log.info(cmd)
            process = subprocess.Popen(
                cmd, shell=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            )
            self.parse_output(process, 'fullsync')
            self.progress_callback(self, watch_config['source'], 1.0)
