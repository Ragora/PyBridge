""" 
    IRC.py
    
    IRC code for the PyIRCBot. This is what actually establishes the connections and emits various
    event types for loaded addons to respond to. 
    
"""

import os
import socket
import importlib

from blinker import signal

import settings

class Connection(object):
	addons = None
	""" A list addon instances that have been initialized and are operating in this IRC instance. """
	username = None
	""" The """
	nickname = None
	""" The nickname of the bot to use in the server. """
	server = None
	password = None
	
	""" The IP address of the server to connect to. """
	channel = None
	on_receive = signal("on_receive")
	on_receive_private = signal("on_receive_private")
	on_update = signal("on_update")

	buffer = None
	scheduler = None
	commands = None
	
	_socket = None
	""" The internal socket that the client will use. """
	_scheduler = None
	_performed_identification = None

	def __init__(self, home_path, scheduler):
		configuration = settings.Settings("configuration.txt")
		self.username = configuration.get_index("username", str)
		self.nickname = configuration.get_index("nickname", str)
		self.channel = configuration.get_index("channel", str)
		self.phrase = configuration.get_index("phrase", str)
		self.password = configuration.get_index("password", str)
		
		self._scheduler = scheduler

		server_info = configuration.get_index("server", str).split(":")
		if (len(server_info) == 1):
			self.server = (server_info[0], 6667)
		else:
			self.server = (server_info[0], int(server_info[1]))

		self.reconnect()

		self.addons = [ ]
		self.commands = { }
		self.buffer = ""

		addons = configuration.get_index("addons", str).split(";")
		for addon in addons:
			try:
				module = importlib.import_module(addon)
				addon_instance = module.Addon(self, self._scheduler)
				command_listing = addon_instance.get_commands()
				
				print(addon_instance)
				if (command_listing is not None):
					self.commands.update(command_listing)
				self.addons.append(addon_instance)
			except ImportError as e:
				print(e)
				
		self._performed_identification = False

		self.send("NICK %s" % self.nickname)
		self.send("USER %s" % self.username)

	def reconnect(self):
		self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._socket.connect(self.server)

		return True

	def send(self, string):
		self._socket.send("%s\r\n" % string)

	def say(self, string):
		self._socket.send('PRIVMSG #%s :%s\r\n' % (self.channel, string))

	def say_to(self, name, string):
		self._socket.send('PRIVMSG %s :%s\r\n' % (name, string))

	def receive(self):
		while (True):
			self.on_update.send()

			try:
				received = self._socket.recv(9)
				self.buffer += received

				if ("\r\n" in self.buffer):
					split = self.buffer.split("\r\n")

					return_buffer = str(split[0]).lstrip(":")
					if (len(split) != 1):
						self.buffer = split[1]
					else:
						self.buffer = ""

					words = return_buffer.split()
					print(words)
					if (words[0] == "PING"):
						self.send("PONG %s" % words[1])
						return None
					elif (words[1] == "004"):
						self.send("JOIN #%s" % self.channel)
						return None
					elif (words[1] == "PRIVMSG" and words[2] == "#" + self.channel):
						sending_user = words[0].split("!")
						sending_user = sending_user[0]
						message_data = return_buffer[return_buffer.find(":") + 1:]

						words = message_data.split()
						if (message_data[0] == "]"):
							command = words[0].lstrip("]").lower()
							if (command in self.commands):
								function_call = self.commands[command]["call"]
								function_call(sending_user, message_data[len(command) + 1:])

						self.on_receive.send(sending_user=sending_user, message=message_data, channel=self.channel)
						return None
					elif(words[1] == "PRIVMSG" and words[2] != "#" + self.channel):
						sending_user = words[0].split('!')
						sending_user = sending_user[0]
						message_data = return_buffer[return_buffer.find(":") + 1:]

						self.on_receive_private.send(sending_user=sending_user, message=message_data)
						return None
					# Handles for nick
					elif (words[1] == "NOTICE" and "nickserv" in words[0].lower() and not self._performed_identification and "registered" in return_buffer):
						self.say_to("NickServ", "IDENTIFY %s" % self.password)
						self._performed_identification = True
						
					return return_buffer
			except(socket.error):
				print("Disconnected from server -- attempting reconnection ...")
					
				self.reconnect()
