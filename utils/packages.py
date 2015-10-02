#!/usr/bin/env python3
import pkgutil
import pyclbr

def find_modules_with_super_class(pkg, super_class):
    for importer, modname, ispkg in pkgutil.walk_packages(pkg.__path__):
        if ispkg: continue
        import_path = "%s.%s" % (pkg.__name__, modname)
        module = pyclbr.readmodule(import_path)
        for item, val in module.items():
            if super_class.__name__ in val.super:
                yield item, import_path
