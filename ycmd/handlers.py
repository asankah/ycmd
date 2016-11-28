# Copyright (C) 2013 Google Inc.
#
# This file is part of ycmd.
#
# ycmd is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ycmd is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ycmd.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from future import standard_library
standard_library.install_aliases()
from builtins import *  # noqa

import logging
import traceback

import ycm_core
from ycmd import extra_conf_store, server_state, user_options_store
from ycmd.responses import BuildExceptionResponse, BuildCompletionResponse
from ycmd.request_wrap import RequestWrap
from ycmd.completers.completer_utils import FilterAndSortCandidatesWrap

_server_state = None
_logger = logging.getLogger(__name__)


def EventNotification(request_data):
  _logger.info('Received event notification')
  request_data = RequestWrap(request_data)
  event_name = request_data['event_name']
  _logger.debug('Event name: %s', event_name)

  event_handler = 'On' + event_name
  getattr(_server_state.GetGeneralCompleter(), event_handler)(request_data)

  filetypes = request_data['filetypes']
  response_data = None
  if _server_state.FiletypeCompletionUsable(filetypes):
    response_data = getattr(
        _server_state.GetFiletypeCompleter(filetypes),
        event_handler)(request_data)

  if response_data:
    return response_data
  return {}


def RunCompleterCommand(request_data):
  _logger.info('Received command request')
  request_data = RequestWrap(request_data)
  completer = _GetCompleterForRequestData(request_data)

  return completer.OnUserCommand(request_data['command_arguments'],
                                 request_data)


def GetCompletions(request_data):
  _logger.info('Received completion request')
  request_data = RequestWrap(request_data)
  (do_filetype_completion, forced_filetype_completion) = (
      _server_state.ShouldUseFiletypeCompleter(request_data))
  _logger.debug('Using filetype completion: %s', do_filetype_completion)

  errors = None
  completions = None

  if do_filetype_completion:
    try:
      completions = (
          _server_state.GetFiletypeCompleter(request_data['filetypes'])
          .ComputeCandidates(request_data))

    except Exception as exception:
      if forced_filetype_completion:
        # user explicitly asked for semantic completion, so just pass the error
        # back
        raise
      else:
        # store the error to be returned with results from the identifier
        # completer
        stack = traceback.format_exc()
        _logger.error('Exception from semantic completer (using general): ' +
                      ''.join(stack))
        errors = [BuildExceptionResponse(exception, stack)]

  if not completions and not forced_filetype_completion:
    completions = (_server_state.GetGeneralCompleter()
                   .ComputeCandidates(request_data))

  return BuildCompletionResponse(
      completions if completions else [],
      request_data.CompletionStartColumn(),
      errors=errors)


def FilterAndSortCandidates(request_data):
  _logger.info('Received filter & sort request')
  # Not using RequestWrap because no need and the requests coming in aren't like
  # the usual requests we handle.
  return FilterAndSortCandidatesWrap(request_data['candidates'],
                                     request_data['sort_property'],
                                     request_data['query'])


def GetHealthy(include_subservers=False):
  _logger.info('Received health request')
  if include_subservers:
    cs_completer = _server_state.GetFiletypeCompleter(['cs'])
    return cs_completer.ServerIsHealthy()
  return True


def GetReady(include_subservers=False, subserver=None):
  _logger.info('Received ready request')
  if subserver:
    filetype = subserver
    return _IsSubserverReady(filetype)
  if include_subservers:
    return _IsSubserverReady('cs')
  return True


def _IsSubserverReady(filetype):
  completer = _server_state.GetFiletypeCompleter([filetype])
  return completer.ServerIsReady()


def FiletypeCompletionAvailable(request_data):
  _logger.info('Received filetype completion available request')
  return _server_state.FiletypeCompletionAvailable(
      RequestWrap(request_data)['filetypes'])


def GetDefinedSubcommands(request_data):
  _logger.info('Received defined subcommands request')
  completer = _GetCompleterForRequestData(RequestWrap(request_data))

  return completer.DefinedSubcommands()


def GetDetailedDiagnostic(request_data):
  _logger.info('Received detailed diagnostic request')
  request_data = RequestWrap(request_data)
  completer = _GetCompleterForRequestData(request_data)

  return completer.GetDetailedDiagnostic(request_data)


def LoadExtraConfFile(request_data):
  _logger.info('Received extra conf load request')
  extra_conf_store.Load(request_data['filepath'], force=True)

  return True


def IgnoreExtraConfFile(request_data):
  _logger.info('Received extra conf ignore request')
  extra_conf_store.Disable(request_data['filepath'])

  return True


def DebugInfo(request_data):
  _logger.info('Received debug info request')

  output = []
  has_clang_support = ycm_core.HasClangSupport()
  output.append('Server has Clang support compiled in: {0}'.format(
      has_clang_support))

  if has_clang_support:
    output.append('Clang version: ' + ycm_core.ClangVersion())

  request_data = RequestWrap(request_data)
  try:
    output.append(
        _GetCompleterForRequestData(request_data).DebugInfo(request_data))
  except Exception:
    _logger.debug('Exception in debug info request: ' + traceback.format_exc())

  return '\n'.join(output)


def _GetCompleterForRequestData(request_data):
  completer_target = request_data.get('completer_target', None)

  if completer_target == 'identifier':
    return _server_state.GetGeneralCompleter().GetIdentifierCompleter()
  elif completer_target == 'filetype_default' or not completer_target:
    return _server_state.GetFiletypeCompleter(request_data['filetypes'])
  else:
    return _server_state.GetFiletypeCompleter([completer_target])


def Shutdown():
  return True


def ServerCleanup():
  if _server_state:
    _server_state.Shutdown()
    extra_conf_store.Shutdown()


def UpdateUserOptions(options):
  global _server_state

  if not options:
    return

  user_options_store.SetAll(options)
  _server_state = server_state.ServerState(options)


def SetServerStateToDefaults():
  global _server_state, _logger
  _logger = logging.getLogger(__name__)
  user_options_store.LoadDefaults()
  _server_state = server_state.ServerState(user_options_store.GetAll())
  extra_conf_store.Reset()


