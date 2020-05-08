#!/usr/bin/python3
#
# imap2thehive.py - Poll a IMAP mailbox and create new cases/alerts in TheHive
#
# Author: Xavier Mertens <xavier@rootshell.be>
# Copyright: GPLv3 (http://gplv3.fsf.org)
# Fell free to use the code, but please share the changes you've made
#
# Todo:
# - Configuration validation
# - Support for GnuPG
#

from __future__ import print_function
from __future__ import unicode_literals
import logging
import logging.config
import argparse
import configparser
import os,sys
import tempfile
import re

import mailFetcher



__author__     = "Xavier Mertens"
__license__    = "GPLv3"
__version__    = "1.0.7"
__maintainer__ = "Xavier Mertens"
__email__      = "xavier@rootshell.be"
__name__       = "imap2thehive"

log = ''
args = ''

# Default configuration 
config = {
    'imapHost'           : '',
    'imapPort'           : 993,
    'imapUser'           : '',
    'imapPassword'       : '',
    'imapFolder'         : '',
    'imapExpunge'        : False,
    'imapSpam'           : '',
    'thehiveURL'         : '',
    'thehiveApiKey'	 : '',
    'thehiveObservables' : False,
    'thehiveWhitelists'  : None,
    'mailHandlers'       : {},
    'caseTLP'            : '',
    'caseTags'           : ['email'],
    'caseTasks'          : [],
    'caseFiles'          : [],
    'caseTemplate'       : '',
    'alertTLP'           : '',
    'alertTags'          : ['email'],
    'alertKeyword'       : '\S*\[ALERT\]\S*',
    'customObservables'  : {}
}



'''
Build "observable whitelists" from the given whitelist file.
'''
whitelists = []
def loadWhitelists(filename):
    '''
    Read regex from the provided file, validate them and populate the list
    '''
    if not filename:
        return []

    try:
        lines = [line.rstrip('\n') for line in open(filename)]
    except IOError as e:
        log.error('Cannot read %s: %s' % (filename, e.strerror))
        sys.exit(1)

    i = 1
    w = []
    for l in lines:
        if len(l) > 0:
            if l[0] == '#':
                # Skip comments and empty lines
                continue
            try:
                re.compile(l)
            except re.error:
                log.error('Line %d: Regular expression "%s" is invalid.' % (l, f))
                sys.exit(1)
            i += 1
            w.append(l)
    return w

'''
Load and parse the config from the config file.
'''
def loadConfig():
    global args
    global config
    global log

    parser = argparse.ArgumentParser(
        description = 'Process an IMAP folder to create TheHive alerts/cased.')
    parser.add_argument('-v', '--verbose',
        action = 'store_true',
        dest = 'verbose',
        help = 'verbose output',
        default = False)
    parser.add_argument('-c', '--config',
        dest = 'configFile',
        help = 'configuration file (default: /etc/imap2thehive.conf)',
        metavar = 'CONFIG')
    args = parser.parse_args()

    # Default values
    if not args.configFile:
        args.configFile = '/etc/imap2thehive.conf'
    if not args.verbose:
        args.verbose = False

    if not os.path.isfile(args.configFile):
        log.error('Configuration file %s is not readable.' % args.configFile)
        sys.exit(1);

    try:
        c = configparser.ConfigParser()
        c.read(args.configFile)
    except OSerror as e:
        log.error('Cannot read config file %s: %s' % (args.configFile, e.errno))
        sys.exit(1)

    logging.config.fileConfig(args.configFile)

    if args.verbose:
        root_logger = logging.getLogger('root')
        root_logger.setLevel(logging.DEBUG)

    log = logging.getLogger(__name__)

    # IMAP Config
    config['imapHost']          = c.get('imap', 'host')
    if c.has_option('imap', 'port'):
        config['imapPort']      = int(c.get('imap', 'port'))
    config['imapUser']          = c.get('imap', 'user')
    config['imapPassword']      = c.get('imap', 'password')
    config['imapFolder']        = c.get('imap', 'folder')
    if c.has_option('imap', 'expunge'):
        value = c.get('imap', 'expunge')
        if value == '1' or value == 'true' or value == 'yes':
             config['imapExpunge']   = True
    if c.has_option('imap', 'spam'):
        config['imapSpam']          = c.get('imap', 'spam')
        try:
            re.compile(config['imapSpam'])
        except re.error:
            log.error('Regular expression "%s" is invalid.' % config['imapSpam'])
            sys.exit(1)

    # TheHive Config
    config['thehiveURL']        = c.get('thehive', 'url')
    config['thehiveApiKey']     = c.get('thehive', 'apikey')
    if c.has_option('thehive', 'observables'):
        value = c.get('thehive', 'observables')
        if value == '1' or value == 'true' or value == 'yes':
            config['thehiveObservables'] = True
    if c.has_option('thehive', 'whitelists'):
        config['thehiveWhitelists'] = c.get('thehive', 'whitelists')

    # Custom mail handler config
    mailHandlerKeywords = c.get('mailhandler', 'keywords').split(',')
    mailHandlerModuleNames = c.get('mailhandler', 'modulenames').split(',')
    i = 0
    for k in mailHandlerKeywords:
        config['mailHandlers'][ k ] = mailHandlerModuleNames[ i ]
        i = i + 1
    log.info('config[mailHandlers]: %s' % config['mailHandlers'])

    # Case config
    # Email subject encoding for email to existing case matching:
    config['subjectCaseIdEncodingCustomPrefix'] = c.get('case', 'subjectCaseIdEncodingCustomPrefix')
    config['subjectCaseIdEncodingPrefix'] = '\('+config['subjectCaseIdEncodingCustomPrefix']+':#'
    config['subjectCaseIdEncodingPostfix'] = '\)'
    config['subjectCaseIdEncodingRegEx'] = config['subjectCaseIdEncodingPrefix']+'\w*'+config['subjectCaseIdEncodingPostfix']

    # Defaults for new cases:
    config['caseTLP']           = c.get('case', 'tlp')
    config['caseTags']          = c.get('case', 'tags').split(',')
    if c.has_option('case', 'tasks'):
        config['caseTasks']     = c.get('case', 'tasks').split(',')
    if c.has_option('case', 'template'):
        config['caseTemplate']  = c.get('case', 'template')
    if c.has_option('case', 'files'):
        config['caseFiles']     = c.get('case', 'files').split(',')

    # Get custom observables if any
    for o in c.options("custom_observables"):
        # Validate the regex
        config['customObservables'][o] = c.get("custom_observables", o)
        try:
            re.compile(config['customObservables'][o])
        except re.error:
            log.error('Regular expression "%s" is invalid.' % config['customObservables'][o])
            sys.exit(1)

    # Issue a warning of both tasks & template are defined!
    if len(config['caseTasks']) > 0 and config['caseTemplate'] != '':
        log.warning('Both case template and tasks are defined. Template (%s) will be used.' % config['caseTemplate'])

    # New alert config
    config['alertTLP']          = c.get('alert', 'tlp')
    config['alertTags']         = c.get('alert', 'tags').split(',')
    if c.has_option('alert', 'keywords'):
        config['alertKeywords'] = c.get('alert', 'keywords')
    # Validate the keywords regex
    try:
        re.compile(config['alertKeywords'])
    except re.error:
        log.error('Regular expression "%s" is invalid.' % config['alertKeywords'])
        sys.exit(1)

    # Validate whitelists
    config['whitelists'] = loadWhitelists(config['thehiveWhitelists'])

'''
Main application handler.
'''
def main():
    global config
    global whitelists

    # Load and parse config files...
    loadConfig()

    # Connect to the IMAP Server, check for new mails and handle them...
    log.info('Processing %s@%s:%d/%s' % (config['imapUser'], config['imapHost'], config['imapPort'], config['imapFolder']))
    mailFetcher.init( config, log )
    mailFetcher.readMail(
        mailFetcher.mailConnect()
    )
    return

if __name__ == 'imap2thehive':
    main()
    sys.exit(0)
