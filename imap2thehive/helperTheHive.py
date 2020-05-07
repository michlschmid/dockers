import os,sys
import email
import email.header
from email.parser import HeaderParser
import chardet
import tempfile
import re

import helperAlert
import helperCase

def slugify(s):
    '''
    Sanitize filenames
    Source: https://github.com/django/django/blob/master/django/utils/text.py
    '''
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)

def isWhitelisted(string):
    '''
    Check if the provided string matches one of the whitelist regexes
    '''
    global config
    found = False
    for w in config['whitelists']:
        if re.search(w, string, re.IGNORECASE):
            found = True
            break
    return found

def submitTheHive(message):

    '''
    Create a new case in TheHive based on the email
    Return 'TRUE' is successfully processed otherwise 'FALSE'
    '''

    global log

    # Decode email
    msg = email.message_from_bytes(message)
    decode = email.header.decode_header(msg['From'])[0]
    if decode[1] is not None:
        fromField = decode[0].decode(decode[1])
    else:
        fromField = str(decode[0])
    decode = email.header.decode_header(msg['Subject'])[0]
    if decode[1] is not None:
        subjectField = decode[0].decode(decode[1])
    else:
        subjectField = str(decode[0])
    log.info("From: %s Subject: %s" % (fromField, subjectField))

    attachments = []
    observables = []

    # Extract SMTP headers and search for observables
    parser = HeaderParser()
    headers = parser.parsestr(msg.as_string())
    headers_string = ''
    i = 0
    while  i < len(headers.keys()):
        headers_string = headers_string + headers.keys()[i] + ': ' + headers.values()[i] + '\n'
        i+=1
    # Temporary disabled
    # observables = helperCase.searchObservables(headers_string, observables)

    body = ''
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            try:
                body = part.get_payload(decode=True).decode()
            except UnicodeDecodeError:
                body = part.get_payload(decode=True).decode('ISO-8859-1')
            observables.extend( helperCase.searchObservables(body, observables) )
        elif part.get_content_type() == "text/html":
            try:
                html = part.get_payload(decode=True).decode()
            except UnicodeDecodeError:
                html = part.get_payload(decode=True).decode('ISO-8859-1')
            observables.extend( helperCase.searchObservables(html, observables) )
        else:
            # Extract MIME parts
            filename = part.get_filename()
            mimetype = part.get_content_type()
            if filename and mimetype:
                if mimetype in config['caseFiles'] or not config['caseFiles']:
                    log.info("Found attachment: %s (%s)" % (filename, mimetype))
                    # Decode the attachment and save it in a temporary file
                    charset = part.get_content_charset()
                    if charset is None:
                        charset = chardet.detect(bytes(part))['encoding']
                    # Get filename extension to not break TheHive analysers (see Github #11)
                    fname, fextension = os.path.splitext(filename)
                    fd, path = tempfile.mkstemp(prefix=slugify(fname) + "_", suffix=fextension)
                    try:
                        with os.fdopen(fd, 'w+b') as tmp:
                            tmp.write(part.get_payload(decode=1))
                        attachments.append(path)
                    except OSerror as e:
                        log.error("Cannot dump attachment to %s: %s" % (path,e.errno))
                        return False

    # Cleanup observables (remove duplicates)
    new_observables = []
    for o in observables:
        if not {'type': o['type'], 'value': o['value'] } in new_observables:
            # Is the observable whitelisted?
            if isWhitelisted(o['value']):
                log.debug('Skipping whitelisted observable: %s' % o['value'])
            else:
                new_observables.append({ 'type': o['type'], 'value': o['value'] })
                log.debug('Found observable %s: %s' % (o['type'], o['value']))
        else:
            log.info('Ignoring duplicate observable: %s' % o['value'])
    log.info("Removed duplicate observables: %d -> %d" % (len(observables), len(new_observables)))
    observables = new_observables

    # Apply custom email handling
    # Search for interesting keywords in subjectField for decision making whether to apply a custom converter workflow:
    customHandlerFlag = False
    for key in config['mailHandler']:
        log.debug("Searching for mailhandler '%s' in '%s'" % (key, subjectField))

        if (customHandlerFlag == False) and re.search(config['alertKeywords'], subjectField, flags=0):
            log.debug("Using custom mailhandler '%s' in '%s'" % (key, subjectField))
            customHandlerFlag = True
            # @DEV
            # import handler + Key as mailHandler

    # Use "default" handler if no specific handler was found
    if customHandlerFlag == False:
        import mailHandlerDefault as mailHandler

    # Start handler and convert email to TheHive
    mailHandler.init( config, log )
    mailHandler.convertMailToTheHive(
        subjectField,
        body,
        fromField,
        observables,
        attachments
    )

def init(configObj, logObj):
    global config
    global log
    config = configObj
    log = logObj

    helperCase.init(configObj, logObj)
    helperAlert.init(configObj, logObj)
