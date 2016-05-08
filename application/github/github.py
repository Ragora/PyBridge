import json
import httplib
from datetime import datetime, timedelta

from blinker import signal
from apscheduler.schedulers.background import BackgroundScheduler

class Addon(object):
	username = "Username"
	token = "Token"

	headers = {
		"User-Agent": username,
		"Authorization": "token %s" % token,
	}

	last_sha = None
	api_call_counter = 0
	api_call_limit = 5000

	def __init__(self, connection, scheduler):
		self.connection = connection
		signal('on_receive').connect(self.on_receive)

		self.scheduler = BackgroundScheduler()
		self.scheduler.add_job(self.process_repositories, "interval", seconds=10)
		self.scheduler.start()

		self.api_call_counter = 0
		self.api_call_counter = self.get_api_usage()

	def get_api_usage(self):
		status, rate_data = self.perform_query("/rate_limit")

		if (status == 200):
			rate_data = rate_data["resources"]["core"]

			self.api_call_limit = int(rate_data["limit"])
			return self.api_call_limit - int(rate_data["remaining"])

		return None

	def perform_query(self, url):
		if (self.api_call_counter >= 5000):
			return

		connection = httplib.HTTPSConnection("api.github.com")
		connection.request("GET", url, None, self.headers)

		response = connection.getresponse()
		data = response.read()
		status = response.status
		connection.close()

		self.api_call_counter = self.api_call_counter + 1

		if (status == 200):
			data = json.loads(data)
		else:
			data = None

		return (status, data)

	def process_repositories(self):
		# Refresh our call counter
		api_usage = self.get_api_usage()

		if (api_usage is not None):
			self.api_call_counter = api_usage

		status, data = self.perform_query("/users/%s/events" % self.username)

		if (status == 200):
			now = datetime.utcnow()

			for index, action in enumerate(data):
				action_data = action
				action = action["payload"]

				date = datetime.strptime(action_data["created_at"], "%Y-%m-%dT%H:%M:%SZ")
				date_delta = now - date

				seconds_ago = abs(date_delta.seconds)
				if ((date.day != now.day or date.month != now.month or date.year != now.year) or seconds_ago >= 20):
					continue

				# A commit
				if ("commits" in action):
					commit = action["commits"][0]
					sha = commit["sha"]

					if (sha == self.last_sha):
						return

					self.last_sha = sha

					# Grab information about the commit
					status, data = self.perform_query(commit["url"])

					message = "New Commit (%s) %u seconds ago: %s" % (self.username, seconds_ago, commit["message"])
					self.connection.say(message)

					if (status == 200):
						self.connection.say(data["html_url"])
					else:
						self.connection.say("Cannot get commit URL!")

				# A tag, probably
				elif ("master_branch" in action):
					branch = action["master_branch"]
					name = action["ref"]

					repo_name = action_data["repo"]["name"]

					self.connection.say("New tag (%s) on %s: %s on branch %s" % (self.username, repo_name, name, branch))

	def get_commands(self):
		command_dict = {
			"usage": {
				"call": self.cmd_usage
			},
		}
		return command_dict

	def cmd_usage(self, sender, message):
		self.connection.say("%u calls dispatched out of %u max" % (self.api_call_counter, self.api_call_limit))

	def on_receive(self, sender, sending_user, message, channel):
		if (sending_user == self.connection.nickname):
			return
