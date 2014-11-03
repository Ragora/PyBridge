""" 
    PyIRCBot is a bot written in Python that is designed to be simple to use.
    
    All of the behavior is controlled by a single configuration file whose syntax
    is very user friendly and is commented to desiginate the exact functionality of
    each configuration value.
    
    The technical design of the software is addon-oriented, therefore it is quite
    simple to add and remove functionality to the system as deemed necessary.
    
    This software is licensed under the MIT license, refer to LICENSE.txt for
    more information.
    
    Copyright (c) 2014 Robert MacGregor
"""


import os
import sys

from apscheduler.schedulers.background import BackgroundScheduler

import irc

# Does this work on Windows too?
home_path = os.path.expanduser('~') + '/.pyIRCBot/'

home_exists = os.path.exists(home_path)
if (home_exists is False):
    os.system('mkdir %s' % home_path)

# Setup the scheduler
scheduler = BackgroundScheduler()    

@scheduler.scheduled_job('interval', seconds=2)
def keepalive():
    client.send('PING :DRAGON\r\n')
    
# Setup the IRC client
client = irc.Connection(home_path, scheduler)
scheduler.start()

# Begin the main loop
while (True):
    client.receive()
        
