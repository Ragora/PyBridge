"""
    discordbridge.py

    Code to provide discord IRC bridging.
"""

import re
import sys
import time
import random
import asyncio
import threading

import discord

import irc

class Addon(object):
    connections = None
    """
        A list of all IRC connections in use by this addon.
    """

    configuration = None
    """
        The configuration associated with this addon.
    """

    discord_thread = None
    """
        The discord thread running the discord connection.
    """

    DISCORD_TO_IRC_FORMATS = {
        "(\*{1,3})([^\*]+)\\1": ["\x1D%s\x1D", "\x02%s\x02", "\x02\x1D%s\x1D\x02"],
        "(\_{1,4})([^_]+)\\1": ["\x1D%s\x1D", "\x1F%s\x1F", "\x1D\x1F%s\x1F\x1D", "\x1F%s\x1F"],
    }
    """
        Formatting specifications for translating Discord formats to IRC formats.
    """

    discord_user_color_maps = None
    """
        A dictionary mapping user names to their colors to be displayed in the IRC.
    """

    class DiscordThread(threading.Thread):
        """
            A class representing an independent thread of execution for running the discord bots in.
            This allows us to run the IRC programming while asyncio events are being processed.
        """

        outgoing_lock = None
        """
            A thread lock for the outgoing message list.
        """

        outgoing_messages = None
        """
            All messages waiting to be sent from Discord to the IRC.
        """

        incoming_lock = None
        """
            A thread lock for the incoming message list.
        """

        incoming_messages = None
        """
            All messages waiting to be sent from the IRC to Discord.
        """

        configuration = None
        """
            The configuration associated with this discord bridge.
        """

        discord_to_irc = None
        """
            A dictionary mapping discord channels to IRC channel names and their hosts.
        """

        irc_to_discord = None
        """
            A dictionary mapping IRC channels to discord channel names.
        """

        should_run = None
        """
            Whether or not this thread should continue to run.
        """

        loop = None
        """
            The asyncio event loop in use for this thread.
        """

        discord_connection = None
        """
            The discord connection in use for this thread.
        """

        def __init__(self, configuration):
            super(Addon.DiscordThread, self).__init__()

            self.configuration = configuration
            self.outgoing_lock = threading.Lock()
            self.outgoing_messages = []

            self.incoming_lock = threading.Lock()
            self.incoming_messages = []

            # Process the mappings block to determine IRC <-> Discord mappings
            self.discord_to_irc = {}
            self.irc_to_discord = {}

            self.should_run = True

            # Initialize the discord mappings
            for mapping_data in self.configuration["mappings"]:
                for irc_channel in mapping_data["ircchannels"]:
                    self.irc_to_discord.setdefault(irc_channel, [])
                    self.irc_to_discord[irc_channel] += mapping_data["discordchannels"]

        def run(self):
            """
                The thread function. This represents a new thread of execution.
            """
            while self.should_run is True:
                if self.discord_connection is not None:
                    self.discord_connection.logout()
                    print("!!! Attempting to reconnect.")

                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

                self.discord_connection = discord.Client()

                @self.discord_connection.event
                @asyncio.coroutine
                def on_message(message):
                    if message.type is discord.MessageType.default:
                        self.outgoing_lock.acquire()
                        self.outgoing_messages.append(message)
                        self.outgoing_lock.release()

                try:
                    self.discord_connection.loop.create_task(self.process_input_messages())
                    self.discord_connection.run(self.configuration["token"])
                except Exception as e:
                    print("!!! Discord connection threw an exception: %s" % str(e))

        @asyncio.coroutine
        def process_input_messages(self):
            yield from self.discord_connection.wait_until_ready()

            while self.discord_connection.is_closed is False:
                self.incoming_lock.acquire()

                queued_calls = []
                for irc_channels, message in self.incoming_messages:
                    irc_channels = [irc_channels] if type(irc_channels) is not list and irc_channels is not None else irc_channels

                    if irc_channels is None:
                        for recipient_discord_channels in self.irc_to_discord.values():
                            recipient_discord_channels = [discord_channel for discord_channel in self.discord_connection.get_all_channels()
                            if discord_channel.name in recipient_discord_channels or int(discord_channel.id) in recipient_discord_channels]

                            for recipient_discord_channel in recipient_discord_channels:
                                queued_calls.append(self.discord_connection.send_message(recipient_discord_channel, message))
                    else:
                        discord_channels = self.discord_connection.get_all_channels()
                        recipient_discord_channels = []

                        for irc_channel in irc_channels:
                            for channel in discord_channels:
                                if irc_channel in self.irc_to_discord and channel.name in self.irc_to_discord[irc_channel] or int(channel.id) in self.irc_to_discord[irc_channel]:
                                    recipient_discord_channels.append(channel)

                            for recipient_discord_channel in recipient_discord_channels:
                                queued_calls.append(self.discord_connection.send_message(recipient_discord_channel, message))

                self.incoming_messages = []
                self.incoming_lock.release()

                for queued_call in queued_calls:
                    yield from queued_call
                yield from asyncio.sleep(0.02)

        def stop(self):
            """
                Stops the Discord thread. This will disconnect from discord before terminating the running
                thread.
            """
            self.should_run = False
            discord.compat.create_task(self._disconnect_discord(), loop=self.loop)

            # Wait for the thread to die
            self.loop.stop()
            while self.is_alive() is True:
                time.sleep(0.01)

        @asyncio.coroutine
        def _disconnect_discord(self):
            """
                Internal function used to attempt total cleanup of the discord connection in the event
                an error is encountered.
            """
            queued_calls = [self.discord_connection.logout(), self.discord_connection.close()]
            discord.compat.create_task(asyncio.wait(queued_calls))

    def __init__(self, server_configurations, configuration):
        self.connections = []
        self.configuration = configuration

        self.discord_user_color_maps = {}

    def stop(self):
        """
            Stops the addon.
        """
        self.discord_thread.stop()

    def start(self):
        """
            Starts the addon after it has been initialized and all connections associated. This is called after
            all connections have been created.
        """
        self.initialize_discord_connection()

    def initialize_discord_connection(self):
        """
            Initializes the connection to discord.
        """
        self.discord_thread = Addon.DiscordThread(self.configuration)

        # Initialize the IRC mappings
        for mapping_data in self.configuration["mappings"]:
            irc_host = mapping_data["irchost"]

            # Locate the connection object on this host
            connection = [connection for connection in self.connections if connection.host == irc_host]
            if len(connection) != 1:
                raise Exception("!!! Cannot start Discord bridge. Invalid IRC host!")

            for discord_channel in mapping_data["discordchannels"]:
                self.discord_thread.discord_to_irc.setdefault(discord_channel, [])
                self.discord_thread.discord_to_irc[discord_channel].append((mapping_data["ircchannels"], connection))

        self.discord_thread.start()

    def register_connection(self, connection):
        """
            Registers this addon with the given IRC connection.

            :param connection: The IRC connection we are being associated with.
        """
        self.connections.append(connection)
        connection.bind_event("OnReceive", self.on_receive)
        connection.bind_event("OnJoin", self.on_join)
        connection.bind_event("OnPart", self.on_part)
        connection.bind_event("OnUsernameChange", self.on_username_change)
        connection.bind_event("OnReceivePose", self.on_receive_pose)
        connection.bind_event("OnQuit", self.on_quit)

    def update(self, delta_time):
        """
            Process an update tick.

            :param delta_time: The time since the last time addon updates were processed.
        """

        # Ensure that the thread is still running. If for some reason it exploded, reconnect.
        if self.discord_thread.is_alive() is False:
            print("!!! Discord thread has died. Reinitializing.")
            self.initialize_discord_connection()

        self.discord_thread.outgoing_lock.acquire()

        for message in self.discord_thread.outgoing_messages:
            author = message.author.name.rsplit("#", 1)[0].rstrip().lstrip()

            if author not in self.configuration["discordblacklist"]:
                message_content = message.clean_content
                message_content = message_content.rstrip().lstrip()
                message_content = message_content if len(message_content) != 0 else "(No Message)"

                # If the content is empty, process attachments.
                attachments_content = ""
                if len(message.attachments) != 0:
                    attachments_content = "(Attachments: %s ): " % " ".join([attachment["url"] for attachment in message.attachments])

                # Produce the replacements before altering the string we are searching
                while True:
                    generated_replacements = {}
                    for discord_pattern, irc_patterns in zip(self.DISCORD_TO_IRC_FORMATS.keys(), self.DISCORD_TO_IRC_FORMATS.values()):
                        for match in re.finditer(discord_pattern, message_content):
                            """
                                We need to perform processing for locating URL's in our matching sequences so the underscore characters
                                aren't formatted into IRC URL's and screwing them.
                            """
                            match_start = match.start()
                            http_location = message_content.rfind("http://", None, match_start)
                            https_location = message_content.rfind("https://", None, match_start)

                            hypertext_start = None
                            if http_location != -1:
                                hypertext_start = http_location
                            elif https_location != -1:
                                hypertext_start = https_location

                            # If there is a found hypertext, check if there is any spaces
                            if hypertext_start is not None:
                                potential_url = message_content[hypertext_start:match.end()]
                                if " " not in potential_url:
                                    continue

                            irc_pattern_index = len(match.group(1)) - 1
                            generated_replacements[match.group(0)] = irc_patterns[irc_pattern_index] % match.group(2)

                    if len(generated_replacements) == 0:
                        break

                    # Generate the final output message
                    for replaced_value, new_value in zip(generated_replacements.keys(), generated_replacements.values()):
                        message_content = message_content.replace(replaced_value, new_value)

                mapping_channel_name = message.channel.name in self.discord_thread.discord_to_irc
                mapping_channel_id = int(message.channel.id) in self.discord_thread.discord_to_irc

                if mapping_channel_name or mapping_channel_id:
                    mapped_channels = self.discord_thread.discord_to_irc[message.channel.name] if mapping_channel_name else self.discord_thread.discord_to_irc[int(message.channel.id)]

                    # Determine the color for this user.
                    user_color = None
                    if self.configuration["enableirccolors"]:
                        user_color = "%02d" % random.randint(2,15)
                        if author in self.discord_user_color_maps:
                            user_color = self.discord_user_color_maps[author]
                        else:
                            self.discord_user_color_maps[author] = user_color

                    # Insert a zero width character into the output to prevent toggling of name references
                    old_author = author
                    author = old_author[0] + "\u200B"
                    if len(old_author) > 1:
                        author = author + old_author[1:]

                    if user_color is not None:
                        formatted_message = "\x02<\x03%s%s\x03>\x02 %s %s" % (user_color, author, attachments_content, message_content)
                    else:
                        formatted_message = "\x02<%s>\x02 %s %s" % (author, attachments_content, message_content)

                    for recipient_irc_channels, connections in mapped_channels:
                        for recipient_irc_channel in recipient_irc_channels:
                            for recipient_connection in connections:
                                recipient_connection.say(formatted_message, recipient_irc_channel)

        self.discord_thread.outgoing_messages = []
        self.discord_thread.outgoing_lock.release()

    def get_commands(self):
        return {}

    def on_username_change(self, old_username, new_username, hostmask, channels):
        """
            Event handler for when people change their usernames in the IRC.

            :param old_username: The username that was transferred from.
            :param new_username: The username that was transferred to.
            :param hostmask: The hostmask.
        """
        if self.configuration["dispatchusernamechanges"] is False or old_username in self.configuration["ircblacklist"] or new_username in self.configuration["ircblacklist"]:
            return

        self.discord_thread.incoming_lock.acquire()
        self.discord_thread.incoming_messages.append((channels, "**%s** changed their nickname to **%s**." % (old_username, new_username)))
        self.discord_thread.incoming_lock.release()

    def on_join(self, username, hostmask, channel):
        """
            Event handler for when people join an IRC channel that the bot is in.

            :param username: The username of the person connecting.
            :param hostmask: The hostmask.
            :param channel: The name of the channel they joined.
        """
        if self.configuration["dispatchjoinevents"] is False or username in self.configuration["ircblacklist"]:
            return

        self.discord_thread.incoming_lock.acquire()
        self.discord_thread.incoming_messages.append((channel, "**%s** joined #%s." % (username, channel)))
        self.discord_thread.incoming_lock.release()

    def on_part(self, username, hostmask, message, channel):
        """
            Event handler for when people part from an IRC channel the bot is in.

            :param username: The username of the person connecting.
            :param hostmask: The hostmask.
            :param message: The part message.
            :param channel: The name of the channel they joined.
        """
        if self.configuration["dispatchpartevents"] is False or username in self.configuration["ircblacklist"]:
            return

        self.discord_thread.incoming_lock.acquire()
        message = message.lstrip().rstrip()
        message = ": %s" % message if len(message) != 0 else ""
        self.discord_thread.incoming_messages.append((channel, "**%s** left #%s%s" % (username, channel, message)))
        self.discord_thread.incoming_lock.release()

    def on_receive_pose(self, username, message, channel):
        """
            Event handler for when people use the ACTION command in IRC.

            :param username: The username of the person connecting.
            :param message: The pose message.
            :param channel: The name of the channel they sent the message to.
        """
        if self.configuration["dispatchmessages"] is False or username in self.configuration["ircblacklist"]:
            return

        self.discord_thread.incoming_lock.acquire()
        self.discord_thread.incoming_messages.append((channel, "**<%s>** _%s_" % (username, message)))
        self.discord_thread.incoming_lock.release()

    def on_quit(self, username, message, hostmask, channels):
        """
            Event handler for when people leave the IRC server.

            :param username: The username of the person quitting.
            :param message: The quit message.
            :param hostmask: The hostmask.
        """
        if self.configuration["dispatchquitevents"] is False or username in self.configuration["ircblacklist"]:
            return

        self.discord_thread.incoming_lock.acquire()
        message = message.lstrip().rstrip()
        message = ": %s" % message if len(message) != 0 else "."
        self.discord_thread.incoming_messages.append((channels, "**%s** left the IRC server%s" % (username, message)))
        self.discord_thread.incoming_lock.release()

    def on_receive(self, username, message, channel):
        """
            Event handler for when the bot receives a message from the IRC as a channel message.

            :param username: The username of the user sending the message.
            :param message: The message that was sent.
            :param channel: The name of the channel the message was sent to.
        """
        if self.configuration["dispatchmessages"] is False or username in self.configuration["ircblacklist"]:
            return

        self.discord_thread.incoming_lock.acquire()
        self.discord_thread.incoming_messages.append((channel, "**<%s>** %s" % (username, message)))
        self.discord_thread.incoming_lock.release()
