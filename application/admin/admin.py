from blinker import signal

class Addon(object):
	_curses = [ "fuck", "shit", "cunt", "nigger", "bitch", "ass", "dick", "penis", "vagina", "cock", "negro" ]
	""" A list of curse words to go off at. """
	
	_visual_maps = {
	"i": ["|"],
	"a": ["@"],
	"v": ["\/"],
	"n": ["|\|"]
	}
	""" A mapping of characters or sequences similiar to the alphanumeric ones that
	may be used to get around any straight-up detection. """
	
	_curse_counter = None

	def __init__(self, connection, scheduler):
		self.connection = connection
		signal('on_receive').connect(self.on_receive)
		
		self._curse_counter = { }
		
		print("Admin module initialized")

	def __del__(self):
		del self.on_receive
		del self.on_receive_private

	def get_commands(self):
		command_dict = {
			#'markov': {
		#		'call': self.cmd_markov
		#	}
		}
		return command_dict

	def on_receive(self, sender, sending_user, message, channel):
		if (sending_user == self.connection.nickname):
			return
		
		message = message.lower()
		sending_user = sending_user.lower()
		
		# Replace any visual occurences
		for character in self._visual_maps.keys():
			for visual_map in self._visual_maps[character]:
				message = message.replace(visual_map, character)
		
		# Now scan for each curse
		test_sentence = message.split()
		found_curse = False
		for curse in self._curses:
			if (curse in test_sentence):
				found_curse = True
				break
		
		self._curse_counter.setdefault(sending_user, 0)
		if (found_curse and self._curse_counter[sending_user] == 4):
			self._curse_counter[sending_user] += 1
			self.connection.say("%s, this is your final warning. Do not swear." % (sending_user))
		elif (found_curse and self._curse_counter[sending_user] < 4):
			self._curse_counter[sending_user] += 1
			
			# TODO: Load curse count from config?
			self.connection.say("%s, please do not swear. I will warn you %u times before kicking you from the server." % (sending_user, 5 - self._curse_counter[sending_user]))
		elif (found_curse and self._curse_counter[sending_user] >= 5):
			self._curse_counter[sending_user] = 0
			self.connection.say("Goodbye, %s." % (sending_user))

			self.connection.say_to("ChanServ", "KICK #%s %s Please stop." % (channel, sending_user))
