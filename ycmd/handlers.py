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

import bottle
import json
import logging
import time
import traceback
from bottle import request
from threading import Thread

import ycm_core
from ycmd import hmac_plugin
from ycmd.responses import BuildExceptionResponse
from ycmd.bottle_utils import SetResponseHeader
from ycmd import requests


# num bytes for the request body buffer; request.json only works if the request
# size is less than this
bottle.Request.MEMFILE_MAX = 10 * 1024 * 1024

_hmac_secret = bytes()
_logger = logging.getLogger( __name__ )
app = bottle.Bottle()
wsgi_server = None


@app.post( '/event_notification' )
def EventNotification():
  return _JsonResponse( requests.EventNotification( request.json ) )


@app.post( '/run_completer_command' )
def RunCompleterCommand():
  return _JsonResponse( requests.RunCompleterCommand( request.json ) )


@app.post( '/completions' )
def GetCompletions():
  return _JsonResponse( requests.GetCompletions( request.json ) )


@app.post( '/filter_and_sort_candidates' )
def FilterAndSortCandidates():
  return _JsonResponse( requests.FilterAndSortCandidates( request.json ) )


@app.get( '/healthy' )
def GetHealthy():
  return _JsonResponse( requests.GetHealthy(
      request.query.include_subservers ) )


@app.get( '/ready' )
def GetReady():
  return _JsonResponse( requests.GetReady(
      subserver=request.query.subserver,
      include_subservers=request.query.include_subservers ) )


@app.post( '/semantic_completion_available' )
def FiletypeCompletionAvailable():
  return _JsonResponse( requests.FiletypeCompletionAvailable(
      request.json ) )


@app.post( '/defined_subcommands' )
def DefinedSubcommands():
  return _JsonResponse( requests.DefinedSubcommands( request.json ) )


@app.post( '/detailed_diagnostic' )
def GetDetailedDiagnostic():
  return _JsonResponse( requests.GetDetailedDiagnostic( request.json ) )


@app.post( '/load_extra_conf_file' )
def LoadExtraConfFile():
  return _JsonResponse( requests.LoadExtraConfFile( request.json ) )


@app.post( '/ignore_extra_conf_file' )
def IgnoreExtraConfFile():
  return _JsonResponse( requests.IgnoreExtraConfFile( request.json ) )


@app.post( '/debug_info' )
def DebugInfo():
  return _JsonResponse( requests.DebugInfo( request.json ) )


@app.post( '/shutdown' )
def Shutdown():
  _logger.info( 'Received shutdown request' )
  ServerShutdown()

  return _JsonResponse( True )


# The type of the param is Bottle.HTTPError
def ErrorHandler( httperror ):
  body = _JsonResponse( BuildExceptionResponse( httperror.exception,
                                                httperror.traceback ) )
  hmac_plugin.SetHmacHeader( body, _hmac_secret )
  return body


# For every error Bottle encounters it will use this as the default handler
app.default_error_handler = ErrorHandler


def _JsonResponse( data ):
  SetResponseHeader( 'Content-Type', 'application/json' )
  return json.dumps( data, default = _UniversalSerialize )


def _UniversalSerialize( obj ):
  try:
    serialized = obj.__dict__.copy()
    serialized[ 'TYPE' ] = type( obj ).__name__
    return serialized
  except AttributeError:
    return str( obj )


def ServerShutdown():
  def Terminator():
    if wsgi_server:
      wsgi_server.Shutdown()

  # Use a separate thread to let the server send the response before shutting
  # down.
  terminator = Thread( target = Terminator )
  terminator.daemon = True
  terminator.start()


def ServerCleanup():
  requests.ServerCleanup()


def SetHmacSecret( hmac_secret ):
  global _hmac_secret
  _hmac_secret = hmac_secret


def UpdateUserOptions( options ):
  requests.UpdateUserOptions( options )


def SetServerStateToDefaults():
  requests.SetServerStateToDefaults()


def KeepSubserversAlive( check_interval_seconds ):
  def Keepalive( check_interval_seconds ):
    while True:
      time.sleep( check_interval_seconds )

      _logger.debug( 'Keeping subservers alive' )
      loaded_completers = requests.GetLoadedFiletypeCompleters()
      for completer in loaded_completers:
        completer.ServerIsHealthy()

  keepalive = Thread( target = Keepalive,
                      args = ( check_interval_seconds, ) )
  keepalive.daemon = True
  keepalive.start()
