# -*- coding=utf-8 -*-

paths = [".github", "", "docs"]
endings = [".md", ".txt", ""]
readmes = [
    '/'.join(filter(None, (path, f"README{ending}"))) for path in paths
    for ending in endings
]
