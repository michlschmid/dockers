import os,sys
import re
import uuid

from TheHiveConnector import TheHiveConnector



'''
Converts an emails contents to according TheHive contents.
'''
def convertMailToTheHive(
        subject,
        body,
        fromField,
        observables,
        attachments
    ):

    tasknameCommunication = "Communication"
    tasknameInvestigation = "Investigation"


    """
    Workflow for BSI Emails:
    * Always create a Case
    * Tasks:
     * Communication
     * Investigation
    * Add Attachments as TaskLogs to Communication
    """

    # Check if this email belongs to an existing case...
    if theHiveConnector.searchCaseBySubject( subject ) != None :
        '''
        UPDATE the existing case
        '''

    else:
        '''
        CREATE a new case
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

        # ...and now "create" the Case
        id = None
        case = theHiveConnector.createCase( craftedCase )
        if case:
            log.info("Created case: %s" % dir(case))
            esCaseId = case.id
            log.info('Created esCaseId %s' % esCaseId)
            caseId = case.caseId
            log.info('Created caseId %s' % caseId)

            # Get the Communication task's generated id
            communicationTaskId = theHiveConnector.getTaskIdByTitle( esCaseId, tasknameCommunication )
            log.info('Found communicationTaskId %s' % communicationTaskId)
            if communicationTaskId:
                # Append all "email attachments" as TaskLogs to the Communication task
                if len(attachments) > 0:
                    for path in attachments:
                        craftedTaskLog = theHiveConnector.craftTaskLog(
                                message = "Email attachment",
                                file    = path
                            )
                        if theHiveConnector.createTaskLog( communicationTaskId, craftedTaskLog ):
                            log.info('Added attachment "%s" as TaskLog to Task: %s' % (path, communicationTaskId))
                        else:
                            log.warning('Could not add attachment "%s" as Tasklog to Task: %s' % (path, communicationTaskId))

                        # Remove temp file of attachment from disk
                        os.unlink( path )
            
            # Add all observables found in the mail body to the case
            if config['thehiveObservables'] and len(observables) > 0:
                for o in observables:
                    craftedObservable = theHiveConnector.craftCaseObservable(
                        dataType = o['type'],
                        data     = o['value'],
                        tlp      = int(config['caseTLP']),
                        ioc      = False,
                        tags     = config['caseTags'],
                        message  = 'Found in the email body'
                        )
                    if theHiveConnector.createCaseObservable( esCaseId, craftedObservable ):
                        log.info('Added observable %s: %s to case ID %s' % (o['type'], o['value'], esCaseId))
                    else:
                        log.warning('Could not add observable %s: %s to case ID %s' % (o['type'], o['value'], esCaseId))

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
