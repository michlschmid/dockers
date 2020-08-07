import os,sys
import re
import uuid

from TheHiveConnector import TheHiveConnector
import mailConverterHelper



'''
Converts an emails contents to according TheHive contents.
'''
def convertMailToTheHive(
        subject,
        body,
        mdBody,
        emailDate,
        fromField,
        observables,
        attachments
    ):

    tasknameCommunication = "Communication"
    tasknameInvestigation = "Investigation"


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
            log.debug("No Task named %s found => creating one." % tasknameCommunication)
            craftedTask = theHiveConnector.craftTask( title=tasknameCommunication )
            communicationTaskId = theHiveConnector.createTask(esCaseId, craftedTask)

        # Add Email as TaskLog to the Communication task
        craftedTaskLog = theHiveConnector.craftTaskLog( message=mdBody)
        taskLogId = theHiveConnector.createTaskLog(communicationTaskId, craftedTaskLog)

        # Add Attachments to TaskLog
        mailConverterHelper.addAttachmentsToTaskLog( communicationTaskId, attachments )

        # Add Observables to Case
        mailConverterHelper.addObservablesToCase( esCaseId, observables )

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
        log.info('Parsed TLP string from subject: %s', parsedTlpString)        
        tlp = TheHiveConnector.tlpStringToInt( parsedTlpString )
        log.info('Converted TLP to TheHive TLP-int: %s', tlp)

        # Bring it together as a new Case...
        craftedCase = theHiveConnector.craftCase(
                title        = subject,
                tlp          = tlp,
                flag         = False,
                tags         = config['caseTags'],
                description  = body,
                tasks        = craftedTasks,
                #@DEV customFields = customFields
            )

        # ...and now create the Case
        case = theHiveConnector.createCase( craftedCase )
        if case:
            esCaseId = case.id
            log.info('Created esCaseId %s' % esCaseId)
            caseId = case.caseId
            log.info('Created caseId %s' % caseId)

            # Get the Communication task's generated id
            communicationTaskId = theHiveConnector.getTaskIdByTitle( esCaseId, tasknameCommunication )
            log.info('Found communicationTaskId %s' % communicationTaskId)
            if communicationTaskId:
                # Append all "email attachments" as TaskLogs to the Communication task
                mailConverterHelper.addAttachmentsToTaskLog( communicationTaskId, attachments )

            # Add all observables found in the mail body to the case
            mailConverterHelper.addObservablesToCase( esCaseId, observables )

        else:
            log.error('Could not create case.')
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
    log.info('extractBsiCswNrFromString got string: %s' % string)
    parsedString = re.search( "(?<=\]\ )(\w+)-(\w+)-(\w+)", string, flags=0)
    log.info('extractBsiCswNrFromString got values: %s', ', '.join(parsedString))        

    bsiCswNr = parsedString[0]+"-"+parsedString[1]
    log.info('extractBsiCswNrFromString built bsiCswNr: %s', bsiCswNr)
    return bsiCswNr



"""
Tries to find an existing Case with the
given BSI CSW number in its title.

If it finds a match it returns the according
internal esCaseId.
"""
def searchCaseByBsiCswNr( bsiCswNr ):
    log.info('searchCaseByBsiCswNr got bsiCswNr: %s' % bsiCswNr)
    return None



'''
Setup the module
'''
def init(configObj, logObj):
    global config
    global log
    global theHiveConnector

    config = configObj
    log = logObj

    theHiveConnector = TheHiveConnector(configObj, logObj)
    mailConverterHelper.init( configObj, logObj )
