"""
    A plugin implementing a seen command for tracking users.
"""

import datetime

from bridgesystem import PluginBase


class SeenCommandPlugin(PluginBase):
    """
        Class representing the plugin to be called by the main programming.
    """

    seen_database = None
    """
        A dictionary mapping user objects to the last datetime they were seen at.
    """

    def start(self):
        """
            Called when the plugin should actually startup and begin operation.
        """
        self.seen_database = {}
        self.domain.event_handler.register_event(self.domain.event_handler.Events.OnReceiveMessage, self.on_receive_message)

        for plugin in self.domain.plugins:
            if plugin.__class__.__name__ == "ChatCommandsPlugin":
                plugin.register_private_command_handler("seen", self.handle_seen_command, description="Determines when someone was last seen.")
                plugin.register_command_handler("seen", self.handle_seen_command, description="Determines when someone was last seen.")
                break
        else:
            raise BaseException("!!! Could not locate ChatCommandsPlugin for this Domain!")

    def stop(self):
        """
            Called when the plugin should stop all operational functions to be unloaded.
        """

    def update(self, delta_time):
        """
            Called when the plugin should update any internals it may have on an update pulse.
            This is called once per iteration of the main program loop.

            :param delta_time: A datetime.timedelta object representing how much realtime has passed
                since the last update.
        """

    def handle_seen_command(self, message, components):
        """
            Command handler for the seen invocation.

            :param message: The message object that was received.
            :param components: The command components split up by spaces.
        """
        search_name = " ".join(components).lstrip().rstrip()

        if search_name == "":
            message.sender.send_reply(message="A username is required.", channels=message.channels)
            return

        possible_matches = [message_data for user, message_data in zip(self.seen_database.keys(), self.seen_database.values()) if user.username.lower() == search_name.lower() or search_name.lower() in user.username.lower()]
        if len(possible_matches) == 0:
            message.sender.send_reply(message="No user by that name is on record.", channels=message.channels)
        else:
            result = "Matches for '%s'\n" % search_name
            for message_data in possible_matches:
                channels = ", ".join([channel.name for channel in message_data.channels])
                result += "    %s in channels %s at %s: %s\n" % (message_data.sender.username, channels, message_data.date.ctime(), message_data.raw_text)
            message.sender.send_reply(message=result, channels=message.channels)

    def on_receive_message(self, emitter, message):
        """
            A callback handler for when the bot receives a regular text message in a channel.

            :param bridge: The sending bridge.
            :param message: The message that was sent.
        """
        self.seen_database[message.sender] = message
