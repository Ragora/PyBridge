"""
    IRC.py

    IRC code for the PyIRCBot. This is what actually establishes the connections and emits various
    event types for loaded addons to respond to.

"""

import os
import select
import errno
import socket
import asyncio
import datetime
import threading
import importlib

class Connection(object):
    addons = None
    """ A list addon instances that have been initialized and are operating in this IRC instance. """

    username = None
    """ The """

    nickname = None

    """ The nickname of the bot to use in the server. """
    server = None
    password = None

    """ The IP address of the server to connect to. """
    channel = None

    buffer = None
    scheduler = None
    commands = None

    _socket = None
    """ The internal socket that the client will use. """

    _performed_identification = None

    event_handlers = None

    total_timeout_time = None
    """
        The current total time that recv's from the server have timed out.
    """

    debug_prints_enabled = None
    """
        Whether or not debugging prints are enabled.
    """

    last_ping_time = None

    channel_users = None
    """
        A dictionary mapping IRC channel names to lists of usernames.
    """

    def __init__(self, global_configuration, configuration):
        self.event_handlers =  {
            "OnReceive": [],
            "OnJoin": [],
            "OnPart": [],
            "OnReceivePrivate": [],
            "OnUsernameChange": [],
            "OnReceivePose": [],
            "OnReceivePosePrivate": [],
            "OnQuit": [],
        }

        # Initialize event declarations
        self.username = configuration["username"]
        self.nickname = "%s 1337 hax :Construct" % self.username
        self.channels = configuration["channels"]
        self.password = configuration["password"]
        self.host = configuration["host"]
        self.port = configuration["port"]
        self.connection_info = (configuration["host"], configuration["port"])
        self.configuration = configuration
        self.global_configuration = global_configuration
        self.last_ping_time = datetime.datetime.now()
        self.total_timeout_time = datetime.timedelta(seconds=0)
        self.debug_prints_enabled = False

        self.reconnect()

        self.addons = []
        self.commands = {}
        self.channel_users = {}
        self.buffer = ""

        self._performed_identification = False

        self.send("NICK %s" % self.username)
        self.send("USER %s" % self.nickname)

    def bind_event(self, name, handler):
        self.event_handlers[name].append(handler)

    def dispatch_event(self, name, *args, **kwargs):
        for handler in self.event_handlers[name]:
            result = handler(*args, **kwargs)

    def disconnect(self):
        """
            Closes the connection with the IRC server.
        """
        self._socket.close()

    def reconnect(self):
        self.buffer = ""
        if self._socket is not None:
            self._socket.close()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect(self.connection_info)
        self._socket.setblocking(False)
        self._socket.settimeout(0.03)
        return True

    def send(self, string):
        self._socket.send(bytes("%s\r\n" % string, "utf8"))

    def say(self, string, channel):
        self._socket.send(bytes('PRIVMSG #%s :%s\r\n' % (channel, string), "utf8"))

    def say_to(self, name, string):
        self._socket.send(bytes('PRIVMSG %s :%s\r\n' % (name, string), "utf8"))

    def update(self, delta_time):
        """
            Processes updates for the IRC programming and addons.

            :param delta_time: The time since the last time this update function was called.
        """
        current_time = datetime.datetime.now()
        if current_time - self.last_ping_time >= datetime.timedelta(seconds=self.global_configuration["pingseconds"]):
            self.send("PING :DRAGON\r\n")
            self.last_ping_time = datetime.datetime.now()

        for addon in self.addons:
            addon.update(delta_time)

        received_data = None
        try:
            while True:
                received_data = self._socket.recv(self.global_configuration["chunksize"]).decode("utf8")
                self.buffer += received_data
                self.total_timeout_time = datetime.timedelta(seconds=0)
                received_data = None
        except socket.timeout as e:
            if received_data is not None:
                self.buffer += received_data
            else:
                self.total_timeout_time += delta_time

                if self.total_timeout_time >= datetime.timedelta(seconds=self.global_configuration["timeoutseconds"]):
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

                        self.channel_users[channel_name] = set(users)
                    elif words[1] == "004":
                        for channel in self.channels:
                            self.send("JOIN #%s" % channel)

                        for channel in self.channels:
                            self.send("NAMES #%s" % channel)
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
                    elif words[1] == "NOTICE" and "nickserv" in words[0].lower() and not self._performed_identification and "registered" in return_buffer and self.password is not None:
                        self.say_to("NickServ", "IDENTIFY %s" % self.password)
                        self._performed_identification = True
                    elif words[1] == "NICK":
                        hostmask = words[0]
                        old_username = hostmask.split("!", 1)[0]
                        new_username = words[2][1:]

                        for channel_name, channel_users in zip(self.channel_users.keys(), self.channel_users.values()):
                            if username in channel_users:
                                channel_users.remove(old_username)
                                channel_users.add(new_username)

                        self.dispatch_event("OnUsernameChange", old_username=old_username, new_username=new_username, hostmask=hostmask)
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
