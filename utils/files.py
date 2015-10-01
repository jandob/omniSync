#!/usr/bin/env python3
import os

def write_random_file(path, size_kb):
    with open(path, 'wb') as f:
        f.write(os.urandom(size_kb))
