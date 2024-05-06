# -*- coding=utf-8 -*-

# https://github.com/joelparkerhenderson/github-special-files-and-paths#contributing
# usual paths for README files
paths = [".github", "", "docs"]
# README file endings (not official)
# usual file endings for README files
endings = [".md", ".txt", ""]
# concat paths, "README" and endings to valid combinations
readmes = [
    "/".join(filter(None, (path, f"README{ending}")))
    for path in paths
    for ending in endings
]
