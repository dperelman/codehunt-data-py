import json
import requests
import time


class ExplorationTestCase(object):
    '''Wrapper for the test case part of an Exploration.'''

    def __init__(self, names, test_case):
        self._names = names
        # See https://api.codehunt.com/ for documentation on interface TestCase
        self.test_case = test_case
        # one of the following: "Failure", "Inconclusive", "Success"
        self.status = self.test_case['status']
        self.any_exception_or_path_bounds_exceeded =\
                self.test_case['anyExceptionOrPathBoundsExceeded']
        self.summary = self.test_case['summary']
        self.message = self.test_case['message']
        self.exception = self.test_case['exception']
        self.stack_trace = self.test_case['stackTrace']

        if names and test_case['values']:
            self.values_dict = dict(zip(names, test_case['values']))

            self.names = list(names) # copy names because we mutate it
            self.values = test_case['values']

            if 'EXPECTED RESULT' in self.values_dict:
                self.expected = self.values_dict['EXPECTED RESULT']
                del self.values_dict['EXPECTED RESULT']
                idx = self.names.index('EXPECTED RESULT')
                del self.names[idx]
                del self.values[idx]
            else:
                self.expected = None

            if 'YOUR RESULT' in self.values_dict:
                self.actual = self.values_dict['YOUR RESULT']
                del self.values_dict['YOUR RESULT']
                idx = self.names.index('YOUR RESULT')
                del self.names[idx]
                del self.values[idx]
            else:
                self.actual = None

            for name in self.names:
                if ' ' in name:
                    print(name)
        else:
            self.names = None
            self.values = None
            self.actual = None
            self.expected = None

            print(self.test_case)

    def __repr__(self):
        return "%s.%s(%s, %s)" % (type(self).__module__, type(self).__name__,
                                  repr(self._names), repr(self.test_case))

    def __str__(self):
        params = ', '.join(['%s=%s' % (param, value)
                            for (param, value)
                            in zip(self.names, self.values)])
        correct = 'Puzzle(%(params)s)%(expected)s' % {
                'params': params,
                'expected': ' = %s' % self.expected if self.expected else ''
                }
        if self.summary == 'Mismatch':
            return "%(summary)s: %(correct)s (code returned %(actual)s)" % {
                    'summary': self.summary,
                    'actual': self.actual,
                    'correct': correct,
                    }
        elif self.summary == '' and self.status == 'Success':
            return "Success: %(correct)s" % {
                    'correct': correct,
                    }
        elif self.exception:
            return "Exception: %(correct)s (code threw %(exception)s)" % {
                    'correct': correct,
                    'exception': self.exception,
                    }
        elif self.summary == 'path bounds exceeded (path bounds exceeded)':
            return "Inconclusive: %(correct) (path bounds exceeded)"
        else:
            # Shouldn't get here, but say something meaningful if the above
            #   is missing a case.
            return "%s: %s" % (self.status, correct)

def compilation_error_to_string(error):
    return '%(line)d:%(column)d::%(errorNumber)s: %(errorText)s' % error

class Exploration(object):
    '''Wrapper for /api/explorations response.'''

    def __init__(self, attempt, exp):
        self.attempt = attempt
        # See https://api.codehunt.com/ for documentation on
        #   interface Exploration
        self.exp = exp

        self.is_complete = exp['isComplete']
        self.kind = exp['kind']

        self.attempt_compiles = self.kind == 'TestCases'

        if self.attempt_compiles:
            self.has_won = exp['hasWon']
            self.test_cases = [ExplorationTestCase(exp['names'], tc)
                               for tc in exp['testCases']]
            self.errors = None
        else:
            self.has_won = False
            self.test_cases = None

            if self.kind == 'InternalError':
                # Should not happen
                self.errors = [exp['exception']]
            elif self.kind == 'CompilationError':
                self.compilation_errors = exp['errors']
                self.errors = [compilation_error_to_string(error)
                               for error in exp['errors']]
            elif self.kind == 'BadPuzzle':
                self.errors = [exp['description']]
            elif self.kind == 'BadCodingDuel':
                self.errors = exp['errors']
            elif self.kind == 'BadDependency':
                self.errors = exp['referencedTypes']

    def __repr__(self):
        return "%s.%s(%s, %s)" % (type(self).__module__, type(self).__name__,
                                  repr(self.attempt), repr(self.exp))

    def __str__(self):
        if self.kind == 'TestCases':
            return "{Exploration %(kind)s%(won)s [%(test_cases)s]}" % {
                    'kind': self.kind,
                    'test_cases': '; '.join([str(tc)
                                             for tc in self.test_cases]),
                    'won': ' (won)' if self.has_won else ''
                    }
        else:
            return "{Exploration %(kind)s %(errors)s}" % {
                    'kind': self.kind,
                    'errors': self.errors,
                    }

class Translation(object):
    '''Wrapper for /api/translate response.'''

    def __init__(self, attempt, translation):
        self.attempt = attempt
        # Include level so a translation object is a valid attempt for
        #   the Client.explore() method
        self.level = attempt.level
        self.translation = translation

        if translation['kind'] == 'Translated':
            self.success = True
            self.text = translation['program']['text']
            self.language = translation['program']['language']
            self.errors = None
        else:
            self.success = False
            self.text = None
            self.language = None
            self.errors = translation['errors']

    def __repr__(self):
        return "%s.%s(%s, %s)" % (type(self).__module__, type(self).__name__,
                                  repr(self.attempt), repr(self.translation))

    def __str__(self):
        if self.success:
            return '{Translation of %s}' % self.attempt
        else:
            return '{Failed translation of %s: %s}' % \
                    (self.attempt, [compilation_error_to_string(error)
                                    for error in self.errors])

class Client(object):
    '''Client for Code Hunt REST API. See https://api.codehunt.com/ for
        documentation on the API.'''

    base_url = 'https://api.codehunt.com/api'

    def __init__(self, client_id, client_secret):
        '''client_id and client_secret are the Code Hunt REST API equivalent
            of a username and password. If you do not have a client_id and
            client_secret, you can request them from codehunt@microsoft.com.'''

        self.client_id = client_id
        self.client_secret = client_secret

        self.headers = self._get_auth_header()

    def _get_auth_header(self):
        resp = requests.post("%s/token" % self.base_url,
                params = { 'grant_type': 'client_credentials',
                           'client_id': self.client_id,
                           'client_secret': self.client_secret })
        token = resp.json()['access_token']

        return { 'Authorization': 'Bearer %s' % token }

    def explore(self, attempt, wait=False):
        '''Perform an exploration on an attempt finding one of three cases:
            1. It has errors.
            2. It is a correct solution.
            3. It is incorrect, along with counterexamples showing that.
            
        Returns a value of type Exploration.'''

        resp = requests.post("%s/explorations" % self.base_url,
                             headers = self.headers,
                data = json.dumps({
                        'program': {
                                'language': attempt.language,
                                'text': attempt.text
                            },
                        'challengeId': attempt.level.challenge_id,
                    }))
        data = resp.json()
        id = data['id']
        get_exp_url = "%s/explorations/%s" % (self.base_url, id)
        data = requests.get(get_exp_url, headers = self.headers).json()
        # Don't wait for computation because any explorations in the
        #   data release should be cached and be available immediately.
        if wait:
            while not data['isComplete']:
                time.sleep(1)
                data = requests.get(get_exp_url, headers = self.headers).json()

        return Exploration(attempt, data)

    def translate(self, attempt):
        '''Translates a Java program to C#. Note that the translation is very
            limited in its Java support. The result of a translation is either
            1. An error due to the code not being valid Java or using
                unsupported features of Java.
            2. The C# translation of the Java program which Code Hunt uses
                internally.

        Returns a value of type Translation.'''

        if attempt.language != "Java":
            raise Exception("Can only translate Java programs.")

        resp = requests.post("%s/translate?language=CSharp" % self.base_url,
                             headers = self.headers,
                data = json.dumps({
                            'language': attempt.language,
                            'text': attempt.text
                    }))
        data = resp.json()

        return Translation(attempt, data)
