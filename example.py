#!/usr/bin/env python

import codehunt.datarelease
import codehunt.rest

# In order to get access to the Code Hunt REST API, please
#   request a client_id and client_secret from codehunt@microsoft.com
client_id = None
client_secret = None

if client_id is None:
    client = None
else:
    client = codehunt.rest.Client(client_id=client_id,
                                  client_secret=client_secret)

data = codehunt.datarelease.Data("./Code Hunt data release 1/")

for level in data.levels:
    # The friendly name for the level used in the data release and Python
    print(level)
    # The Code Hunt API name for the level
    print(level.challenge_id)
    # The reference solution for the level
    print(level.challenge_text)

for user in data.users:
    print(user)
    # user-reported experience level, 1-3:
    #   1="Beginner", 2="Intermediate", 3="Advanced"
    print(user.experience)
    for level in data.levels:
        attempts = user.get_attempts(level)
        # attempts will be None if the user did not attempt this level
        if attempts:
            for attempt in attempts:
                print(attempt.filename)
                print(attempt.attempt_num)
                print(attempt.won)
                print(attempt.rating)
                print(attempt.timestamp)
                print(attempt.language)
                print(attempt.text)

                # Get a client_id/client_secret from codehunt@microsoft.com
                #   to query the Code Hunt REST API.
                if client is not None:
                    if(attempt.language == "Java"):
                        # Translate from Java to C#
                        t = client.translate(attempt)
                        print(t)
                        if t.success:
                            print(t.text)
                        else:
                            print(t.errors)
                    # Perform "exploration": this is what the "Capture Code"
                    #   button does in the game. The response will be an error
                    #   or a set of test cases.
                    exp = client.explore(attempt)
                    print(exp)
                    if attempt.won != exp.has_won:
                        print("This shouldn't happen.")
                    if exp.attempt_compiles:
                        for test_case in exp.test_cases:
                            print(test_case)
                    else:
                        # kind of failure
                        print(exp.kind)
                        # error messages
                        print(exp.errors)
                        if exp.kind == 'CompilationError':
                            # compilation error messages are more structured,
                            #   they are also summarized in exp.errors
                            print(exp.compilation_errors)
