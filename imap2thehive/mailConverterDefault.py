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

    '''
    Default Workflow:

    1. Check whether there is an encoded ID to an existing Case specified within the Email subject.
    1. YES: => Update that case's observables and "Communication" task with a tasklog entry of the email content.
    1. NO:  =>  2. Check whether the email subject contains an "alert keyword"
                2. YES  => Create an Alert from that Email and append all Attachments as Alert Artifacts (=Observables).
                2. NO   => Create a new Case from that Email and append all Attachments as Observables.
    '''

    # Check if this email belongs to an existing case...
    esCaseId = theHiveConnector.searchCaseBySubject( subject )
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
        CREATE a new Case or Alert
        '''

        '''
        Search for interesting keywords in the email subject
        to decide if to create an Case OR an Alert.
        '''
        log.debug("Searching for '%s' in '%s'" % (config['alertKeywords'], subject))
        if config['alertKeywords'] == "ALERTS_ONLY" or re.search(config['alertKeywords'], subject, flags=0):
            '''
            CREATE an ALERT
            '''
            artifacts = []

            # Prepare AlertArtifacts from all found observables
            if config['thehiveObservables'] and len(observables) > 0:
                for o in observables:
                    log.debug("Adding 'observable' as AlertArtifact '%s'..." % o)
                    artifacts.append(
                        theHiveConnector.craftAlertArtifact(
                            dataType=o['type'],
                            data=o['value']
                        )
                    )

            # Prepare AlertArtifacts from all found email attachments
            if config['thehiveObservables'] and len(attachments) > 0:
                for path in attachments:
                    log.debug("Adding 'attachment' as AlertArtifact '%s'..." % path)
                    artifacts.append(
                        theHiveConnector.craftAlertArtifact(
                        dataType='file',
                        data    = path,
                        message = 'Found as email attachment',
                        tlp     = int(config['alertTLP']),
                        ioc     = False,
                        tags    = config['caseTags'].append("attachment")
                        )
                    )

            # Prepare Tags for the Alert
            tags = list(config['alertTags'])
            # Add the matching/triggering "alert keywords"
            # to the list of tags as well
            match = re.findall(config['alertKeywords'], subject)
            for m in match:
                tags.append(m)

            # Prepare the alert
            sourceRef = str(uuid.uuid4())[0:6]
            craftedAlert = theHiveConnector.craftAlert(
                        title       = subject.replace('[ALERT]', ''),
                        tlp         = int(config['alertTLP']),
                        tags        = tags,
                        description = mdBody,
                        date        = emailDate,
                        type        = 'email',
                        source      = fromField,
                        sourceRef   = sourceRef,
                        artifacts   = artifacts
                        )

            # Create the Alert
            alert = theHiveConnector.createAlert( craftedAlert )

            # Delete temp attachment files anyway
            if len(attachments) > 0:
                for path in attachments:
                    os.unlink( path )

            if alert:
                log.info('Created alert.' )
            else:
                log.error('Could not create alert.')
                return False

        else:
            '''
            CREATE a CASE
            '''

            '''
            # Prepare the custom fields
            customFields = CustomFieldHelper()\
                .add_string('from', fromField)\
                .add_string('attachment', str(attachments))\
                .build()
            '''

            # If a case template is specified in the config
            # then use it instead of the tasks given in the config
            if len(config['caseTemplate']) > 0:
                craftedCase = theHiveConnector.craftCase(
                            title        = subject,
                            tlp          = int(config['caseTLP']), 
                            flag         = False,
                            tags         = config['caseTags'],
                            description  = mdBody,
                            template     = config['caseTemplate'],
                            #@DEV customFields = customFields
                        )
            else:
                # Prepare the Case's "tasks"
                tasks = []
                for task in config['caseTasks']:
                    tasks.append( theHiveConnector.craftTask(title=task) )

                craftedCase = theHiveConnector.craftCase(title        = subject,
                            tlp          = int(config['caseTLP']), 
                            flag         = False,
                            tags         = config['caseTags'],
                            description  = mdBody,
                            tasks        = tasks,
                            #@DEV customFields = customFields
                        )

            # Create the case
            case = theHiveConnector.createCase( craftedCase )
            if case:
                esCaseId = case.id
                log.info('Created esCaseId %s' % esCaseId)
                caseId = case.caseId
                log.info('Created caseId %s' % caseId)

                # Add all mail attachments as observables to the case
                if len(attachments) > 0:
                    for path in attachments:
                        craftedObservable = theHiveConnector.craftCaseObservable(
                            dataType='file',
                            data    = [path],
                            tlp     = int(config['caseTLP']),
                            ioc     = False,
                            tags    = config['caseTags'],
                            message = 'Found as email attachment'
                            )
                        if theHiveConnector.createCaseObservable( esCaseId, craftedObservable ):
                            log.info('Added attachment "%s" as an observable to case ID %s' % (path, esCaseId))
                        else:
                            log.warning('Could not add attachment "%s" as an observable to case ID %s' % (path, esCaseId))

                        # Delete temp attachment files anyway
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
                log.error('Cannot create case: %s (%s)' % (response.status_code, response.text))
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

    theHiveConnector = TheHiveConnector( configObj, logObj )
    mailConverterHelper.init( configObj, logObj )
