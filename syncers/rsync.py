#!/usr/bin/env python3

import builtins
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
        builtins.super(self.__class__, self).__init__(progress_callback)

    @staticmethod
    def event_hash_function(event):
        # use base_path as hash in order to prevent overflowing the queue
        if event.isdir:
            return event.source_absolute
        return event.base_path

    def push_dir(self, event):
        self.progress_callback(self, event.source_absolute, 0.0)
        cmd = ['rsync', '--no-r'] + \
            config.data['configuration'][self.name]['arguments'] + \
            [event.base_path, event.target_base_dir_absolute]
        log.info(cmd)
        process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )
        self.parse_output(process, event.source_absolute)

    def push_file(self, event):
        # currently not used
        if not event.isdir:
            print('dir skipped (TODO)')
            return
        self.progress_callback(self, event.source_absolute, 0.0)
        cmd = ['rsync', '--relative'] + \
            config.data['configuration'][self.name]['arguments'] + \
            [event.source_relative, event.target_base_dir]
        #log.info(cmd)
        process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            cwd=event.source_base_dir
        )
        self.parse_output(process, event.source_absolute)

    def parse_output(self, process, name):
        # parse rsync output
        line = ''
        progress = None
        while process.poll() is None:
            byte = process.stdout.read(1)
            line += byte.decode('utf-8')
            if byte == b'\r' or byte == b'\n':
                #speed = next(iter(re.findall(r'\S*/s', line)), None)
                #files = next(iter(re.findall(r'(\d)/(\d+)', line)), None)
                new_progress = next(iter(re.findall(r'(\d+)%', line)), None)
                if new_progress and new_progress != progress:
                    progress = new_progress
                    self.progress_callback(
                        self, name, float(progress) / 100)
                line = ''
        if progress != '100':
            self.progress_callback(self, name, 1.0)

    def delete(self, event):

        self.progress_callback(self, event.source_absolute, 0.0)
        cmd = [
            'rm', os.path.join(event.target_base_dir, event.source_relative)
        ]
        if event.isdir:
            cmd = ['rm', '-rf'] + cmd[1:]
        log.info(cmd)
        subprocess.check_call(cmd)
        self.progress_callback(self, event.source_absolute, 1.0)

    def consume_item(self, event):
        if event.type in ['DELETE', 'MOVED_FROM']:
            self.delete(event)
        else:
            #self.push_file(event)
            self.push_dir(event)

    def fullsync(self, pull=False):
        """
            pull==True pull from target (overwriting source)
        """
        for watch_config in filter(
            lambda x: self.name in x['syncers'] and not x.get('disabled'),
            config.data['watches']
        ):
            self.progress_callback(self, watch_config['source'], 0.0)
            excludes = ' '.join(
                ['--exclude=' + x for x in watch_config.get('exclude', [])])
            cmd = ' '.join([
                'rsync', '--info=progress2', excludes,
                config.data['configuration'][self.name]['arguments']
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
