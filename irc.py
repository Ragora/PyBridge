""" IRC code for the PyIRCBot. This is what actually establishes the connections and emits various
event types for loaded addons to respond to. """

import os

import importlib
import socket

from blinker import signal
from apscheduler.scheduler import Scheduler

import settings

class IRC:
	addons = None
	username = None
	nickname = None
	server = None
	channel = None
	socket = None

	on_receive = signal('on_receive')
	on_receive_private = signal('on_receive_private')
	on_update = signal('on_update')

	buffer = None
	scheduler = None
	commands = None

	def __init__(self, home_path, nick=None):
		configuration = settings.Settings('configuration.txt')
		self.username = configuration.get_index('username', str)
		if (nick is None):
			self.nickname = configuration.get_index('nickname', str)
		else:
			self.nickname = nick

		self.channel = configuration.get_index('channel', str)
		self.phrase = configuration.get_index('phrase', str)

		server_info = configuration.get_index('server', str).split(':')
		if (len(server_info) == 1):
			self.server = (server_info[0], 6667)
		else:
			self.server = (server_info[0], int(server_info[1]))

		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect(self.server)

		self.addons = [ ]
		self.commands = { }
		self.buffer = ''

		addons = configuration.get_index('addons', str).split(';')
		for addon in addons:
			try:
				module = importlib.import_module(addon)
				addon_instance = module.Addon(self)
				command_listing = addon_instance.get_commands()
				if (command_listing is not None):
					self.commands.update(command_listing)
				self.addons.append(addon_instance)
			except ImportError as e:
				print(e)

		self.send('NICK %s' % self.nickname)
		self.send('USER %s' % self.username)

		self.scheduler = Scheduler()
		self.scheduler.add_interval_job(self.keepalive, seconds=2)
		self.scheduler.start()

	def send(self, string):
		self.socket.send('%s\r\n' % string)

	def say(self, string):
		self.socket.send('PRIVMSG #%s :%s\r\n' % (self.channel, string))

	def say_to(self, name, string):
		self.socket.send('PRIVMSG %s :%s\r\n' % (name, string))

	def receive(self):
		while (True):
			self.on_update.send()

			received = self.socket.recv(9)
			self.buffer += received

			if ('\r\n' in self.buffer):
				split = self.buffer.split('\r\n')

				return_buffer = str(split[0]).lstrip(':')
				if (len(split) != 1):
					self.buffer = split[1]
				else:
					self.buffer = ''

				words = return_buffer.split()
				if (words[0] == 'PING'):
					self.send('PONG %s' % words[1])
					return None
				elif (words[1] == '004'):
					self.send('JOIN #%s' % self.channel)
					return None
				elif (words[1] == 'PRIVMSG' and words[2] == '#' + self.channel):
					sending_user = words[0].split('!')
					sending_user = sending_user[0]

					message_data = return_buffer[return_buffer.find(':')+1:]
					if (sending_user == 'MD2Funhouse'):
						game_user_end = message_data.find('>')
						sending_user = message_data[message_data.find('<')+1:game_user_end]
						message_data = message_data[game_user_end+1:].lstrip()

					words = message_data.split()
					if (message_data[0] == ']'):
						command = words[0].lstrip(']').lower()
						if (command in self.commands):
							function_call = self.commands[command]['call']
							function_call(sending_user, message_data[len(command)+1:])
					if (words[0] == '(team)'):
						message_data = message_data[7:]

					self.on_receive.send(sending_user=sending_user, message=message_data)
					return None
				elif(words[1] == 'PRIVMSG' and words[2] != '#' + self.channel):
					sending_user = words[0].split('!')
					sending_user = sending_user[0]
					message_data = return_buffer[return_buffer.find(':')+1:]

					self.on_receive_private.send(sending_user=sending_user, message=message_data)
					return None

				return return_buffer

	def keepalive(self):
		self.socket.send('PING :DRAGON\r\n')