import re
import math

import numpy

from blinker import signal
from matheval import Parser

class Addon(object):
	_parser = None
	_variable_expression_ver = re.compile("[A-z]=([0-9]|\.)+(,[A-z]=([0-9]|\.)+)*$", re.IGNORECASE)
	_variable_expression_iter = re.compile("[A-z]=([0-9]|\.)+", re.IGNORECASE)

	def __init__(self, connection, scheduler):
		self.connection = connection
		signal('on_receive').connect(self.on_receive)

		self._parser = Parser()
		
	def __del__(self):
		del self.on_receive
		del self.on_receive_private

	def get_commands(self):
		command_dict = {
			"evaluate": {
				"call": self.cmd_evaluate
			},
			"eval": {
				"call": self.cmd_evaluate
			},
			"ev": {
				"call": self.cmd_evaluate
			},
			"substitute": {
				"call": self.cmd_substitute
			},
			"sub": {
				"call": self.cmd_substitute
			}
		}
		return command_dict
		
	def cmd_evaluate(self, sender, message):		
		words = message.lower().split()
		
		if (len(words) > 2):
			self.connection.say("Incorrect argument count. Must be used like: ]evaluate <expression> [a=value,b=value,...]")
			self.connection.say("Example: ]evaluate 2^x^y x=3,y=2")
			return
			
		expression = words[0]
		variable_mapping = { }
		if (len(words) == 2):
			if (re.match(self._variable_expression_ver, words[1]) is None):
				self.connection.say("Incorrect variable list format. Must be like: ]evaluate <expression> [a=value,b=value,...]")
				self.connection.say("Example: ]evaluate 2^x^y x=3,y=2")
				return
			
			# Now map the variables
			for result in re.finditer(self._variable_expression_iter, words[1]):
				result_text = result.group(0)
				
				variable = result_text[0]
				variable_value = None
				
				if (variable in variable_mapping.keys()):
					self.connection.say("Encountered duplicate variable '%s' in value mapping" % result_text[0])
					return
				
				try:
					variable_value = float(result_text[2])
				except(ValueError):
					self.connection.say("Encountered illegal value '%s'. All variable values must be decimals." % result_text[1])
					return
					
				variable_mapping[variable] = variable_value
				
		# Quick hack for "pi" and "e"
		expression = expression.replace("pi", "%s" % str(numpy.pi))
		expression = expression.replace("e", "%s" % str(numpy.e))
				
		# And parse
		try:
			result = self._parser.parse(expression).evaluate(variable_mapping)
			
			#if (result.imag == 0.0):
			#	result = numpy.float64(result.real)
				
			#if (numpy.abs(result) == numpy.floor(numpy.abs(result))):
			#	result = int(result)
				
			self.connection.say("Result of \"%s\": %s" % (expression, str(result)))
		except Exception as e:
			self.connection.say("Encountered an error: \"%s\"" % e)
			
	def cmd_substitute(self, sender, message):
		words = message.lower().split()
		
		if (len(words) < 3):
			self.connection.say("Incorrect argument count. Must be used like: ]substitute <expression> <variable> <insertexpression>")
			self.connection.say("Example: ]substitute x+y+z x 1+2")
			return

		original_expression = words[0]
		variable = words[1]
		inserted_expression = words[2]
			
		try:
			self.connection.say("Result of the substitution: %s" % self._parser.parse(original_expression).substitute(variable, inserted_expression).toString())
		except Exception as e:
			self.connection.say("Encountered an error: \"%s\"" % e)
			
	def on_receive(self, sender, sending_user, message, channel):
		if (sending_user == self.connection.nickname):
			return
		
	
