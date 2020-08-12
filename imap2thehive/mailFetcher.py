import os,sys
import imaplib
import logging
import logging.config
import re
import mailParser
import email

'''
Connection to mailserver and handle the IMAP connection
'''
def connectToMailbox():
    try:
        if config['imapPort'] == 993:
            mbox = imaplib.IMAP4_SSL(config['imapHost'], config['imapPort'])
        else:
            mbox = imaplib.IMAP4(config['imapHost'], config['imapPort'])
    except:
        typ,val = sys.exc_info()[:2]
        log.error("%s.connectToMailbox()::Cannot connect to IMAP server %s: %s" % (__name__, config['imapHost'],str(val)))
        mbox = None
        return

    try:
        typ,dat = mbox.login(config['imapUser'],config['imapPassword'])
    except:
        typ,dat = sys.exc_info()[:2]

    if typ != 'OK':
        log.error("%s.connectToMailbox()::Cannot open %s for %s@%s: %s" % (__name__, config['imapFolder'], config['imapUser'], config['imapHost'], str(dat)))
        mbox = None
        return

    log.info('%s.connectToMailbox()::Connected to IMAP server.' % __name__)

    return mbox

'''
Reads all unread emails from the specfied MAILBOX folder
 * fetches 
 * processes
 * converts
and forwards them to TheHive.
'''
def readAndProcessEmailsFromMailbox(mbox):
    global log

    if not mbox:
        return

    mbox.select(config['imapFolder'])
    # debug typ, dat = mbox.search(None, '(ALL)')
    typ, dat = mbox.search(None, '(UNSEEN)')
    newEmails = len(dat[0].split())
    log.info("%s.readAndProcessEmailsFromMailbox()::Found '%d' unread messages to process" % (__name__, newEmails))
    for num in dat[0].split():
        log.info("\n\n%s.readAndProcessEmailsFromMailbox()::Processing message '%d'..." % (__name__, int(num)))

        typ, dat = mbox.fetch(num, '(RFC822)')
        if typ != 'OK':
            error(dat[-1])
        message = dat[0][1]

        """
        @DEV: Ability to "REUSE" TEST-EMAILs over and over and over again... ;-)
        #mbox.store(num, '-FLAGS', '\\Seen')
        """

        # Ignore messages matching the spam regex if present
        if len(config['imapSpam']) > 0:
            if re.match(config['imapSpam'], message.decode('utf-8'), flags=0):
                log.info("%s.readAndProcessEmailsFromMailbox()::Message '%d' flagged as spam and skipped" % (__name__, int(num)))
                continue

        # Try to deliver this message to TheHive as case or observable...
        messageObj = email.message_from_bytes(message)

        if mailParser.submitEmailToTheHive( messageObj ) == True:
            # If message successfully processed, flag it as 'Deleted' otherwise restore the 'Unread' status
            if config['imapExpunge']:
                mbox.store(num, '+FLAGS', '\\Deleted')
                log.info("%s.readAndProcessEmailsFromMailbox()::Message '%d' successfully processed and deleted" % (__name__, int(num)))
            else:
                log.info("%s.readAndProcessEmailsFromMailbox()::Message '%d' successfully processed and flagged as read" % (__name__, int(num)))
        else:
            mbox.store(num, '-FLAGS', '\\Seen')
            log.warning("%s.readAndProcessEmailsFromMailbox()::Message '%d' not processed and flagged as unread" % (__name__, int(num)))
    mbox.expunge() 
    return newEmails

'''
Reads all *.eml email files from the specfied "test email" folder
 * fetches 
 * processes
 * converts
and forwards them to TheHive.
'''
def readAndProcessEmailsFromTestFolder():
    global log

    path = './test-emails/'
    listing = os.listdir(path)

    i = 0
    for fle in listing:
        log.info("\n\n%s.readAndProcessEmailsFromTestFolder()::Processing file '%d'..." % (__name__, int(i)))
        if str.lower(fle[-3:])=="eml":
            fle = path + fle
            log.info("%s.readAndProcessEmailsFromTestFolder()::Processing FLE: %s as email file..." % (__name__, fle))

            messageObj = email.message_from_file(open( fle ))

            # Try to deliver this message to TheHive as case or observable...
            mailParser.submitEmailToTheHive( messageObj )

        else:
            log.info("%s.readAndProcessEmailsFromTestFolder()::Dropping FLE: %s as it doesn't look like an email file." % (__name__, fle))

        i = i + 1


'''
Setup the module
'''
def init(configObj, logObj):
    global config
    global log
    config = configObj
    log = logObj

    mailParser.init(configObj, logObj)
