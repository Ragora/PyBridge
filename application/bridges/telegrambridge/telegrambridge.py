"""
    discordbridge.py

    Code to provide discord IRC bridging.
"""

import os
import re
import sys
import time
import random
import socket
import asyncio
import datetime
import threading
import tempfile
import magic
import collections
import mimetypes

import telegram

from PIL import Image
from bridgesystem import BridgeBase

class Bridge(BridgeBase):
    connection = None
    """
        The telegram bot connection.
    """

    most_recent_update_id = None
    """
        The identifier of the most recent update.
    """

    chat_mapping = None
    """
        A mapping of chat channel names to ID's.
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

        self.register_event("on_receive_message", self.on_receive_message)
        self.register_event("on_receive_pose", self.on_receive_pose)
        self.register_event("on_receive_leave", self.on_receive_leave)
        self.register_event("on_receive_join", self.on_receive_join)
        self.connection = telegram.Bot(token=self.configuration.bridge_internal_config["token"])

        self.chat_mapping = self.configuration.bridge_internal_config["chatMapping"]

    def on_receive_join(self, sender, joined_name, target_channels):
        for channel in target_channels:
            if channel in self.chat_mapping.keys():
                for chat_id in self.chat_mapping[channel]:
                    generated_message = "<%s: %s> joined %s" % (sender.configuration.name, joined_name, ", ".join(target_channels))
                    self.connection.send_message(text=generated_message, chat_id=chat_id)

    def on_receive_leave(self, sender, left_name, target_channels):
        for channel in target_channels:
            if channel in self.chat_mapping.keys():
                for chat_id in self.chat_mapping[channel]:
                    generated_message = "<%s: %s> left %s" % (sender.configuration.name, left_name, ", ".join(target_channels))
                    self.connection.send_message(text=generated_message, chat_id=chat_id)

    def send(self, sender, message, target_channels):
        for channel in target_channels:
            if channel in self.chat_mapping.keys():
                for chat_id in self.chat_mapping[channel]:
                    self.connection.send_message(text=message, chat_id=chat_id)

    def on_receive_message(self, sender, sender_name, message, target_channels):
        if sender_name not in self.configuration.bridge_generic_config.ignore_senders:
            generated_message = "<%s: %s> %s" % (sender.configuration.name, sender_name, message)
            self.send_buffered_message(sender=sender_name, target_channels=target_channels, message=generated_message, buffer_size=4000, send_function=self.send)

    def on_receive_pose(self, sender, sender_name, message, target_channels):
        if sender_name not in self.configuration.bridge_generic_config.ignore_senders:
            generated_message = "<%s: %s> _%s_" % (sender.configuration.name, sender_name, message)
            self.send_buffered_message(sender=sender_name, target_channels=target_channels, message=generated_message, buffer_size=4000, send_function=self.send)

    def register_connection(self, connection):
        """
            Registers this addon with the given IRC connection.

            :param connection: The IRC connection we are being associated with.
        """

    def get_most_recent_update(self, updates):
        most_recent = None
        for update in updates:
            if update.message is not None:
                if most_recent is None:
                    most_recent = update
                elif update.message.date > most_recent.message.date:
                    most_recent = update
        return most_recent

    def get_channel_from_identifier(self, identifier):
        for channel_name, identifiers in zip(self.chat_mapping.keys(), self.chat_mapping.values()):
            if identifier in identifiers:
                return channel_name
        return None

    def update(self, delta_time):
        """
            Process an update tick.

            :param delta_time: The time since the last time addon updates were processed.
        """

        super(Bridge, self).update(delta_time)

        try:
            updates = self.connection.get_updates(offset=self.most_recent_update_id)

            if self.most_recent_update_id is None:
                readback_time = datetime.datetime.now() + datetime.timedelta(seconds=10)
                most_recent_update = self.get_most_recent_update(updates)

                if most_recent_update is not None:
                    self.most_recent_update_id = most_recent_update.update_id
                updates = [update for update in updates if update.message is not None and update.message.date >= readback_time]
            else:
                updates = [update for update in updates if update.update_id != self.most_recent_update_id]

            # Group by channels
            chat_updates = {}
            for update in updates:
                if update.message is not None:
                    chat_identifier = update.message.chat_id
                    chat_updates.setdefault(chat_identifier, [])
                    chat_updates[chat_identifier].append(update)

            # Record the most recent ipdate ID
            most_recent_update = self.get_most_recent_update(updates)
            if most_recent_update is not None:
                self.most_recent_update_id = most_recent_update.update_id

            # Process all of the channel messages now
            for chat_identifier, updates in zip(chat_updates.keys(), chat_updates.values()):
                # Look up the channel name
                channel_name = self.get_channel_from_identifier(chat_identifier)
                if channel_name is None or channel_name not in self.configuration.bridge_generic_config.broadcasting_channels:
                    continue

                for update in updates:
                    message_text = "(No Comment)" if update.message.text is None else update.message.text

                    # Download the file if necessary.
                    if self.global_configuration.global_configuration.image_hosting.enabled:
                        file_id = None
                        mime_type = None
                        image_type = None

                        if update.message.sticker is not None:
                            image_type = "Telegram Sticker"
                            file_id = update.message.sticker.file_id
                        elif update.message.photo is not None and len(update.message.photo) != 0:
                            image_type = "Telegram Photo"
                            largest_photo = update.message.photo[0]
                            for photo_size in update.message.photo:
                                if photo_size.width >= largest_photo.width and photo_size.height >= largest_photo.height:
                                    largest_photo = photo_size
                            file_id = largest_photo.file_id
                        elif update.message.video is not None:
                            image_type = "Telegram Video"
                            file_id = update.message.video.file_id
                        elif update.message.document is not None:
                            image_type = "Telegram Document"
                            file_id = update.message.document.file_id
                        elif update.message.audio is not None:
                            image_type = "Telegram Audio"
                            file_id = update.message.audio.file_id

                        # Handle the image hosting. FIXME: Handle re-generation of URL's from stuff already on file.
                        if file_id is not None:
                            handle = self.connection.get_file(file_id=file_id)
                            _, temp_path = tempfile.mkstemp()
                            handle.download(custom_path=temp_path)

                            mime_type = magic.Magic(mime=True).from_file(temp_path)

                            # Handle stickers specifically for now.
                            if update.message.sticker is not None:
                                generated_name = self.get_hosted_image_from_path(temp_path, extension=".png")
                                generated_url = self.get_hosted_image_url(generated_name)
                                message_text = "(%s %s ): %s" % (image_type, generated_url, "No Caption" if update.message.caption is None else update.message.caption)
                            else:
                                if mime_type is not None:
                                    extension = mimetypes.guess_extension(mime_type)

                                    if extension is None:
                                        os.remove(temp_path)
                                        message_text = "(%s Failed to generate URL: Failed to determine file type): %s" % (image_type, "No Caption" if update.message.caption is None else update.message.caption)
                                    else:
                                        generated_name = self.get_hosted_image_from_path(temp_path, extension=extension)
                                        generated_url = self.get_hosted_image_url(generated_name)
                                        message_text = "(%s %s ): %s" % (image_type, generated_url, "No Caption" if update.message.caption is None else update.message.caption)
                                else:
                                    os.remove(temp_path)
                                    message_text = "(%s Failed to generate URL: No MIME type Specified): %s" % (image_type, "No Caption" if update.message.caption is None else update.message.caption)

                    if self.configuration.bridge_generic_config.broadcast_messages:
                        self.application.broadcast_event("on_receive_message",
                        sender=self,
                        sender_name=update.message.from_user.username,
                        message=message_text,
                        target_channels=[channel_name])
        except telegram.error.TimedOut as e:
            pass

    def get_commands(self):
        return {}
