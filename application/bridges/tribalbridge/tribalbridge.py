"""
    Tribes 2 bridge code.
"""

import re
import sys
import time
import errno
import random
import socket
import asyncio
import datetime
import threading
import collections

from bridgesystem import BridgeBase

class Bridge(BridgeBase):
    """
        Class representing a Tribes 2 bridge.
    """

    tribal_connection = None
    """
        The socket connecting to our Tribes 2 server.
    """

    receive_buffer_size = None
    """
        The total number of bytes we will read in one recv call.
    """

    message_buffer = None
    """
        The current message buffer from the Tribes 2 server.
    """

    last_connection_attempt = None
    """
        The last time a connection attempt was made.
    """

    last_heartbeat_time = None
    """
        The last time a heartbeat was received from the Tribes 2 server.
    """

    RECONNECT_ATTEMPT_TIME = datetime.timedelta(seconds=5)
    """
        How long between connection attempts to wait.
    """

    HEARTBEAT_ERROR_TIME = datetime.timedelta(seconds=10)
    """
        The time between heart beats at which point the Tribes 2 server is considered dead and that
        we should initiate reconnection attempts.
    """

    def __init__(self, application, home_path, configuration, global_configuration):
        super(Addon, self).__init__(application, configuration)
        self.message_buffer = ""
        self.receive_buffer_size = int(self.configuration["receiveSize"])

    def stop(self):
        """
            Stops the addon.
        """

    def on_receive_message(self, sender, sender_name, message, target_channels):
        for target_channel in target_channels:
            if target_channel in self.configuration["channels"] and self.tribal_connection is not None and sender_name not in self.configuration["ignoreSenders"]:
                produced_message = bytes("MESSAGE\r\n%s\r\n%s\r\n%s\r\n" % (sender_name, sender.configuration["name"], message), "ascii", errors="replace")
                self.tribal_connection.send(produced_message)
                return

    def establish_connection(self):
        now = datetime.datetime.now()

        try:
            self.tribal_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tribal_connection.connect((self.configuration["address"], self.configuration["port"]))
            self.tribal_connection.settimeout(0.2)

            if self.last_connection_attempt is not None:
                self.application.broadcast_event("on_receive_message",
                sender=self,
                sender_name="Internal System",
                message="Successfully established a connection to the Tribes 2 server after previous connectivity problems.",
                target_channels=self.configuration["channels"])
            self.last_heartbeat_time = now
        except ConnectionRefusedError as e:
            self.tribal_connection = None

            if self.last_connection_attempt is None:
                self.application.broadcast_event("on_receive_message",
                sender=self,
                sender_name="Internal System",
                message="Failed to connect to the Tribes 2 server. Will attempt to reconnect on a delay of %s." % self.RECONNECT_ATTEMPT_TIME,
                target_channels=self.configuration["channels"])
        self.last_connection_attempt = now

    def start(self):
        """
            Starts the addon after it has been initialized and all connections associated. This is called after
            all connections have been created.
        """

        self.register_event("on_receive_message", self.on_receive_message)
        self.establish_connection()

    def update(self, delta_time):
        """
            Process an update tick.

            :param delta_time: The time since the last time addon updates were processed.
        """

        now = datetime.datetime.now()
        if self.tribal_connection is not None:
            received_data = None
            try:
                received_data = self.tribal_connection.recv(self.receive_buffer_size)
            except socket.error as e:
                socket_error = e.args[0]
                if socket_error != errno.EWOULDBLOCK and socket_error != errno.EAGAIN and socket_error != "timed out":
                    self.tribal_connection.close()
                    self.tribal_connection = None

                    self.application.broadcast_event("on_receive_message",
                    sender=self,
                    sender_name="Internal System",
                    message="Lost the connection to the Tribes 2 server due to a socket error. Will attempt to reconnect on a delay of %s." % self.RECONNECT_ATTEMPT_TIME,
                    target_channels=self.configuration["channels"])
                    self.last_connection_attempt = now
                    return
                elif now - self.last_heartbeat_time >= self.HEARTBEAT_ERROR_TIME:
                    self.tribal_connection.close()
                    self.tribal_connection = None

                    self.application.broadcast_event("on_receive_message",
                    sender=self,
                    sender_name="Internal System",
                    message="Lost the connection to the Tribes 2 server due to a timeout. Will attempt to reconnect on a delay of %s." % self.RECONNECT_ATTEMPT_TIME,
                    target_channels=self.configuration["channels"])
                    self.last_connection_attempt = now
                    return

            if received_data is not None:
                self.message_buffer += received_data.decode("ascii", errors="replace")

            if "\r\n" in self.message_buffer:
                received_messages = self.message_buffer.split("\r\n")
                self.message_buffer = received_messages.pop()

                for received_message in received_messages:
                    message_components = received_message.split("\n")

                    message_type = message_components[0]
                    if message_type == "MESSAGE":
                        self.application.broadcast_event("on_receive_message",
                        sender=self,
                        sender_name=message_components[1],
                        message=message_components[2],
                        target_channels=self.configuration["channels"])
                    elif message_type == "CONNECT":
                        self.application.broadcast_event("on_receive_join",
                        sender=self,
                        joined_name=message_components[1],
                        target_channels=self.configuration["channels"])
                    elif message_type == "DISCONNECT":
                        self.application.broadcast_event("on_receive_leave",
                        sender=self,
                        left_name=message_components[1],
                        target_channels=self.configuration["channels"])
                    elif message_type == "HEARTBEAT":
                        self.last_heartbeat_time = now
            elif now - self.last_heartbeat_time >= self.HEARTBEAT_ERROR_TIME:
                self.tribal_connection.close()
                self.tribal_connection = None

                self.application.broadcast_event("on_receive_message",
                sender=self,
                sender_name="Internal System",
                message="Lost the connection to the Tribes 2 server due to a timeout. Will attempt to reconnect on a delay of %s." % self.RECONNECT_ATTEMPT_TIME,
                target_channels=self.configuration["channels"])
                self.last_connection_attempt = now
                return
        elif now - self.last_connection_attempt >= self.RECONNECT_ATTEMPT_TIME:
            self.establish_connection()

    def get_commands(self):
        return {}
