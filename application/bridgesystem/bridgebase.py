"""
    Base class for all bridges.
"""

import os
import base64
import random
import datetime
import inspect
import shutil

from bridgesystem import util

class AddonError(Exception):
    pass

class AddonMismatchedEventArgsError(AddonError):
    pass

class AddonConfigurationError(AddonError):
    pass

class BridgeBase(object):
    event_map = None
    """
        A dictionary mapping events to each other.
    """

    application = None
    """
        The main application instance we are associated with.
    """

    configuration = None
    """
        Addon specific configuration data.
    """

    long_block_buffers = None
    """
        A dictionary mapping message senders to their long block buffers.
    """

    last_long_block_process = None
    """
        The last times long blocks were processed.
    """

    global_configuration = None

    def __init__(self, application, configuration, global_configuration):
        """
            Base initialize function to create empty lambdas for the base event types. Events of other types may be specified,
            but these at the least should be defined for interoperability.

            :param configuration: The configuration data in use for this addon.
        """
        self.event_map = {}
        self.application = application
        self.configuration = configuration
        self.global_configuration = global_configuration

        self.long_block_buffers = {}
        self.last_long_block_process = {}

        self.register_event("on_receive_message", lambda sender, sender_name, message, target_channels: True)
        self.register_event("on_receive_join", lambda sender, joined_name, target_channels: True)
        self.register_event("on_receive_leave", lambda sender, left_name, target_channels: True)

    def receive_event(self, name, *args, **kwargs):
        """
            Raises an event within this addon.

            :param name: The name of the event to raise. If there is no event going by this name, nothing happens.
            :param *args: All positional args to pass to the events.
            :param kwargs: All key word args to pass to the events.
        """
        # Quietly do nothing because there isn't any responder for this.
        if name not in self.event_map:
            return

        for responder in self.event_map[name]:
            try:
                responder(*args, **kwargs)
            except StandardError as e:
                pass
                # FIXME: Process and log the error in some way.

    def register_event(self, name, responder):
        """
            Registers an event to be processed by this addon.
        """
        self.event_map.setdefault(name, [])

        # Verify that all functions have the same signature if we have any events defined already
        if len(self.event_map[name]) != 0:
            first_responder = self.event_map[name][0]

            responder_argument_count = responder.__code__.co_argcount
            if inspect.ismethod(responder):
                responder_argument_count -= 1

            if first_responder.__code__.co_argcount != responder_argument_count:
                raise AddonMismatchedEventArgsError("Attempted to register a responder to event '%s' using a function accepting %u parameters! Expected %u." % (name, responder.__code__.co_argcount, first_responder.__code__.co_argcount))
        self.event_map[name].append(responder)

    def send_buffered_message(self, sender, target_channels, message, buffer_size, send_function):
        message_blocks = util.chunk_string(message, buffer_size)
        if len(message_blocks) >= 2 or sender in self.long_block_buffers.keys():
            self.long_block_buffers.setdefault(sender, [])

            # Send the first line if this is new
            if sender not in self.last_long_block_process.keys():
                message = message_blocks[0]
                send_function(sender=sender, message=message, target_channels=target_channels)
                message_blocks = message_blocks[1:]

            self.long_block_buffers[sender] += [(target_channels, message_blocks, send_function)]
            self.last_long_block_process.setdefault(sender, datetime.datetime.now())
        else:
            send_function(sender=sender, message=message, target_channels=target_channels)

    def update(self, delta_time):
        # Process long block buffers
        now = datetime.datetime.now()
        removed_senders = []
        for sender_name, last_sent in zip(self.last_long_block_process.keys(), self.last_long_block_process.values()):
            # If there's nothing in the buffer, stop blocking
            if len(self.long_block_buffers[sender_name]) == 0:
                removed_senders.append(sender_name)
                continue

            # Process the next message
            if now - last_sent >= self.configuration.bridge_generic_config.long_block_delay_seconds:
                target_channels, block_data, send_function = self.long_block_buffers[sender_name][0]

                # Read the first message
                message = block_data[0]
                send_function(sender=sender_name, message=message, target_channels=target_channels)

                # Update the block data and remove if exhausted
                block_data = block_data[1:]
                if len(block_data) == 0:
                    self.long_block_buffers[sender_name] = self.long_block_buffers[sender_name][1:]
                else:
                    self.long_block_buffers[sender_name][0] = (target_channels, block_data, send_function)
                self.last_long_block_process[sender_name] = datetime.datetime.now()

        for removed_sender in removed_senders:
            del self.long_block_buffers[removed_sender]
            del self.last_long_block_process[removed_sender]

    def get_hosted_image_local_path(self, name):
        return os.path.join(self.global_configuration.global_configuration.image_hosting.image_path_base, name)

    def get_hosted_image_url(self, name):
        return os.path.join(self.global_configuration.global_configuration.image_hosting.image_url_base, name)

    def hosted_name_unused(self, name):
        return os.path.exists(self.get_hosted_image_local_path(name)) is False

    def get_unused_hosted_image_name(self, extension=".png"):
        generated_name = None

        potential_symbols = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz123467890-"
        while generated_name is None or self.hosted_name_unused(generated_name) is False:
            symbol_count = random.randint(10, 32)

            generated_name = ""
            for iteration in range(symbol_count):
                generated_name += random.choice(potential_symbols)
            generated_name = "%s%s" % (generated_name, extension)
        return generated_name

    def get_hosted_image_from_path(self, path, extension):
        new_name = self.get_unused_hosted_image_name(extension=extension)
        new_path = self.get_hosted_image_local_path(new_name)

        shutil.move(path, new_path)
        os.chmod(new_path, 0o664)
        return new_name
