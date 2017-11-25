"""
    A plugin implementing a chat command framework.
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

    def __init__(self, application, logger, home_path, configuration, global_configuration, event_handler):
        """
            Initializes a new Plugin. Here you should perform basic initialization of your plugin.
        """
        super(SeenCommandPlugin, self).__init__(application=application, event_handler=event_handler, logger=logger,
                                                 home_path=home_path, configuration=configuration, global_configuration=global_configuration)


    def start(self):
        """
            Called when the plugin should actually startup and begin operation.
        """
        self.seen_database = {}
        self.event_handler.register_event(self.event_handler.Events.OnReceiveMessage, self.on_receive_message)
        self.event_handler.register_event(self.event_handler.Events.OnReceiveMessagePrivate, self.on_receive_private_message)

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

    def on_receive_message(self, emitter, message):
        """
            A callback handler for when the bot receives a regular text message in a channel.

            :param bridge: The sending bridge.
            :param message: The message that was sent.
        """
        self.seen_database[message.sender] = datetime.datetime.now()

    def on_receive_private_message(self, emitter, message):
        """
            A callback handler for when the bot receives a private text message.

            :param bridge: The sending bridge.
            :param message: The message that was sent.
        """
        self.seen_database[message.sender] = datetime.datetime.now()
