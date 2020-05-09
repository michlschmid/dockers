import os

from TheHiveConnector import TheHiveConnector



def addAttachmentsToTaskLog(
        taskId,
        attachments
    ):
    # Append all "email attachments" as TaskLogs to the Communication task
    if len(attachments) > 0:
        for path in attachments:
            craftedTaskLog = theHiveConnector.craftTaskLog(
                    message = "Email attachment",
                    file    = path
                )
            if theHiveConnector.createTaskLog( taskId, craftedTaskLog ):
                log.info('Added attachment "%s" as TaskLog to Task: %s' % (path, taskId))
            else:
                log.warning('Could not add attachment "%s" as Tasklog to Task: %s' % (path, taskId))

            # Remove temp file of attachment from disk
            os.unlink( path )

def addObservablesToCase(
        esCaseId,
        observables
    ):
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
