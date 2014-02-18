""" PyIRCBot is mostly just personal software of mine I had designed out of pure boredom. It is
intended to connect to a given IRC server and channel and via the installed addons, it would
behave as desired. 

This software is licensed under the GNU General Public License version 3. Please refer to gpl.txt
for more information.

Copyright (c) 2013 Robert MacGregor """

import os
import sys

import irc

class Application:
	def main(self):
		# Does this work on Windows too?
		home_path = os.path.expanduser('~') + '/.pyIRCBot/'

		home_exists = os.path.exists(home_path)
		if (home_exists is False):
			os.system('mkdir %s' % home_path)

		# Get the ball rolling, start up the actual application logic.
		client = irc.IRC(home_path)

		while (True):
			received = client.receive()

if __name__ == '__main__':
	app = Application()
	app.main()
