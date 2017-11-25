"""
    Python programming to provide Discord service bridging.
"""

import os
import re
import sys
import time
import random
import pathlib
import asyncio
import tempfile
import http.client
import threading
import collections
from urllib.parse import urlparse
from urllib.request import urlretrieve

import discord

from PIL import Image

from .user import User
from .channel import Channel
from .message import Message
from bridgesystem import BridgeBase, util


class Bridge(BridgeBase):
    """
        A class representing the Discord bridge.
    """

    configuration = None
    """
        The configuration associated with this addon.
    """

    discord_thread = None
    """
        The discord thread running the discord connection.
    """

    user_instances = None
    """
        A dictionary mapping user identifiers to their UserBase instance.
    """

    channel_instances = None
    """
        A dictionary mapping channel identifiers to their ChannelBase instance.
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

        logger = None

        def __init__(self, logger, configuration):
            """
                Initializes a new DiscordThread instance.
            """
            super(Bridge.DiscordThread, self).__init__()

            self.logger = logger
            self.configuration = configuration
            self.outgoing_lock = threading.Lock()
            self.outgoing_messages = []

            self.incoming_lock = threading.Lock()
            self.incoming_messages = []

            self.should_run = True
            self.daemon = True

        def run(self):
            """
                The thread function. This represents a new thread of execution.
            """
            while self.should_run is True:
                if self.discord_connection is not None:
                    self.discord_connection.logout()
                    self.logger.info("Attempting to reconnect.")

                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

                self.discord_connection = discord.Client()

                # Only process incoming messages if the configuration allows for it
                if self.configuration.bridge_generic_config.broadcast_messages:
                    @self.discord_connection.event
                    @asyncio.coroutine
                    def on_message(message):
                        if message.type is discord.MessageType.default:
                            self.outgoing_lock.acquire()
                            self.outgoing_messages.append(message)
                            self.outgoing_lock.release()

                try:
                    self.discord_connection.loop.create_task(self.process_input_messages())
                    self.discord_connection.run(self.configuration.bridge_internal_config["token"])
                except Exception as e:
                    self.logger.error("!!! Discord connection threw an exception: %s" % str(e))

        @asyncio.coroutine
        def process_input_messages(self):
            """
                A couroutine used for processing input messages to be sent to Discord.
            """
            yield from self.discord_connection.wait_until_ready()

            while self.discord_connection.is_closed is False:
                self.incoming_lock.acquire()

                queued_calls = []
                discord_channels = self.discord_connection.get_all_channels()
                discord_channels = {channel.name: channel for channel in discord_channels}

                for recipient_channels, message in self.incoming_messages:
                    if hasattr(recipient_channels, "__iter__") is False:
                        recipient_channels = [recipient_channels]

                    for recipient_channel in recipient_channels:
                        if recipient_channel in discord_channels:
                            # FIXME: If not found, report an error.
                            recipient_channel = discord_channels[recipient_channel]
                            queued_calls.append(self.discord_connection.send_message(recipient_channel, message))

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

    def __init__(self, application, logger, home_path, configuration, global_configuration, event_handler):
        """
            Initializes a new Bridge instance.

            :param application: The main application object.
            :param logger: The logger object for this bridge.
            :param home_path: The home path.
            :param configuration: The configuration data for this bridge.
            :param global_configuration: The global configuration data for the bot.
        """
        super(Bridge, self).__init__(application, logger, home_path, configuration, global_configuration, event_handler=event_handler)
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

        self.user_instances = {}
        self.channel_instances = {}

        self.event_handler.register_event(self.event_handler.Events.OnReceivePose, self.on_receive_pose)
        self.event_handler.register_event(self.event_handler.Events.OnReceiveJoin, self.on_receive_join)
        self.event_handler.register_event(self.event_handler.Events.OnReceiveLeave, self.on_receive_leave)
        self.event_handler.register_event(self.event_handler.Events.OnReceiveMessage, self.on_receive_message)

        self.initialize_discord_connection()

    def initialize_discord_connection(self):
        """
            Initializes the connection to discord.
        """
        if self.discord_thread in self.threads:
            self.threads.remove(self.discord_thread)

        self.discord_thread = Bridge.DiscordThread(self.logger, self.configuration)
        self.discord_thread.start()
        self.threads.append(self.discord_thread)

    def register_addon(self, application):
        """
            Registers this addon with the given IRC connection.

            :param connection: The IRC connection we are being associated with.
        """

    def register_user(self, user):
        """
            Registers user objects with the discord bridge.

            :param user: The Discord user object.

            :rtype: UserBase
            :return: A UserBase object wrapping the Discord user.
        """
        if user.id in self.user_instances.keys():
            return self.user_instances[user.id]

        user_instance = User(connection=self.discord_thread.discord_connection, user_instance=user, event_loop=self.discord_thread.loop)
        self.user_instances[user.id] = user_instance
        return user_instance

    def register_channel(self, channel):
        """
            Registers channel objects with the discord bridge.

            :param channel: The Discord channel object.

            :rtype: ChannelBase
            :return: A ChannelBase object wrapping the Discord channel.
        """
        if channel.id in self.channel_instances.keys():
            return self.channel_instances[channel.id]

        channel_instance = Channel(connection=self.discord_thread.discord_connection, event_loop=self.discord_thread.loop, channel_instance=channel)
        self.channel_instances[channel.id] = channel_instance
        return channel_instance

    def update(self, delta_time):
        """
            Process an update tick.

            :param delta_time: The time since the last time addon updates were processed.
        """

        super(Bridge, self).update(delta_time)

        # Ensure that the thread is still running. If for some reason it exploded, reconnect.
        if self.discord_thread.is_alive() is False:
            self.logger.error("!!! Discord thread has died. Reinitializing.")
            self.initialize_discord_connection()

        self.discord_thread.outgoing_lock.acquire()
        for message in self.discord_thread.outgoing_messages:
            author = message.author.name.rsplit("#", 1)[0].rstrip().lstrip()

            message_content = message.clean_content
            if len(message.attachments) != 0:
                message_content = "No Comment" if message_content is None or len(message_content) == 0 else message_content

                if self.global_configuration.global_configuration.image_hosting.enabled:
                    generated_urls = []
                    for attachment in message.attachments:
                        parsed_url = urlparse(attachment["url"])
                        connection = http.client.HTTPSConnection(parsed_url.netloc)
                        connection.request("GET", parsed_url.path, headers={
                            "authority": parsed_url.netloc,
                            "path": parsed_url.path,
                            "scheme": "https",
                            "accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                            "accept-encoding": "gzip, deflate, br",
                            "accept-language": "en-US,en;q=0.8",
                            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36"
                        })

                        # Get the response and save it
                        response = connection.getresponse()
                        response_data = response.read()
                        _, temp_path = tempfile.mkstemp()
                        with open(temp_path, "wb") as handle:
                            handle.write(response_data)

                        # Attmept to convert it.
                        try:
                            image_handle = Image.open(temp_path)
                            image_handle.save(temp_path, "PNG")
                            image_handle.close()

                            generated_name = self.get_hosted_image_from_path(temp_path, extension=".png")
                            generated_urls.append(self.get_hosted_image_url(generated_name))
                        except OSError as e:
                            os.remove(temp_path)
                            generated_urls.append("Failed to generate URL: %s" % str(e))

                    message_content = "(Discord Attachment: %s): %s" % (message_content, "\n".join(generated_urls))
                else:
                    message_content = "(Discord Attachment: %s): %s" % (message_content, "\n".join([attachment["url"] for attachment in message.attachments]))

            if self.configuration.bridge_generic_config.broadcast_messages and author not in self.configuration.bridge_generic_config.ignore_senders:
                channel = None
                user = self.register_user(user=message.author)

                if message.channel.type != discord.enums.ChannelType.private:
                    channel = self.register_channel(channel=message.channel)
                message = Message(message_instance=message, sender=user, channels=channel, event_loop=self.discord_thread.loop, connection=self.discord_thread.discord_connection)

                if channel is not None:
                    self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveMessage, emitter=self, message=message)
                else:
                    self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveMessagePrivate, emitter=self, message=message)

        self.discord_thread.outgoing_messages = []
        self.discord_thread.outgoing_lock.release()

    def send(self, sender, message, target_channels):
        if sender is self:
            return

        self.discord_thread.incoming_lock.acquire()
        self.discord_thread.incoming_messages.append((target_channels, message))
        self.discord_thread.incoming_lock.release()

    def on_receive_pose(self, emitter, message):
        """
            Callback that is raised when the bridge receives a pose in a channel.

            :param emitter: The emitting bridge instance.
            :param message: The MessageBase instance representing the message received.
        """
        if emitter is self:
            return

        if self.configuration.bridge_generic_config.receive_messages and message.sender.username not in self.configuration.bridge_generic_config.ignore_senders:
            message_text = "**<%s: %s>** _%s_" % (emitter.configuration.name, message.sender.username, message.raw_text)
            target_channels = [channel.name for channel in message.channels]
            self.send_buffered_message(sender=message.sender.username, target_channels=target_channels, message=message_text, buffer_size=1900, send_function=self.send)

    def on_receive_message(self, emitter, message):
        """
            A callback handler for when the bot receives a regular text message in a channel.

            :param emitter: The sending bridge.
            :param sender_name: The name of the sending client.
            :param message: The message that was sent.
            :param target_channels: The names of all channels this message was sent to.
        """
        if emitter is self:
            return

        if self.configuration.bridge_generic_config.receive_messages and message.sender.username not in self.configuration.bridge_generic_config.ignore_senders:
            message_text = "**<%s: %s>** %s" % (emitter.configuration.name, message.sender.username, message.raw_text)
            target_channels = [channel.name for channel in message.channels]
            self.send_buffered_message(sender=message.sender.username, target_channels=target_channels, message=message_text, buffer_size=1900, send_function=self.send)

    def on_receive_join(self, emitter, user, channels):
        """
            A callback handler for when the bot receives a join event.

            :param emitter: The sending bridge.
            :param user: The joining UserBase instance.
            :param channels: A list of ChannelBase instances representing the channels that the user joined.
        """
        if emitter is self:
            return

        if self.configuration.bridge_generic_config.receive_join_leaves and user.username not in self.configuration.bridge_generic_config.ignore_senders:
            self.discord_thread.incoming_lock.acquire()
            target_channels = [channel.name for channel in channels]
            self.discord_thread.incoming_messages.append((target_channels, "**<%s: %s>** joined %s." % (emitter.configuration.name, user.username, ", ".join(target_channels))))
            self.discord_thread.incoming_lock.release()

    def on_receive_leave(self, emitter, user, channels):
        """
            A callback handler for when the bot receives a leave event.
        """
        if emitter is self:
            return

        if self.configuration.bridge_generic_config.receive_join_leaves and user.username not in self.configuration.bridge_generic_config.ignore_senders:
            self.discord_thread.incoming_lock.acquire()
            target_channels = [channel.name for channel in channels]
            self.discord_thread.incoming_messages.append((target_channels, "**<%s: %s>** left %s." % (emitter.configuration.name, user.username, ", ".join(target_channels))))
            self.discord_thread.incoming_lock.release()
