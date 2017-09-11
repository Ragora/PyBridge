"""
    discordbridge.py

    Code to provide discord IRC bridging.
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
from bridgesystem import BridgeBase, util

class Bridge(BridgeBase):
    configuration = None
    """
        The configuration associated with this addon.
    """

    discord_thread = None
    """
        The discord thread running the discord connection.
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

        def __init__(self, configuration):
            super(Bridge.DiscordThread, self).__init__()

            self.configuration = configuration
            self.outgoing_lock = threading.Lock()
            self.outgoing_messages = []

            self.incoming_lock = threading.Lock()
            self.incoming_messages = []

            self.should_run = True

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
                    print("!!! Discord connection threw an exception: %s" % str(e))

        @asyncio.coroutine
        def process_input_messages(self):
            yield from self.discord_connection.wait_until_ready()

            while self.discord_connection.is_closed is False:
                self.incoming_lock.acquire()

                queued_calls = []
                discord_channels = self.discord_connection.get_all_channels()
                discord_channels = {channel.name: channel for channel in discord_channels}

                for recipient_channels, message in self.incoming_messages:
                    if type(recipient_channels) is not list:
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

    def __init__(self, application, home_path, configuration, global_configuration):
        super(Bridge, self).__init__(application, home_path, configuration, global_configuration)

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

        self.register_event("on_receive_message", self.on_receive_message)
        self.register_event("on_receive_join", self.on_receive_join)
        self.register_event("on_receive_leave", self.on_receive_leave)

        self.initialize_discord_connection()

    def initialize_discord_connection(self):
        """
            Initializes the connection to discord.
        """
        self.discord_thread = Bridge.DiscordThread(self.configuration)
        self.discord_thread.start()

    def register_addon(self, application):
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

        # Ensure that the thread is still running. If for some reason it exploded, reconnect.
        if self.discord_thread.is_alive() is False:
            print("!!! Discord thread has died. Reinitializing.")
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
                self.application.broadcast_event("on_receive_message",
                sender=self,
                sender_name=author,
                message=message_content,
                target_channels=[message.channel.name])

        self.discord_thread.outgoing_messages = []
        self.discord_thread.outgoing_lock.release()

    def get_commands(self):
        return {}

    def send(self, sender, message, target_channels):
        self.discord_thread.incoming_lock.acquire()
        self.discord_thread.incoming_messages.append((target_channels, message))
        self.discord_thread.incoming_lock.release()

    def on_receive_message(self, sender, sender_name, message, target_channels):
        if self.configuration.bridge_generic_config.receive_messages and sender_name not in self.configuration.bridge_generic_config.ignore_senders:
            message = "**<%s: %s>** %s" % (sender.configuration.name, sender_name, message)
            self.send_buffered_message(sender=sender_name, target_channels=target_channels, message=message, buffer_size=1900, send_function=self.send)

    def on_receive_join(self, sender, joined_name, target_channels):
        if self.configuration.bridge_generic_config.receive_join_leaves and joined_name not in self.configuration.bridge_generic_config.ignore_senders:
            self.discord_thread.incoming_lock.acquire()
            self.discord_thread.incoming_messages.append((target_channels, "**<%s: %s>** joined %s." % (sender.configuration.name, joined_name, ", ".join(target_channels))))
            self.discord_thread.incoming_lock.release()

    def on_receive_leave(self, sender, left_name, target_channels):
        if self.configuration.bridge_generic_config.receive_join_leaves and left_name not in self.configuration.bridge_generic_config.ignore_senders:
            self.discord_thread.incoming_lock.acquire()
            self.discord_thread.incoming_messages.append((target_channels, "**<%s: %s>** left %s." % (sender.configuration.name, left_name, ", ".join(target_channels))))
            self.discord_thread.incoming_lock.release()
