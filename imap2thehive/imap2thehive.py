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
import logging
import logging.config
import argparse
import configparser
import os,sys
import tempfile
import re

import click

import mailFetcher

__author__     = "Xavier Mertens"
__license__    = "GPLv3"
__version__    = "1.0.7"
__maintainer__ = "Xavier Mertens"
__email__      = "xavier@rootshell.be"
__name__       = "imap2thehive"

log = logging.getLogger(__name__)

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
    'customObservables'  : {},
    'customAttachments'  : {
        'attachOriginalEmail' : False
    }
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
        log.error('%s.loadWhitelists()::Cannot read %s: %s' % (__name__, filename, e.strerror))
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
                log.error('%s.loadWhitelists()::Line %d: Regular expression "%s" is invalid.' % (__name__, l, f))
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
    parser.add_argument('-t', '--test',
        action = 'store_true',
        dest = 'test',
        help = 'use "local test emails" (in *.eml format). Files need to be placed in ./test-emails/',
        default = False)
    args = parser.parse_args()

    # Default values
    if not args.configFile:
        args.configFile = '/etc/imap2thehive.conf'
    if not args.verbose:
        args.verbose = False
    if not args.test:
        args.test = False

    if not os.path.isfile(args.configFile):
        log.error('%s.loadConfig()::Configuration file %s is not readable.' % (__name__, args.configFile))
        sys.exit(1);

    try:
        c = configparser.ConfigParser()
        c.read(args.configFile)
    except OSError as e:
        log.error('%s.loadConfig()::Cannot read config file %s: %s' % (__name__, args.configFile, e.errno))
        sys.exit(1)


    if args.verbose:
        # Click Fancy Colored
        logging.basicConfig(
            level=logging.DEBUG,
            format="".join((
                click.style("[%(asctime)s]", "yellow"),
                click.style("[%(levelname)-7s]", "green"),
                " %(message)s",
            ))
        )
    else:
        logging.basicConfig(
            filemode="w",
            filename="imap2thehive.log",
            level=logging.INFO,
            format="[%(asctime)s][%(levelname)s] %(message)s"
        )

    log = logging.getLogger(__name__)

    config['testmode']          = False
    if args.test == True:
        config['testmode']      = True

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
            log.error('%s.loadConfig()::Regular expression "%s" is invalid.' % (__name__, config['imapSpam']))
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
    log.info('%s.loadConfig()::config[mailHandlers]: %s' % (__name__, config['mailHandlers']))

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

    # Get custom "observable" options if any
    for o in c.options("custom_observables"):
        # Validate the regex
        config['customObservables'][o] = c.get("custom_observables", o)
        try:
            re.compile(config['customObservables'][o])
        except re.error:
            log.error('%s.loadConfig()::Regular expression "%s" is invalid.' % (__name__, config['customObservables'][o]))
            sys.exit(1)

    # Get custom "attachment" options if any
    if c.has_option('custom_attachments', 'attachOriginalEmail'):
        value = c.get('custom_attachments', 'attachOriginalEmail')
        if value == '1' or value == 'true' or value == 'yes':
            config['customAttachments']['attachOriginalEmail'] = True

    # Issue a warning of both tasks & template are defined!
    if len(config['caseTasks']) > 0 and config['caseTemplate'] != '':
        log.warning('%s.loadConfig()::Both case template and tasks are defined. Template (%s) will be used.' % (__name__, config['caseTemplate']))

    # New alert config
    config['alertTLP']          = c.get('alert', 'tlp')
    config['alertTags']         = c.get('alert', 'tags').split(',')
    if c.has_option('alert', 'keywords'):
        config['alertKeywords'] = c.get('alert', 'keywords')
    # Validate the keywords regex
    try:
        re.compile(config['alertKeywords'])
    except re.error:
        log.error('%s.loadConfig()::Regular expression "%s" is invalid.' % (__name__, config['alertKeywords']))
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

    mailFetcher.init( config )

    if config['testmode'] == False:
        # Connect to the IMAP Server, check for new mails and handle them...
        log.info('%s.main()::Processing %s@%s:%d/%s' % (__name__, config['imapUser'], config['imapHost'], config['imapPort'], config['imapFolder']))
        mailFetcher.readAndProcessEmailsFromMailbox(
            mailFetcher.connectToMailbox()
        )

    else:
        # Fetch emails from *.eml files from local "test-emails" folder.
        log.info('%s.main()::Processing !! TEST FILES !!' % (__name__))
        mailFetcher.readAndProcessEmailsFromTestFolder()

    return

if __name__ == 'imap2thehive':
    main()
    sys.exit(0)
