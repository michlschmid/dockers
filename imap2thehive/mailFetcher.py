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
        log.error("Cannot connect to IMAP server %s: %s" % (config['imapHost'],str(val)))
        mbox = None
        return

    try:
        typ,dat = mbox.login(config['imapUser'],config['imapPassword'])
    except:
        typ,dat = sys.exc_info()[:2]

    if typ != 'OK':
        log.error("Cannot open %s for %s@%s: %s" % (config['imapFolder'], config['imapUser'], config['imapHost'], str(dat)))
        mbox = None
        return

    log.info('Connected to IMAP server.')

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
    log.info("%d unread messages to process" % newEmails)
    for num in dat[0].split():
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
                log.info("Message %d flagged as spam and skipped" % int(num))
                continue

        # Try to deliver this message to TheHive as case or observable...
        if mailParser.submitEmailToTheHive( message ) == True:
            # If message successfully processed, flag it as 'Deleted' otherwise restore the 'Unread' status
            if config['imapExpunge']:
                mbox.store(num, '+FLAGS', '\\Deleted')
                log.info("Message %d successfully processed and deleted" % int(num))
            else:
                log.info("Message %d successfully processed and flagged as read" % int(num))
        else:
            mbox.store(num, '-FLAGS', '\\Seen')
            log.warning("Message %d not processed and flagged as unread" % int(num))
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

    for fle in listing:
        if str.lower(fle[-3:])=="eml":
            fle = path + fle
            log.info("FLE: %s" % fle)

            message = email.message_from_file(open( fle ))

            # Try to deliver this message to TheHive as case or observable...
            mailParser.submitEmailToTheHive( message.encode() )

'''
Setup the module
'''
def init(configObj, logObj):
    global config
    global log
    config = configObj
    log = logObj

    mailParser.init(configObj, logObj)
