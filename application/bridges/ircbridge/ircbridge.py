"""
    discordbridge.py

    Code to provide discord IRC bridging.
"""

import os
import re
import sys
import time
import json
import random
import socket
import asyncio
import datetime
import threading
import collections

from .irc import Connection
from bridgesystem import BridgeBase, util

class Bridge(BridgeBase):
    connection = None
    """
        The IRC connection object in use.
    """

    user_color_maps = None
    """
        A map mapping user names to colors.
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
                self.user_color_maps = json.loads(handle.read())

        self.register_event("on_receive_message", self.on_receive_message)

        event_handlers = {
            "OnJoin": self.handle_irc_join,
            "OnReceive": self.handle_irc_message,
            "OnReceivePose": self.handle_irc_pose,
            "OnQuit": self.handle_irc_quit,
            "OnPart": self.handle_irc_part,
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

    def handle_irc_join(self, username, channel, hostmask):
        if self.configuration.bridge_generic_config.broadcast_join_leaves:
            self.application.broadcast_event("on_receive_join", sender=self, joined_name=username, target_channels=[channel])

    def handle_irc_part(self, username, channel, hostmask, message):
        if self.configuration.bridge_generic_config.broadcast_join_leaves:
            self.application.broadcast_event("on_receive_leave", sender=self, left_name=username, target_channels=[channel])

    def handle_irc_quit(self, username, message, hostmask, channels):
        if self.configuration.bridge_generic_config.broadcast_join_leaves:
            self.application.broadcast_event("on_receive_leave", sender=self, left_name=username, target_channels=channels)

    def handle_irc_pose(self, username, message, channel):
        if self.configuration.bridge_generic_config.broadcast_messages:
            self.application.broadcast_event("on_receive_pose", sender=self, message=message, sender_name=username, target_channels=[channel])

    def handle_irc_message(self, username, message, channel):
        if self.configuration.bridge_generic_config.broadcast_messages:
            self.application.broadcast_event("on_receive_message", sender=self, sender_name=username, message=message, target_channels=[channel])

    def send(self, sender, message, target_channels):
        message_lines = message.replace("\r", "").split("\n")
        for channel in target_channels:
            for line in message_lines:
                self.connection.say(line, channel)

    def on_receive_message(self, sender, sender_name, message, target_channels):
        if sender_name not in self.configuration.bridge_generic_config.ignore_senders:
            # Generate colors
            user_color = None
            if self.configuration.bridge_internal_config["enableUserColors"]:
                if sender_name in self.user_color_maps.keys():
                    user_color = self.user_color_maps[sender_name]
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
                    self.user_color_maps[sender_name] = color_selection

                    # Write the new color file.
                    color_file_path = self.get_data_path("userColors.json")
                    with open(color_file_path, "w") as handle:
                        handle.write(json.dumps(self.user_color_maps, sort_keys=True, separators=(", ", ":"), indent=4))

                    user_color = "%02d" % color_selection

            # Fixes people pinging themselves in IRC if they are also connected here
            old_sender = sender_name
            sender_name = sender_name[0] + "\u200B"
            if len(sender_name) > 1:
                sender_name = sender_name + old_sender[1:]

            # Colorize the name.
            if user_color is not None:
                sender_name = "\x03%s%s\x03" % (user_color, sender_name)

            # Produce the replacements before altering the string we are searching
            while True:
                generated_replacements = {}
                for discord_pattern, irc_patterns in zip(self.DISCORD_TO_IRC_FORMATS.keys(), self.DISCORD_TO_IRC_FORMATS.values()):
                    for match in re.finditer(discord_pattern, message):

                        #    We need to perform processing for locating URL's in our matching sequences so the underscore characters
                        #    aren't formatted into IRC URL's and screwing them.
                        match_start = match.start()
                        http_location = message.rfind("http://", None, match_start)
                        https_location = message.rfind("https://", None, match_start)

                        hypertext_start = None
                        if http_location != -1:
                            hypertext_start = http_location
                        elif https_location != -1:
                            hypertext_start = https_location

                        # If there is a found hypertext, check if there is any spaces
                        if hypertext_start is not None:
                            potential_url = message[hypertext_start:match.end()]
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
                    message = message.replace(replaced_value, new_value)

            # Generate final output.
            message = "\x02<%s: %s>\x02 %s" % (sender.configuration.name, sender_name, message)

            # Send the message.
            self.send_buffered_message(sender=old_sender, target_channels=target_channels, message=message, buffer_size=450, send_function=self.send)

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

    def get_commands(self):
        return {}
