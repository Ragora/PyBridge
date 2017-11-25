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
import tempfile
import magic
import collections
import mimetypes

import telegram

from .user import User
from .channel import Channel
from .message import Message

from PIL import Image
from bridgesystem import BridgeBase


class Bridge(BridgeBase):
    """
        A class representing the bridge to the Telegram service.
    """

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

    unmapped_chats = None
    """
        A list of chat identifiers that are unmapped in the configuration.
    """

    user_instances = None
    """
        A dictionary mapping user identifiers to the abstracted user instances.
    """

    channel_instances = None
    """
        A dictionary mapping channel identifiers to the abstracted channel instances.
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

        self.event_handler.register_event(self.event_handler.Events.OnReceiveMessage, self.on_receive_message)
        self.event_handler.register_event(self.event_handler.Events.OnReceivePose, self.on_receive_pose)
        self.event_handler.register_event(self.event_handler.Events.OnReceiveLeave, self.on_receive_leave)
        self.event_handler.register_event(self.event_handler.Events.OnReceiveJoin, self.on_receive_join)
        self.connection = telegram.Bot(token=self.configuration.bridge_internal_config["token"])

        self.unmapped_chats = []
        self.user_instances = {}

        # Initialize the chat mapping
        self.chat_mapping = self.configuration.bridge_internal_config["chatMapping"]
        self.chat_mapping = {name.lower(): identifier for name, identifier in zip(self.chat_mapping.keys(), self.chat_mapping.values())}

        # For now, the channel set is always static
        self.channel_instances = {}
        for identifiers in self.chat_mapping.values():
            for identifier in identifiers:
                chat_instance = self.connection.get_chat(chat_id=identifier)
                self.channel_instances[identifier] = Channel(connection=self.connection, chat_instance=chat_instance)

    def register_user(self, user_instance):
        if user_instance.id in self.user_instances.keys():
            return self.user_instances[user_instance.id]
        result = User(connection=self.connection, user_instance=user_instance)
        self.user_instances[user_instance.id] = result
        return result

    def on_receive_join(self, emitter, user, channels):
        """
            An event raised for when a user joins a channel.

            :param bridge: The bridge instance that raised the event.
            :param user: The user object that joined.
            :param channels: A list of channel instances for the channels the user joined.
        """
        if emitter is self:
            return None

        result = []
        for channel in channels:
            if channel.name in self.chat_mapping.keys():
                for chat_id in self.chat_mapping[channel.name]:
                    generated_message = "<%s: %s> joined %s" % (emitter.configuration.name, user.username, ", ".join([channel.name for channel in channels]))
                    result.append(self.channel_instances[chat_id].send_message(generated_message))
        return result

    def on_receive_leave(self, emitter, user, channels):
        """
            An event raised for when a user leaves a channel.

            :param bridge: The bridge instance that raised the event.
            :param user: The user object that left.
            :param channels: A list of channel instances for the channels the user left.
        """
        if emitter is self:
            return None

        result = []
        for channel in channels:
            if channel.name in self.chat_mapping.keys():
                for chat_id in self.chat_mapping[channel.name]:
                    generated_message = "<%s: %s> left %s" % (emitter.configuration.name, user.username, ", ".join([channel.name for channel in channels]))
                    result.append(self.channel_instances[chat_id].send_message(generated_message))
        return result

    def send(self, sender, message, target_channels):
        """
            Sends a message to the telegram service.
        """
        if sender is self:
            return

        for channel in target_channels:
            if channel in self.chat_mapping.keys():
                for chat_id in self.chat_mapping[channel]:
                    self.connection.send_message(text=message, chat_id=chat_id)

    def on_receive_message(self, emitter, message):
        """
            An event raised for when a user sends a message to a channel the bot is in.

            :param bridge: The bridge instance that raised the event.
            :param message: The MessageBase instance representing the sent message.

            :rtype: MessageBase
            :return: A MessageBase instance representing the mirror message.
        """
        if emitter is self:
            return None

        if message.sender.username not in self.configuration.bridge_generic_config.ignore_senders:
            generated_message = "<%s: %s> %s" % (emitter.configuration.name, message.sender.username, message.raw_text)
            target_channels = [channel.name.lower() for channel in message.channels]
            self.send_buffered_message(sender=message.sender.username, target_channels=target_channels, message=generated_message, buffer_size=4000, send_function=self.send)
        return None

    def on_receive_pose(self, emitter, message):
        """
            An event raised for when a user sends a pose to a channel the bot is in.

            :param bridge: The bridge instance that raised the event.
            :param message: The MessageBase instance representing the sent pose.

            :rtype: MessageBase
            :return: A MessageBase instance representing the mirror pose.
        """
        if emitter is self:
            return None

        if message.sender.username not in self.configuration.bridge_generic_config.ignore_senders:
            generated_message = "<%s: %s> _%s_" % (emitter.configuration.name, message.sender.username, message.raw_text)
            target_channels = [channel.name.lower() for channel in message.channels]
            self.send_buffered_message(sender=message.sender.username, target_channels=target_channels, message=generated_message, buffer_size=4000, send_function=self.send)
        return None

    def register_connection(self, connection):
        """
            Registers this addon with the given IRC connection.

            :param connection: The IRC connection we are being associated with.
        """

    def get_most_recent_update(self, updates):
        """
            Retrieves the most recent update out of the given set of updates.

            :param updates: A list of update objects received from the Telegram server.

            :rtype: None, Update
            :return: The most recent update out of the set. None if there isn't one.
        """
        most_recent = None
        for update in updates:
            if update.message is not None:
                if most_recent is None:
                    most_recent = update
                elif update.message.date > most_recent.message.date:
                    most_recent = update
        return most_recent

    def get_channel_from_identifier(self, identifier):
        """
            Gets the channel from the given identifier.

            :param identifier: The Telegram channel identifier.
        """
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

            # Record the most recent update ID
            most_recent_update = self.get_most_recent_update(updates)
            if most_recent_update is not None:
                self.most_recent_update_id = most_recent_update.update_id

            # Process all of the channel messages now
            for chat_identifier, updates in zip(chat_updates.keys(), chat_updates.values()):
                # Look up the channel name
                channel_name = self.get_channel_from_identifier(chat_identifier)

                # If the chat is unknown, remember it and report an error
                chat_object = self.connection.get_chat(chat_id=chat_identifier)
                if channel_name is None and chat_identifier not in self.unmapped_chats:
                    chat_object = self.connection.get_chat(chat_id=chat_identifier)

                    # Private chats are always unmapped, or should be anyway.
                    if chat_object.type != "private":
                        self.unmapped_chats.append(chat_identifier)
                        self.logger.error("Found unmapped chat ID %s: '%s'. Is your channel map in your configuration correct?" % (chat_identifier, chat_object.title if chat_object.title is not None else "(No Chat Title)"))
                    else:
                        sender = self.register_user(update.message.from_user)
                        message = Message(connection=self.connection, sender=sender, message_instance=update.message, channels=None)
                        self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveMessagePrivate, emitter=self, message=message)

                if channel_name is None or channel_name not in self.configuration.bridge_generic_config.broadcasting_channels:
                    continue

                for update in updates:
                    message_text = "(No Comment)" if update.message.text is None else update.message.text

                    # Download the file if necessary.
                    if self.global_configuration.global_configuration.image_hosting.enabled:
                        file_id = None
                        mime_type = None
                        image_type = None

                        """
                        new_chat_members (List[:class:`telegram.User`]): Optional. Information about new members to
                            the chat. (the bot itself may be one of these members).
                        left_chat_member (:class:`telegram.User`): Optional. Information about the user that left
                            the group. (this member may be the bot itself).
                        forward_from (:class:`telegram.User`): Optional. Sender of the original message.
                        forward_from_chat (:class:`telegram.Chat`): Optional. Information about the original
                            channel.
                        forward_from_message_id (:obj:`int`): Optional. Identifier of the original message in the
                            channel.
                        forward_date (:class:`datetime.datetime`): Optional. Date the original message was sent.
                        pinned_message (:class:`telegram.message`): Optional. Specified message was pinned.
                        """

                        sender_name = update.message.from_user.username
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
                        elif update.message.new_chat_members is not None and len(update.message.new_chat_members) != 0:
                            message_text = "Telegram Users Joined: %s" % ", ".join([user.username for user in update.message.new_chat_members])
                            sender_name = "System"
                        elif update.message.left_chat_member is not None:
                            message_text = "Telegram Users Left: %s" % update.message.left_chat_member.username
                            sender_name = "System"

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

                    # Dispatch the message
                    if self.configuration.bridge_generic_config.broadcast_messages:
                        sender = self.register_user(update.message.from_user)
                        message = Message(connection=self.connection, sender=sender, message_instance=update.message, channels=self.channel_instances[chat_identifier])
                        self.event_handler.broadcast_event(self.event_handler.Events.OnReceiveMessage, emitter=self, message=message)
        except telegram.error.TimedOut as e:
            pass
