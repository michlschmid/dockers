import os,sys
import re
import uuid

try:
    from thehive4py.api import TheHiveApi
    from thehive4py.models import Case, CaseTask, CaseObservable, CustomFieldHelper
    from thehive4py.models import Alert, AlertArtifact
except:
    log.error("Please install thehive4py.")
    sys.exit(1)


#
# Converts an emails contents to according TheHive contents.
#
def convertMailToTheHive(
        subjectField,
        body,
        fromField,
        observables,
        attachments
    ):

    # Initialize TheHiveApi
    api = TheHiveApi( config['thehiveURL'], config['thehiveApiKey'] )

    # Search for interesting keywords in subjectField for decision making whether to create a case or an alert:
    log.debug("Searching for '%s' in '%s'" % (config['alertKeywords'], subjectField))
    if re.search(config['alertKeywords'], subjectField, flags=0):
        #
        # Add AlertArtifacts from observables and attachments found in the email
        #
        artifacts = []
        if config['thehiveObservables'] and len(observables) > 0:
            #
            # Add found observables
            #
            for o in observables:
                log.debug("Adding 'observable' as AlertArtifact '%s'..." % o)
                artifacts.append(
                    AlertArtifact(
                        dataType=o['type'],
                        data=o['value']
                    )
                )

        if config['thehiveObservables'] and len(attachments) > 0:
            #
            # Add found attachments
            #
            for path in attachments:
                log.debug("Adding 'attachment' as AlertArtifact '%s'..." % path)
                artifacts.append(
                    AlertArtifact(
                    dataType='file',
                    data    = path,
                    message = 'Found as email attachment',
                    tlp     = int(config['alertTLP']),
                    ioc     = False,
                    tags    = config['caseTags'].append("attachment")
                    )
                )

        #
        # Prepare tags - add alert keywords found to the list of tags
        #
        tags = list(config['alertTags'])
        match = re.findall(config['alertKeywords'], subjectField)
        for m in match:
            tags.append(m)

        #
        # Prepare the alert
        #
        sourceRef = str(uuid.uuid4())[0:6]
        alert = Alert(title=subjectField.replace('[ALERT]', ''),
                      tlp         = int(config['alertTLP']),
                      tags        = tags,
                      description = body,
                      type        = 'email',
                      source      = fromField,
                      sourceRef   = sourceRef,
                      artifacts   = artifacts
                    )

        # Create the Alert
        id = None
        response = api.create_alert(alert)
        if response.status_code == 201:
            log.info('Created alert %s' % response.json()['sourceRef'])
            # Delete temp attachment files
            if len(attachments) > 0:
                for path in attachments:
                    os.unlink( path )
        else:
            log.error('Cannot create alert: %s (%s)' % (response.status_code, response.text))
            return False

    else:
        # Prepare the sample case
        tasks = []
        for task in config['caseTasks']:
             tasks.append(CaseTask(title=task))

        # Prepare the custom fields
        customFields = CustomFieldHelper()\
            .add_string('from', fromField)\
            .add_string('attachment', str(attachments))\
            .build()

        # If a case template is specified, use it instead of the tasks
        if len(config['caseTemplate']) > 0:
            case = Case(title=subjectField,
                        tlp          = int(config['caseTLP']), 
                        flag         = False,
                        tags         = config['caseTags'],
                        description  = body,
                        template     = config['caseTemplate'],
                        customFields = customFields)
        else:
            case = Case(title        = subjectField,
                        tlp          = int(config['caseTLP']), 
                        flag         = False,
                        tags         = config['caseTags'],
                        description  = body,
                        tasks        = tasks,
                        customFields = customFields)

        # Create the case
        id = None
        response = api.create_case(case)
        if response.status_code == 201:
            newID = response.json()['id']
            log.info('Created case %s' % response.json()['caseId'])
            if len(attachments) > 0:
                for path in attachments:
                    observable = CaseObservable(dataType='file',
                        data    = [path],
                        tlp     = int(config['caseTLP']),
                        ioc     = False,
                        tags    = config['caseTags'],
                        message = 'Found as email attachment'
                        )
                    response = api.create_case_observable(newID, observable)
                    if response.status_code == 201:
                        log.info('Added observable %s to case ID %s' % (path, newID))
                        os.unlink( path )
                    else:
                        log.warning('Cannot add observable: %s - %s (%s)' % (path, response.status_code, response.text))
            #
            # Add observables found in the mail body
            #
            if config['thehiveObservables'] and len(observables) > 0:
                for o in observables:
                    observable = CaseObservable(
                        dataType = o['type'],
                        data     = o['value'],
                        tlp      = int(config['caseTLP']),
                        ioc      = False,
                        tags     = config['caseTags'],
                        message  = 'Found in the email body'
                        )
                    response = api.create_case_observable(newID, observable)
                    if response.status_code == 201:
                        log.info('Added observable %s: %s to case ID %s' % (o['type'], o['value'], newID))
                    else:
                        log.warning('Cannot add observable %s: %s - %s (%s)' % (o['type'], o['value'], response.status_code, response.text))
        else:
            log.error('Cannot create case: %s (%s)' % (response.status_code, response.text))
            return False
    return True

def init(configObj, logObj):
    global config
    global log
    config = configObj
    log = logObj
