"""
	markov.py
	Small code to keep track of multiple markov chains

	Copyright (c) 2013 Robert MacGregor
	This software is licensed under the GNU General Public License v3. Please
	refer to gpl.txt for more information.
"""

import random
from weakref import WeakValueDictionary

from blinker import signal

class MarkovChain:
	chain = None
	def __init__(self):
		self.chain = { }

	def generate(self, word, length):
		sentence = word.capitalize()
		for x in range(0, length):
			if (word not in self.chain):
				word = random.choice(self.chain.keys())

			new = random.choice(self.chain[word])
			if (word.capitalize() == new):
				sentence += '. ' + new
			else:
				sentence += ' ' + new
			word = new

		return sentence

	def export(self, targetfile):
		with open(targetfile, "w") as handle:
			for word in self.chain.keys():
				handle.write('%s:' % word)
				for sub_word in self.chain[word]:
					handle.write('%s:' % sub_word)
				handle.write('\n')

	def load(self, targetfile):
		with open(targetfile, "r") as handle:
			for line in handle:
				line = line.replace("\n", "").replace("\r","").replace(".","").replace(";","").replace("?","")
				data = line.split(":")

				entry = data[1:len(data)-1]
				if len(entry) == 0:
					entry.append("")

				print(entry)
				self.chain[data[0]] = entry

	def clear(self):
		self.chain = { }

	def word(self):
		return random.choice(self.chain.keys())

	def append(self, input):
		input = input.strip('!?.,\";]')

		words = input.split(' ')
		for index, current_word in enumerate(words):
			if (index != 0):
				previous_word = words[index-1]
				if (previous_word not in self.chain):
					self.chain[previous_word] = []
				self.chain[previous_word].append(current_word)
				#self.chain[previous_word].setdefault(previous_word, []).append(current_word)

class Addon:
	markov = None
	count = 0

	def __init__(self, connection):
		self.connection = connection
		signal('on_receive').connect(self.on_receive)
		signal('on_receive_private').connect(self.on_receive_private)
		self.markov = MarkovChain()

	def __del__(self):
		del self.on_receive
		del self.on_receive_private

	def get_commands(self):
		command_dict = {
			'markov': {
				'call': self.cmd_markov
			}
		}
		return command_dict

	def cmd_markov(self, sender, message):
		if (sender == self.connection.nickname):
			return

		words = message.split()

		start_word = random.choice(self.markov.chain.keys())
		sentence_length = 60

		if (len(words) >= 1):
			try:
				sentence_length = int(words[0])
			except ValueError:
				sentence_length = 60
			if (sentence_length > 60 or sentence_length < 1):
				sentence_length = 60

		if (len(words) >= 2):
			start_word = words[1]

		self.connection.say(self.markov.generate(start_word,sentence_length-1))

	def on_receive_private(self, sender, sending_user, message):
		split = message.split()
		if (split[0] != self.connection.phrase):
			return

		if (split[1] == 'export'):
			self.markov.export('database.txt')
		elif (split[1] == 'import'):
			self.markov.load('database.txt')

		self.connection.say_to(sending_user, "Command executed.")

	def on_receive(self, sender, sending_user, message):
		if (sending_user == self.connection.nickname):
			return

		print('%s -> %s' % (sending_user, message))
		self.markov.append(message)
		self.count += 1

		if (self.count >= 90):
			words = message.split()
			self.connection.say(self.markov.generate(random.choice(words), 11))
			self.count = 0
