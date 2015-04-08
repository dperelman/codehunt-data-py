import collections
import datetime
import functools
import glob
import os
import re


# Not in Python 2.x
if hasattr(datetime, 'timezone'):
    tzinfo_utc = datetime.timezone.utc
else:
    # From http://stackoverflow.com/a/2331635
    ZERO = datetime.timedelta(0)

    # A UTC class.

    class UTC(datetime.tzinfo):
        """UTC"""

        def utcoffset(self, dt):
            return ZERO

        def tzname(self, dt):
            return "UTC"

        def dst(self, dt):
            return ZERO

    tzinfo_utc = UTC()


# Not in Python 2.x
if hasattr(functools, 'lru_cache'):
    def memoized(f):
        return functools.lru_cache(maxsize=None)(f)
else:
    # Based on http://stackoverflow.com/a/18723434
    def memoized(input_func):
        class _Cache_class(object):
            def __init__(self, input_func):
                self._input_func        = input_func
                self._caches_dict       = {}

            def __get__(self, obj, objtype):
                """ Called for instance methods """
                return_func = functools.partial(self._cache_wrapper, obj)
                # Return the wrapped function and wraps it to maintain the docstring and the name of the original function:
                return functools.wraps(self._input_func)(return_func)

            def __call__(self, *args, **kwargs):
                """ Called for regular functions """
                return self._cache_wrapper(None, *args, **kwargs)


            def _cache_wrapper(self, caller, *args, **kwargs):
                # Create a unique key including the types (in order to differentiate between 1 and '1'):
                kwargs_key = "".join(map(lambda x : str(x) + str(type(kwargs[x])) + str(kwargs[x]), sorted(kwargs)))
                key = "".join(map(lambda x : str(type(x)) + str(x) , args)) + kwargs_key

                # Check if caller exists, if not create one:
                if caller not in self._caches_dict:
                    self._caches_dict[caller] = collections.OrderedDict()

                # Check if the key exists, if so - return it:
                cur_caller_cache_dict = self._caches_dict[caller]
                if key in cur_caller_cache_dict:
                    return cur_caller_cache_dict[key]

                # Call the function and store the data in the cache (call it with the caller in case it's an instance function - Ternary condition):
                cur_caller_cache_dict[key] = self._input_func(caller, *args, **kwargs) if caller != None else self._input_func(*args, **kwargs)
                return cur_caller_cache_dict[key]


        # Return the decorator wrapping the class (also wraps the instance to maintain the docstring and the name of the original function):
        return functools.wraps(input_func)(_Cache_class(input_func))

def memoized_property(f):
    return property(memoized(f))

def read_all_text(filename):
    with open(filename, "r") as f:
        return f.read()


class Level(object):
    level_name_re = re.compile(r"Sector(?P<sector>\d)-Level(?P<level>\d)")

    def __init__(self, challenge_id_filename):
        self.challenge_id_filename = challenge_id_filename
        basename = os.path.basename(challenge_id_filename)
        self.level_name = os.path.splitext(basename)[0]

        match = self.level_name_re.match(self.level_name)
        self.sector_num = int(match.group('sector'))
        self.level_in_sector = int(match.group('level'))

    def __repr__(self):
        return "%s.%s(%s)" % (type(self).__module__, type(self).__name__,
                              repr(self.challenge_id_filename))

    def __str__(self):
        return "{%s %s}" % (type(self).__name__, self.level_name)

    @memoized_property
    def challenge_id(self):
        return read_all_text(self.challenge_id_filename)

    @memoized_property
    def challenge_text(self):
        filename = os.path.splitext(self.challenge_id_filename)[0] + ".cs"
        return read_all_text(filename)

def load_levels(directory):
    files = glob.glob(os.path.join(directory, "solutions", "*.challengeId"))
    return [Level(f) for f in files]

class Attempt(object):
    #Format: attemptNNN-YYYYMMDD-HHMMSS[-winningR].(java|cs)
    attempt_filename_re = re.compile(r"attempt(?P<attemptNum>[0-9]{3})-(?P<year>[0-9]{4})(?P<month>[0-9]{2})(?P<day>[0-9]{2})-(?P<hour>[0-9]{2})(?P<minute>[0-9]{2})(?P<second>[0-9]{2})(-winning(?P<rating>[1-3]))?.(?P<ext>java|cs)")
    language_ext_dict = {
            'cs': 'CSharp',
            'java': 'Java',
            }

    def __init__(self, user, level, attempt_filename):
        self.user = user
        self.level = level
        self.filename = attempt_filename

        match = self.attempt_filename_re.match(os.path.basename(self.filename))

        self.attempt_num = int(match.group('attemptNum'))

        year = int(match.group('year'))
        month = int(match.group('month'))
        day = int(match.group('day'))
        hour = int(match.group('hour'))
        minute = int(match.group('minute'))
        second = int(match.group('second'))
        self.timestamp = datetime.datetime(year, month, day,
                                           hour, minute, second,
                                           tzinfo=tzinfo_utc)

        if match.group('rating'):
            self.won = True
            self.rating = int(match.group('rating'))
        else:
            self.won = False
            self.rating = None

        # "java" or "cs"
        self.language_ext = match.group('ext')
        # "Java" or "CSharp" (language names used by REST API)
        self.language = self.language_ext_dict[self.language_ext]

    def __repr__(self):
        return "%s.%s(%s, %s, %s)" % (type(self).__module__,
                                      type(self).__name__,
                                      repr(self.user),
                                      repr(self.level),
                                      repr(self.filename))

    def __str__(self):
        return "{%s %s %s %s}" % (type(self).__name__, str(self.user),
                                  str(self.level),
                                  str(os.path.basename(self.filename)))

    @memoized_property
    def text(self):
        return read_all_text(self.filename)

class User(object):
    def __init__(self, user_directory):
        self.directory = user_directory

    def __repr__(self):
        return "%s.%s(%s)" % (type(self).__module__, type(self).__name__,
                              repr(self.directory))

    def __str__(self):
        return "{%s %s}" % (type(self).__name__, self.directory[-3:])

    @memoized_property
    def experience(self):
        filename = os.path.join(self.directory, "experience")
        return read_all_text(filename)

    @memoized
    def get_attempts(self, level):
        directory = os.path.join(self.directory, level.level_name)
        if os.path.exists(directory):
            return [Attempt(self, level, os.path.join(directory, f))
                    for f in os.listdir(directory)]
        else:
            return None

def load_users(directory):
    users = glob.glob(os.path.join(directory, "users", "User*"))
    return [User(u) for u in users]

class Data(object):
    def __init__(self, directory):
        self.directory = directory
        self.levels = load_levels(directory)
        self.users = load_users(directory)
