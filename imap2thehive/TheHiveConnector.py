
import re

try:
    from thehive4py.api import TheHiveApi
    from thehive4py.models import Case, CaseTask, CaseTaskLog, CaseObservable
    from thehive4py.models import Alert, AlertArtifact
    from thehive4py.query import Eq
except:
    self.log.error("Please install thehive4py.")
    sys.exit(1)

class TheHiveConnector:
    'TheHive connector'

    '''
    BASIC SETUP and THE HIVE Connection establishing
    '''

    '''
    Setup the module
    '''
    def __init__(self, configObj, logObj):
        self.config = configObj
        self.log = logObj

        self.theHiveApi = self.connect()

    '''
    Connect to the TheHive server
    '''
    def connect(self):
        self.log.info('%s.connect starts', __name__)
        return TheHiveApi( self.config['thehiveURL'], self.config['thehiveApiKey'] )



    '''
    CASEs related
    '''
    def craftCase(self, **attributes):
        self.log.info('%s.craftCase starts', __name__)
        case = Case( **attributes )
        return case

    def createCase(self, case):
        self.log.info('%s.createCase starts', __name__)

        response = self.theHiveApi.create_case(case)

        if response.status_code == 201:
            esCaseId =  response.json()['id']
            createdCase = self.theHiveApi.case(esCaseId)
            return createdCase
        else:
            self.log.error('Case creation failed')
            raise ValueError(json.dumps(response.json(), indent=4, sort_keys=True))



    '''
    CASE TASKs related
    '''
    def craftTask(self, **attributes):
        self.log.info('%s.craftTask starts', __name__)
        commTask = CaseTask( **attributes )
        return commTask

    def craftTaskCommunication(self):
        self.log.info('%s.craftTaskCommunication starts', __name__)

        commTask = CaseTask(title='Communication',
            status='InProgress',
            owner='synapse')

        return commTask

    def createTask(self, esCaseId, task):
        self.log.info('%s.createTask starts', __name__)

        response = self.theHiveApi.create_case_task(esCaseId, task)

        if response.status_code == 201:
            esCreatedTaskId = response.json()['id']
            return esCreatedTaskId
        else:
            self.log.error('Task creation failed')
            raise ValueError(json.dumps(response.json(), indent=4, sort_keys=True))

    def getTaskIdByTitle(self, esCaseId, taskTitle):
        self.log.info('%s.getTaskIdByName starts esCaseId:%s, taskTitle:%s', __name__, esCaseId, taskTitle)

        response = self.theHiveApi.get_case_tasks(esCaseId)
        for task in response.json():
            if task['title'] == taskTitle:
                return task['id']

        #no <taskTitle> found
        return None



    '''
    CASE TASK LOG related
    '''
    def craftTaskLog(self, **attributes):
        self.log.info('%s.craftTaskLog starts', __name__)
        log = CaseTaskLog( **attributes )
        return log

    def createTaskLog(self, esTaskId, taskLog):
        self.log.info('%s.createTaskLog starts', __name__)

        response = self.theHiveApi.create_task_log(esTaskId, taskLog)

        if response.status_code == 201:
            esCreatedTaskLogId = response.json()['id']
            return esCreatedTaskLogId
        else:
            self.log.error('Task log creation failed')
            raise ValueError(json.dumps(response.json(), indent=4, sort_keys=True))



    '''
    CASE OBSERVABLE related
    '''
    def craftCaseObservable(self, **attributes):
        self.log.info('%s.craftCaseObservable starts', __name__)
        file_observable = CaseObservable( **attributes )
        return file_observable

    def createCaseObservable(self, esCaseId, observable):
        self.log.info('%s.createCaseObservable starts', __name__)
        response = self.theHiveApi.create_case_observable(
            esCaseId, observable)

        if response.status_code == 201:
            esObservableId = response.json()
            return esObservableId
        else:
            self.log.error('Case observable creation failed')
            raise ValueError(json.dumps(response.json(), indent=4, sort_keys=True))



    '''
    ALERT related
    '''
    def craftAlert(self, **attributes):
        self.log.info('%s.craftAlert starts', __name__)
        alert = Alert( **attributes )
        return alert

    def createAlert(self, alert):
        self.log.info('%s.createAlert starts', __name__)

        response = self.theHiveApi.create_alert( alert )

        if response.status_code == 201:
            return response.json()
        else:
            self.log.error('Alert creation failed')
            raise ValueError(json.dumps(response.json(), indent=4, sort_keys=True))

    def findAlert(self, q):
        """
            Search for alerts in TheHive for a given query

            :param q: TheHive query
            :type q: dict

            :return results: list of dict, each dict describes an alert
            :rtype results: list
        """
        self.log.info('%s.findAlert starts', __name__)
        response = self.theHiveApi.find_alerts(query=q)
        if response.status_code == 200:
            results = response.json()
            return results
        else:
            self.log.error('findAlert failed')
            raise ValueError(json.dumps(response.json(), indent=4, sort_keys=True))



    '''
    ALERT ARTIFACT related
    '''
    def craftAlertArtifact(self, **attributes):
        self.log.info('%s.craftAlertArtifact dataType: %s', __name__, attributes['dataType'])
        alertArtifact = AlertArtifact( **attributes )
        #self.log.info('%s.craftAlertArtifact data: %s', __name__, alertArtifact.data)
        return alertArtifact



    '''
    SEARCHes / LOOKUPs
    '''

    '''
    Search for an existing case by scanning a
    given mail subject for an encoded "CaseId"
    via RegEx search.
    '''
    def searchCaseBySubject(self, subject):
        #search case with a specific regex string in 'subject'
        #returns the ES case ID

        self.log.info('searchCaseByDescription starts: %s', __name__)
        self.log.info('searchCaseByDescription subject: %s', subject)
        self.log.info('searchCaseByDescription config[subjectCaseIdEncodingRegEx]: %s', self.config['subjectCaseIdEncodingRegEx'])

        try:
            regex = re.compile( self.config['subjectCaseIdEncodingRegEx'], re.IGNORECASE )
            # take first regex result
            # get number part (after '#')
            # remove trailing ')'
            caseId  = regex.findall( subject )[0]
            caseId  = caseId.split("#")[1]
            caseId  = str( caseId )[:-1]
            self.log.info('searchCaseByDescription caseId: %s', caseId)

            query = dict()
            query['_string'] = 'caseId:"{}"'.format(caseId)
            range = 'all'
            sort = []
            response = self.theHiveApi.find_cases(query=query, range=range, sort=sort)

            if response.status_code != 200:
                error = dict()
                error['message'] = 'get case failed'
                error['case_id'] = caseId
                error['payload'] = response.json()
                self.log.error('Query to TheHive API did not return 200')
                raise ValueError(json.dumps(error, indent=4, sort_keys=True))

            if len(response.json()) == 1:
                #one case matched
                esCaseId = response.json()[0]['id']
                self.log.info('searchCaseByDescription found esCaseId: %s', esCaseId)
                return esCaseId
            elif len(response.json()) == 0:
                #no case matched
                return None
            else:
                #unknown use case
                raise ValueError('unknown use case after searching case by description')

        except Exception as e:
            self.log.info('Failed to find case by subject', exc_info=True)
            return None
        
    """
    TheHive "TLP" => integer mapping
    0: white
    1: green
    2: amber
    3: red

    Source: https://github.com/TheHive-Project/TheHiveDocs/blob/master/api/alert.md
    """
    def tlpStringToInt(tlpString):
        switch = {
            "white": 0,
            "green": 1,
            "amber": 2,
            "red": 3
        }
        return switch.get( str(tlpString).lower(), 2 )
