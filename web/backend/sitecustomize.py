"""Process-wide secure file creation defaults for API and workers."""

import os

os.umask(0o077)
