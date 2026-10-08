"""Madar release deployment helpers; controller imports never write bytecode."""
import sys

# Also protect direct trusted imports, not just the -IB installed launchers.
# The installer publishes source-only trees; entrypoints reject existing caches.
sys.dont_write_bytecode = True
