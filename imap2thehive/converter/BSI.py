import os,sys
import re
import uuid
import logging

from TheHiveConnector import TheHiveConnector

from . import helper

log = logging.getLogger(__name__)

'''
Converts an emails contents to according TheHive contents.
'''
def convertMailToTheHive(
        config,
        subject,
        body,
        mdBody,
        emailDate,
        fromField,
        observables,
        attachments
    ):

    theHiveConnector = TheHiveConnector( config )
    helper.init( config )

    tasknameCommunication = "Communication"
    tasknameInvestigation = "Investigation"

    '''
    Test if this email is approriate for this converter.
    '''
    # => We are searching for certain keywords in the subject line...
    if not re.search( "\[CSW_", subject ):
        return None

    '''
    YES - we're responsible for handling this message! ;-)
    '''
    log.debug("\n\n%s == convertMailToTheHive() parameter dump ==" % __name__)
    log.debug("%s.convertMailToTheHive()::subject:     %s" % (__name__, subject))
    log.debug("%s.convertMailToTheHive()::body:        %s" % (__name__, body))
    log.debug("%s.convertMailToTheHive()::mdBody:      %s" % (__name__, mdBody))
    log.debug("%s.convertMailToTheHive()::emailDate:   %s" % (__name__, emailDate))
    log.debug("%s.convertMailToTheHive()::fromField:   %s" % (__name__, fromField))
    log.debug("%s.convertMailToTheHive()::observables:" % __name__)
    for i in range(len(observables)):
        log.debug("{0}.convertMailToTheHive()::observable[{1}][{2}]:    {3}".format(__name__, i, observables[i]['type'], observables[i]['value']) )
    log.debug("%s.convertMailToTheHive()::attachments:" % __name__)
    for i in range(len(attachments)):
        log.debug("{0}.convertMailToTheHive()::attachment[{1}]: {2}".format(__name__, i, attachments[i]) )
    log.debug("%s == convertMailToTheHive() parameter dump ==\n\n" % __name__)


    """
    Workflow for BSI Emails:

    1. Check whether there is an encoded ID to an existing Case specified within the Email subject.
    1. YES: =>  Update that case's observables and "Communication" task with a tasklog entry of the email content and all it's attachments.
    1. NO:  =>  Create a new Case from that Email
                Add the following Tasks:
                 * Communication
                 * Investigation
                Finally append all email attachments as TaskLogs to the "Communication" task.
    """

    # Check if this email belongs to an existing case...
    esCaseId = searchCaseByBsiCswNr( extractBsiCswNrFromString( subject ) )
    if esCaseId != None :
        '''
        UPDATE the existing case
        '''
        communicationTaskId = theHiveConnector.getTaskIdByTitle( esCaseId, tasknameCommunication )

        if communicationTaskId != None:
            pass
        else:
            #case already exists but no Communication task found
            #creating comm task
            log.debug("%s.convertMailToTheHive()::No Task named %s found => creating one." % (__name__, tasknameCommunication))
            craftedTask = theHiveConnector.craftTask( title=tasknameCommunication )
            communicationTaskId = theHiveConnector.createTask(esCaseId, craftedTask)

        # Add Email as TaskLog to the Communication task
        craftedTaskLog = theHiveConnector.craftTaskLog( message=mdBody)
        taskLogId = theHiveConnector.createTaskLog(communicationTaskId, craftedTaskLog)

        # Add Attachments to TaskLog
        helper.addAttachmentsToTaskLog( communicationTaskId, attachments )

        # Add Observables to Case
        helper.addObservablesToCase( esCaseId, observables )

    else:
        '''
        CREATE a new Case
        '''

        '''
        # Prepare the Case's "custom fields"
        customFields = CustomFieldHelper()\
            .add_string('from', fromField)\
            .add_string('attachment', str(attachments))\
            .build()
        '''

        # Prepare the Case's "tasks"
        craftedTasks = []
        craftedTasks.append( theHiveConnector.craftTask(title=tasknameCommunication) )
        craftedTasks.append( theHiveConnector.craftTask(title=tasknameInvestigation) )

        # Parse TLP from email subject line
        parsedTlpString = re.search( "(?<=\[TLP\:)(\w+)", subject, flags=0)[0]
        log.info('%s.convertMailToTheHive()::Parsed TLP string from subject: %s' % (__name__, parsedTlpString))        
        tlp = TheHiveConnector.tlpStringToInt( parsedTlpString )
        log.info('%s.convertMailToTheHive()::Converted TLP to TheHive TLP-int: %s' % (__name__, tlp))

        # Bring it together as a new Case...
        craftedCase = theHiveConnector.craftCase(
                title        = subject,
                tlp          = tlp,
                flag         = False,
                tags         = config['caseTags'],
                description  = body,
                tasks        = craftedTasks,
                #@TODO customFields = customFields
            )

        # ...and now create the Case
        case = theHiveConnector.createCase( craftedCase )
        if case:
            esCaseId = case.id
            log.info('%s.convertMailToTheHive()::Created esCaseId %s' % (__name__, esCaseId))
            caseId = case.caseId
            log.info('%s.convertMailToTheHive()::Created caseId %s' % (__name__, caseId))

            # Get the Communication task's generated id
            communicationTaskId = theHiveConnector.getTaskIdByTitle( esCaseId, tasknameCommunication )
            log.info('%s.convertMailToTheHive()::Found communicationTaskId %s' % (__name__, communicationTaskId))
            if communicationTaskId:
                # Append all "email attachments" as TaskLogs to the Communication task
                helper.addAttachmentsToTaskLog( communicationTaskId, attachments )

            # Add all observables found in the mail body to the case
            helper.addObservablesToCase( esCaseId, observables )

        else:
            log.error('%s.convertMailToTheHive()::Could not create case.' % __name__)
            return False

    return True



"""
Tries to extract a BSI CSW number from a given string.
Usually the string is taken from an email subject line.

Example:
The following subject line:
* "WG: [CSW_gelb][TLP:GREEN][UPDATE] 2020-199324-11a3: Schwachstelle in ABB SECURITY System 800xA"
is converted to the following CSW number string:
* "2020-199324"

If it finds a match it returns the found CSW number string.
"""
def extractBsiCswNrFromString( string ):
    log.info('%s.extractBsiCswNrFromString()::Got string: "%s"' % (__name__, string))
    parsedString = re.search( "(?<=\]\ )(\w+)-(\w+)-(\w+)", string, flags=0)
#    log.info('%s.extractBsiCswNrFromString got values: %s' % (__name__, ', '.join(parsedString)))

    bsiCswNr = parsedString[0]+"-"+parsedString[1]
    log.info('%s.extractBsiCswNrFromString()::Built bsiCswNr: %s' % (__name__, bsiCswNr))
    return bsiCswNr



"""
Tries to find an existing Case with the
given BSI CSW number in its title.

If it finds a match it returns the according
internal esCaseId.
"""
def searchCaseByBsiCswNr( bsiCswNr ):
    log.info('%s.searchCaseByBsiCswNr()::Got bsiCswNr: %s' % (__name__, bsiCswNr))
    return None
