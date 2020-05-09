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
    if theHiveConnector.searchCaseBySubject( subject ) != None :
        '''
        UPDATE the existing case
        @TODO
        '''

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

        # Bring it together as a new Case...
        craftedCase = theHiveConnector.craftCase(
                title        = subject,
                tlp          = int(config['caseTLP']), 
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
