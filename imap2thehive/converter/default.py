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
    esCaseId = theHiveConnector.searchCaseWithCaseIdInSubject( subject )
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
            log.debug("%s.convertMailToTheHive()::No 'communication-task' named %s found => creating one." % (__name__, tasknameCommunication))
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
        CREATE a new Case or Alert
        '''

        '''
        Search for interesting keywords in the email subject
        to decide if to create an Case OR an Alert.
        '''
        log.debug("%s.convertMailToTheHive()::Searching for '%s' in '%s'" % (__name__, config['alertKeywords'], subject))
        if config['alertKeywords'] == "ALERTS_ONLY" or re.search(config['alertKeywords'], subject, flags=0):
            '''
            CREATE an ALERT
            '''
            artifacts = []

            # Prepare AlertArtifacts from all found observables
            if config['thehiveObservables'] and len(observables) > 0:
                for o in observables:
                    log.debug("%s.convertMailToTheHive()::Adding 'observable' as AlertArtifact '%s'..." % (__name__, o))
                    artifacts.append(
                        theHiveConnector.craftAlertArtifact(
                            dataType=o['type'],
                            data=o['value']
                        )
                    )

            # Prepare AlertArtifacts from all found email attachments
            if config['thehiveObservables'] and len(attachments) > 0:
                for path in attachments:
                    log.debug("%s, convertMailToTheHive()::Adding 'attachment' as AlertArtifact '%s'..." % (__name__, path))
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
                log.info('%s.convertMailToTheHive()::Created alert.' % __name__)
            else:
                log.error('%s.convertMailToTheHive()::Could not create alert.' % __name__)
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
                            #@TODO customFields = customFields
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
                            #@TODO customFields = customFields
                        )

            # Create the case
            case = theHiveConnector.createCase( craftedCase )
            if case:
                esCaseId = case.id
                log.info('%s.convertMailToTheHive()::Created esCaseId %s' % (__name__, esCaseId))
                caseId = case.caseId
                log.info('%s.convertMailToTheHive()::Created caseId %s' % (__name__, caseId))

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
                            log.info('%s.convertMailToTheHive()::Added attachment "%s" as an observable to case ID %s' % (__name__, path, esCaseId))
                        else:
                            log.warning('%s.convertMailToTheHive()::Could not add attachment "%s" as an observable to case ID %s' % (__name__, path, esCaseId))

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
                            log.info('%s.convertMailToTheHive()::Added observable %s: %s to case ID %s' % (__name__, o['type'], o['value'], esCaseId))
                        else:
                            log.warning('%s.convertMailToTheHive()::Could not add observable %s: %s to case ID %s' % (__name__, o['type'], o['value'], esCaseId))

            else:
                log.error('%s.convertMailToTheHive()::Cannot create case: %s (%s)' % (__name__, response.status_code, response.text))
                return False

    return True
