"""TODO(asanka): DO NOT SUBMIT without one-line documentation for embedded_server.

TODO(asanka): DO NOT SUBMIT without a detailed description of embedded_server.
"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
# Other imports from `future` must be placed after SetUpPythonPath.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server_utils import SetUpPythonPath, CompatibleWithCurrentCore
SetUpPythonPath()

from future import standard_library
standard_library.install_aliases()
from builtins import *  # noqa

import atexit
import sys

from concurrent.futures.thread import ThreadPoolExecutor

from ycmd import extra_conf_store, user_options_store, utils
from ycmd.utils import ToBytes, ReadFile, OpenForStdHandle

_EXECUTOR = None
MAX_WORKERS = 4

class FutureWrapper(object):

  def __init__(self, method, executor):
    self._executor = executor
    self._method = method

  def __call__(self, *args, **kwargs):
    return self._executor.submit(self._method, *args, **kwargs)


class WrappedNamespace(object):

  def __init__(self, namespace, executor):
    exported_methods = [
        m for m in dir(namespace)
        if callable(getattr(namespace, m)) and not m.startswith('_')
    ]
    for method in exported_methods:
      setattr(self, method, FutureWrapper(getattr(namespace, method), executor))


def _YcmCoreSanityCheck():
  if 'ycm_core' in sys.modules:
    raise RuntimeError('ycm_core already imported, ycmd has a bug!')


def _SetupOptions(user_options):
  options = user_options_store.DefaultOptions()
  options.update(user_options)
  user_options_store.SetAll(options)
  return options


def StartEmbedded(user_options):
  options = _SetupOptions(user_options)
  _YcmCoreSanityCheck()
  extra_conf_store.CallGlobalExtraConfYcmCorePreloadIfExists()

  code = CompatibleWithCurrentCore()
  if code:
    raise RuntimeError('Core is incompatible.')

  # These can't be top-level imports because they transitively import
  # ycm_core which we want to be imported ONLY after extra conf
  # preload has executed.
  from ycmd import handlers
  handlers.UpdateUserOptions(options)
  atexit.register(handlers.ServerCleanup)

  global _EXECUTOR
  _EXECUTOR = ThreadPoolExecutor(user_options.get('max_workers', MAX_WORKERS))

  return WrappedNamespace(handlers, _EXECUTOR)
