"""
    IRC.py

    IRC code for the PyIRCBot. This is what actually establishes the connections and emits various
    event types for loaded addons to respond to.

"""

import os
import time
import select
import errno
import socket
import asyncio
import datetime
import threading
import importlib

from bridgesystem import BridgeBase, util

class Connection(object):
    username = None
    """ The name this bot will publicly expose itself as. """

    nickname = None

    """ The nickname of the bot to use in the server. """
    server = None

    password = None
    """
        The password that the bot will use to authenticate against NickServ with. This is only temporarily
        stored and is rewritten with None upon authentication.
    """

    """ The IP address of the server to connect to. """
    channel = None

    buffer = None
    """
        The current text buffer.
    """

    socket = None
    """
        The internal socket that the client will use.
    """

    performed_identification = None
    """
        Whether or not the IRC bot has performed the identification step with the NickServ.
    """

    event_handlers = None

    total_timeout_time = None
    """
        The current total time that recv's from the server have timed out.
    """

    debug_prints_enabled = True
    """
        Whether or not debugging prints are enabled.
    """

    last_ping_time = None

    channel_users = None
    """
        A dictionary mapping IRC channel names to lists of usernames.
    """

    ping_delay = None
    """
        How long to wait between pings.
    """

    timeout_delay = None
    """
        How long to wait without data from the server before we call it a timeout.
    """

    receive_length = None
    """
        How many bytes per recv call should be received.
    """

    received_user_lists = False

    def __init__(self, address, port, username, channels, password=None, ping_delay=None,
    timeout_delay=datetime.timedelta(seconds=60), receive_length=4096, event_handlers={}):

        """
         {
            "OnReceive": [],
            "OnJoin": [],
            "OnPart": [],
            "OnReceivePrivate": [],
            "OnUsernameChange": [],
            "OnReceivePose": [],
            "OnReceivePosePrivate": [],
            "OnQuit": [],
        }
        """

        # Initialize event declarations
        self.port = port
        self.host = address
        self.username = username
        self.timeout_delay = timeout_delay
        self.receive_length = receive_length
        self.nickname = "%s 1337 hax :Construct" % self.username
        self.channels = channels
        self.password = password
        self.ping_delay = ping_delay
        self.connection_info = (address, port)
        self.event_handlers = event_handlers
        self.last_ping_time = datetime.datetime.now()
        self.total_timeout_time = datetime.timedelta(seconds=0)
        self.debug_prints_enabled = False

        self.channel_users = {}

        # Ensure all of the responders are lists
        for event_name, responder in zip(self.event_handlers.keys(), self.event_handlers.values()):
            if type(responder) is not list:
                self.event_handlers[event_name] = [responder]

        self.reconnect()

        self.addons = []
        self.commands = {}
        self.buffer = ""

        self.performed_identification = False

        self.send("NICK %s" % self.username)
        self.send("USER %s" % self.nickname)

    def dispatch_event(self, name, *args, **kwargs):
        if name in self.event_handlers:
            for handler in self.event_handlers[name]:
                result = handler(*args, **kwargs)

    def disconnect(self):
        """
            Closes the connection with the IRC server.
        """
        self.socket.close()

    def reconnect(self):
        self.buffer = ""
        if self.socket is not None:
            self.socket.close()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(self.connection_info)
        self.socket.setblocking(False)
        self.socket.settimeout(0.03)
        return True

    def send(self, string):
        self.socket.send(bytes("%s\r\n" % string, "utf8"))

    def say(self, string, channel):
        for string in util.chunk_string(string, 450):
            self.socket.send(bytes('PRIVMSG #%s :%s\r\n' % (channel, string), "utf8"))

    def say_to(self, name, string):
        for string in util.chunk_string(string, 450):
            self.socket.send(bytes('PRIVMSG %s :%s\r\n' % (name, string), "utf8"))

    def update(self, delta_time):
        """
            Processes updates for the IRC programming and addons.

            :param delta_time: The time since the last time this update function was called.
        """
        current_time = datetime.datetime.now()
        if self.ping_delay is not None and current_time - self.last_ping_time >= self.ping_delay:
            self.send("PING :DRAGON\r\n")
            self.last_ping_time = datetime.datetime.now()

        for addon in self.addons:
            addon.update(delta_time)

        received_data = None
        try:
            while True:
                received_data = self.socket.recv(self.receive_length).decode("utf8")
                self.buffer += received_data
                self.total_timeout_time = datetime.timedelta(seconds=0)
                received_data = None
        except socket.timeout as e:
            if received_data is not None:
                self.buffer += received_data
            else:
                self.total_timeout_time += delta_time

                if self.total_timeout_time >= self.timeout_delay:
                    self.total_timeout_time = datetime.timedelta(seconds=0)

                    if self.debug_prints_enabled is True:
                        print("Server connection has timed out -- attempting reconnection ...")
                    self.reconnect()
        except socket.error as e:
            error = e.args[0]
            if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
                return

            if self.debug_prints_enabled is True:
                print("Disconnected from server -- attempting reconnection ...")
                print("Reason: %s" % str(e))

            self.reconnect()
        except BlockingIOError as e:
            pass

        if "\r\n" in self.buffer:
            split = self.buffer.split("\r\n")
            self.buffer = split.pop()

            for return_buffer in split:
                # print(return_buffer)
                return_buffer = return_buffer[1:]

                words = return_buffer.split()
                if len(words) >= 3:
                    if self.debug_prints_enabled is True and words[1] != "PONG":
                        print(words)
                    if words[0] == "PING":
                        self.send("PONG %s" % words[1])
                    elif words[1] == "353":
                        channel_name = words[4][1:]
                        users = words[5:]
                        users[0] = users[0][1:]

                        for user in users:
                            self.channel_users.setdefault(channel_name, set())
                            self.channel_users[channel_name].add(user)

                            self.dispatch_event("OnUserListPopulate", username=user, channel=channel_name)
                    elif words[1] == "004":
                        for channel in self.channels:
                            time.sleep(0.05)
                            self.send("JOIN #%s" % channel)

                        #for channel in self.channels:
                        #    time.sleep(0.05)
                        #    self.send("NAMES #%s" % channel)
                    elif (words[1] == "PRIVMSG" and words[2].lstrip("#") in self.channels):
                        channel = words[2].lstrip("#")
                        sending_user = words[0].split("!")
                        sending_user = sending_user[0]
                        message_data = return_buffer[return_buffer.find(":") + 1:]

                        """
                        words = message_data.split()
                        if (message_data[0] == "]"):
                            command = words[0].lstrip("]").lower()
                            if (command in self.commands):
                                function_call = self.commands[command]["call"]
                                function_call(sending_user, message_data[len(command) + 1:])
                        """

                        if words[3] == ":\x01ACTION":
                            message_data = " ".join(words[4:])
                            self.dispatch_event("OnReceivePose", username=sending_user, message=message_data, channel=channel)
                        else:
                            message_data = " ".join(words[3:])[1:]
                            self.dispatch_event("OnReceive", username=sending_user, message=message_data, channel=channel)

                    elif(words[1] == "PRIVMSG" and words[2].lstrip("#") not in self.channels):
                        sending_user = words[0].split('!')
                        sending_user = sending_user[0]

                        if words[3] == ":\x01ACTION":
                            message_data = " ".join(words[4:])
                            self.dispatch_event("OnReceivePosePrivate", username=sending_user, message=message_data)
                        else:
                            message_data = " ".join(words[3:])[1:]
                            self.dispatch_event("OnReceivePrivate", username=sending_user, message=message_data)

                    # Handles for nick
                    elif words[1] == "NOTICE" and "nickserv" in words[0].lower() and not self.performed_identification and "registered" in return_buffer and self.password is not None:
                        self.say_to("NickServ", "IDENTIFY %s" % self.password)
                        self.performed_identification = True
                        self.password = None
                    elif words[1] == "NICK":
                        hostmask = words[0]
                        old_username = hostmask.split("!", 1)[0]
                        new_username = words[2][1:]

                        channels = set()
                        for channel_name, channel_users in zip(self.channel_users.keys(), self.channel_users.values()):
                            if old_username in channel_users:
                                channels.add(channel_name)
                                channel_users.remove(old_username)
                                channel_users.add(new_username)

                        self.dispatch_event("OnUsernameChange", old_username=old_username, new_username=new_username, hostmask=hostmask, channels=channels)
                    elif words[1] == "QUIT":
                        hostmask = words[0]
                        username = hostmask.split("!", 1)[0]
                        message = " ".join(words[2:])[1:]

                        left_channels = []
                        for channel_name, channel_users in zip(self.channel_users.keys(), self.channel_users.values()):
                            if username in channel_users:
                                left_channels.append(channel_name)
                                channel_users.remove(username)

                        self.dispatch_event("OnQuit", username=username, message=message, hostmask=hostmask, channels=left_channels)
                    elif words[1] == "JOIN":
                        channel = words[2].lstrip("#")
                        if channel in self.channels:
                            hostmask = words[0]
                            username = hostmask.split("!", 1)[0]

                            if username == self.username:
                                return

                            self.channel_users[channel].add(username)
                            self.dispatch_event("OnJoin", username=username, hostmask=hostmask, channel=channel)
                    elif words[1] == "PART":
                        channel = words[2].lstrip("#")
                        if channel in self.channels:
                            hostmask = words[0]
                            username = hostmask.split("!", 1)[0]
                            message = " ".join(words[3:])[1:]

                            if username == self.username:
                                return

                            if username in self.channel_users[channel]:
                                self.channel_users[channel].remove(username)

                            self.dispatch_event("OnPart", username=username, hostmask=hostmask, channel=channel, message=message)
