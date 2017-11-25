"""
    Python programming for the IRC bridging.
"""

import os
import re
import sys
import time
import json
import random
import socket
import datetime
import traceback
import threading
import collections

from .user import User
from .irc import Connection
from .message import Message
from .channel import Channel

from bridgesystem import BridgeBase, util


class Bridge(BridgeBase):
    """
        A class representing a bridge that connects to an IRC server.
    """

    connection = None
    """
        The IRC connection object in use.
    """

    user_color_maps = None
    """
        A map mapping user names to colors.
    """

    channel_instances = None
    """
        A dictionary mapping IRC channel names to their instances representing the channel.
    """

    user_instances = None
    """
        A dictionary mapping IRC user names to their instances representing the user.
    """

    def handle_strikethrough_format(self, match_data):
        """
            Handles processing of strike throughs on Discord.
        """
        result = ""
        for character in match_data.group(2):
            result += character + "\u0336"
        return result

    DISCORD_TO_IRC_FORMATS = collections.OrderedDict()
    """
        Formatting specifications for translating Discord formats to IRC formats.
    """

    def stop(self):
        """
            Stops the addon.
        """

    def start(self):
        """
            Starts the addon after it has been initialized and all connections associated. This is called after
            all connections have been created.
        """

        self.user_color_maps = {}
        color_file_path = self.get_data_path("userColors.json")
        if os.path.exists(color_file_path):
            with open(color_file_path, "r") as handle:
                try:
                    self.user_color_maps = json.loads(handle.read())
                except ValueError as e:
                    self.logger.error("Failed to load userColors.json:\n %s" % traceback.format_exc())

        self.event_handler.register_event(self.event_handler.Events.OnReceiveMessage, self.on_receive_message)

        event_handlers = {
            "OnJoin": self.handle_irc_join,
            "OnQuit": self.handle_irc_quit,
            "OnPart": self.handle_irc_part,
            "OnReceive": self.handle_irc_message,
            "OnReceivePose": self.handle_irc_pose,
            "OnUserListPopulate": self.handle_user_list,
            "OnReceivePrivate": self.handle_private_irc_message
        }

        # Initialize the IRC formats in a specific order
        self.DISCORD_TO_IRC_FORMATS["(\*{1,3})([^\*]+)\\1"] = ["\x1D%s\x1D", "\x02%s\x02", "\x02\x1D%s\x1D\x02"]
        self.DISCORD_TO_IRC_FORMATS["(\_{1,4})([^_]+)\\1"] = ["\x1D%s\x1D", "\x1F%s\x1F", "\x1D\x1F%s\x1F\x1D", "\x1F%s\x1F"]
        self.DISCORD_TO_IRC_FORMATS["(~{2,})([^_]+)\\1"] = self.handle_strikethrough_format

        channels = set(self.configuration.bridge_generic_config.broadcasting_channels + self.configuration.bridge_generic_config.receiving_channels)
        self.connection = Connection(address=self.configuration.bridge_internal_config["host"],
                                     port=self.configuration.bridge_internal_config["port"],
                                     username=self.configuration.bridge_internal_config["username"],
                                     ping_delay=datetime.timedelta(seconds=self.configuration.bridge_internal_config["pingSeconds"]),
                                     channels=list(channels),
                                     logger=self.logger,
                                     password=self.configuration.bridge_internal_config["password"] if "password" in self.configuration.bridge_internal_config else None,
                                     event_handlers=event_handlers)

        self.userlist = {}
        self.user_instances = {}
        self.channel_instances = {}

    def register_channel(self, channel, members=None):
        """
            Registers a channel instance with the IRC bridge.

            :param channel: The name of the channel that we are registering with the bridge.
            :param members: A list of User instances that belong to this channel.
            :rtype: Channel
            :return: A Channel instance representing the registered channel.
        """
        channel = channel.lower()
        if channel in self.channel_instances.keys():
            return self.channel_instances[channel]

        channel = Channel(connection=self.connection, name=channel, display_name=channel, members=[] if members is None else members)
        self.channel_instances[channel] = channel
        return channel

    def register_user(self, username):
        """
            Registers a user instance with the IRC bridge.

            :param username: The name of the user to register.
            :rtype: User
            :return: A User instance representing the registered user.
        """
        username_lower = username.lower()
        if username_lower in self.user_instances.keys():
            return self.user_instances[username_lower]

        user = User(connection=self.connection, username=username)
        self.user_instances[username_lower] = user
        return user

    def handle_user_list(self, usernames, channel):
        """
            Handles an IRC user list event. This is called when the bot first joins the server.

            :param channel: The name of the channel.
            :param usernames: A set of usernames in this channel.
        """
        channel_members = [self.register_user(username) for username in usernames]
        channel_instance = self.register_channel(channel=channel, members=channel_members)
        channel_instance.members = channel_members
        self.channel_instances[channel] = channel_instance

    def handle_irc_join(self, username, channel, hostmask):
        """
            Handles an IRC join event.

            :param username: The username that joined.
            :param channel: The channel that was joined.
            :param hostmask: The hostmask of the joining user.
        """
        if self.configuration.bridge_generic_config.broadcast_join_leaves:
            user = self.register_user(username)
            channel = self.register_channel(channel=channel)
            self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveJoin, emitter=self, user=user, channels=[channel])

    def handle_irc_part(self, username, channel, hostmask, message):
        """
            Handles an IRC part event.

            :param username: The username that left.
            :param channel: The channel that was left.
            :param hostmask: The hostmask of the leaving user.
            :param message: The parting message, if any, specified by the user.
        """
        if self.configuration.bridge_generic_config.broadcast_join_leaves:
            user = self.register_user(username)
            channel = self.register_channel(channel=channel)
            self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveLeave, user=user, emitter=self, channels=[channel])

    def handle_irc_quit(self, username, message, hostmask, channels):
        """
            Handles an IRC quit event.

            :param username: The username that has left the server.
            :param message: The quit message, if any, specified by the user.
            :param hostmask: The hostmask of the quitting user.
            :param channels: A set of channel names that the user was in.
        """
        if self.configuration.bridge_generic_config.broadcast_join_leaves:
            user = self.register_user(username)
            channels = [self.register_channel(channel=channel.lower()) for channel in channels]
            self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveLeave, emitter=self, user=user, target_channels=channels)

    def handle_irc_pose(self, username, message, channel):
        """
            Handles an IRC pose event. This is actually just a CTCP action being handled.

            :param username: The username of the posing client.
            :param message: The pose message.
            :param channel: The channel being posed in.
        """
        if self.configuration.bridge_generic_config.broadcast_messages:
            user = self.register_user(username)
            channel = self.register_channel(channel=channel)
            message = Message(sender=user, raw_text=message, channels=channel, connection=self.connection)
            self.event_handler.broadcast_event(self.event_handler.Events.OnReceivePose, emitter=self, message=message)

    def handle_private_irc_message(self, username, message):
        """
            Handles an IRC message event.

            :param username: The username of the sending user.
            :param message: The message text.
            :param channel: The name of the channel the message was sent to.
        """
        if self.configuration.bridge_generic_config.broadcast_messages:
            user = self.register_user(username)
            message = Message(sender=user, raw_text=message, channels=None, connection=self.connection)
            self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveMessagePrivate, emitter=self, message=message)

    def handle_irc_message(self, username, message, channel):
        """
            Handles an IRC message event.

            :param username: The username of the sending user.
            :param message: The message text.
            :param channel: The name of the channel the message was sent to.
        """
        if self.configuration.bridge_generic_config.broadcast_messages:
            user = self.register_user(username)
            channel = self.register_channel(channel=channel)
            message = Message(sender=user, raw_text=message, channels=channel, connection=self.connection)
            self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveMessage, emitter=self, message=message)

    def send(self, sender, message, target_channels):
        if sender is self:
            return

        message_lines = message.replace("\r", "").split("\n")
        for channel in target_channels:
            for line in message_lines:
                self.connection.say(line, channel)

    def on_receive_message(self, emitter, message):
        """
            A handler for receiving a message from another bridge in the same broadcast domain.

            :param bridge: The bridge instance sending the event.
            :param message: The message object that was sent.
        """
        if emitter is self:
            return

        if message.sender.username not in self.configuration.bridge_generic_config.ignore_senders:
            # Generate colors
            user_color = None
            if self.configuration.bridge_internal_config["enableUserColors"]:
                if message.sender.username in self.user_color_maps.keys():
                    user_color = self.user_color_maps[message.sender.username]
                else:
                    # Initialize the color counts so currently unused colors are viable selections
                    color_counts = {}
                    for color in range(2, 15):
                        color_counts.setdefault(color, 0)

                    # Count color instances
                    for color in self.user_color_maps.values():
                        color_counts[color] += 1

                    # Once we have colors counted, pick the lowest used set of colors.
                    lowest_count = min(color_counts.values())
                    color_selection = [color for color, count in zip(color_counts.keys(), color_counts.values()) if count == lowest_count]
                    color_selection = random.choice(color_selection)
                    self.user_color_maps[message.sender.username] = color_selection

                    # Write the new color file.
                    color_file_path = self.get_data_path("userColors.json")
                    with open(color_file_path, "w") as handle:
                        handle.write(json.dumps(self.user_color_maps, sort_keys=True, separators=(", ", ":"), indent=4))

                    user_color = "%02d" % color_selection

            # Fixes people pinging themselves in IRC if they are also connected here
            old_sender = message.sender.username
            sender_name = message.sender.username[0] + "\u200B"
            if len(sender_name) > 1:
                sender_name = sender_name + old_sender[1:]

            # Colorize the name.
            if user_color is not None:
                sender_name = "\x03%s%s\x03" % (user_color, sender_name)

            # Produce the replacements before altering the string we are searching
            message_text = message.raw_text if message.raw_text is not None else ""
            while True:
                generated_replacements = {}
                for discord_pattern, irc_patterns in zip(self.DISCORD_TO_IRC_FORMATS.keys(), self.DISCORD_TO_IRC_FORMATS.values()):
                    for match in re.finditer(discord_pattern, message_text):
                        #    We need to perform processing for locating URL's in our matching sequences so the underscore characters
                        #    aren't formatted into IRC URL's and screwing them.
                        match_start = match.start()
                        http_location = message_text.rfind("http://", None, match_start)
                        https_location = message_text.rfind("https://", None, match_start)

                        hypertext_start = None
                        if http_location != -1:
                            hypertext_start = http_location
                        elif https_location != -1:
                            hypertext_start = https_location

                        # If there is a found hypertext, check if there is any spaces
                        if hypertext_start is not None:
                            potential_url = message_text[hypertext_start:match.end()]
                            if " " not in potential_url:
                                continue

                        irc_pattern_index = len(match.group(1)) - 1
                        if callable(irc_patterns) is True:
                            generated_replacements[match.group(0)] = irc_patterns(match)
                        else:
                            generated_replacements[match.group(0)] = irc_patterns[irc_pattern_index] % match.group(2)

                if len(generated_replacements) == 0:
                    break

                # Generate the final output message
                for replaced_value, new_value in zip(generated_replacements.keys(), generated_replacements.values()):
                    message_text = message_text.replace(replaced_value, new_value)

            # Generate final output.
            message_text = "\x02<%s: %s>\x02 %s" % (emitter.configuration.name, sender_name, message_text)

            # Send the message.
            result = Message(sender=message.sender, raw_text=message.raw_text, channels=message.channels, connection=self.connection)
            target_channels = [channel.name.lower() for channel in message.channels]
            self.send_buffered_message(sender=old_sender, target_channels=target_channels, message=message_text, buffer_size=450, send_function=self.send)
            return result

    def register_connection(self, connection):
        """
            Registers this addon with the given IRC connection.

            :param connection: The IRC connection we are being associated with.
        """

    def update(self, delta_time):
        """
            Process an update tick.

            :param delta_time: The time since the last time addon updates were processed.
        """
        super(Bridge, self).update(delta_time)
        self.connection.update(delta_time)
