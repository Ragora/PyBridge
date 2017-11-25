"""
    IRC.py

    IRC code for the PyIRCBot. This is what actually establishes the connections and emits various
    event types for loaded addons to respond to.

"""

import os
import time
import logging
import select
import errno
import socket
import asyncio
import datetime
import threading
import importlib

from bridgesystem import BridgeBase, util


class Connection(object):
    """
        A class representing an IRC client connection to a server.
    """

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
    """
        A datetime.datetime object representing the last time a ping was sent to the server.
    """

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

    real_name = None
    """
        The real name of this bot.
    """

    logger = None

    received_user_lists = False

    protocol_handlers = None
    """
        Regular IRC protocol handlers.
    """

    ctcp_handlers = None
    """
        Handlers for the CTCP protocol.
    """

    def handle_ping(self, message, components):
        """
            Handler for a server PING command.
        """
        self.send("PONG %s" % components[1])

    def handle_ctcp_ping(self, sending_user, recipient, message, parameters):
        """
            Handles a CTCP PING command.

            :param sending_user: The name of the user that had sent the CTCP command.
            :param recipient: The name of the recipient. If a channel, then this is preceded with a #.
            :param message: The full CTCP command parameters as a single string.
            :param parameters: The full CTCP command parameters as a list.
        """
        if len(parameters) == 1 and recipient == self.username:
            self.send_ctcp_reply_to(name=sending_user, command="PING", string=parameters[0])

    def handle_ctcp_action(self, sending_user, recipient, message, parameters):
        """
            Handles a CTCP ACTION command.

            :param sending_user: The name of the user that had sent the CTCP command.
            :param recipient: The name of the recipient. If a channel, then this is preceded with a #.
            :param message: The full CTCP command parameters as a single string.
            :param parameters: The full CTCP command parameters as a list.
        """

        parameters[-1] = parameters[-1].rstrip("\x01")
        message_data = " ".join(parameters)

        if recipient[0] == "#":
            recipient = recipient[1:].lower()

            if recipient in self.channels:
                self.dispatch_event("OnReceivePose", username=sending_user, message=message_data, channel=recipient)
        else:
            self.dispatch_event("OnReceivePosePrivate", username=sending_user, message=message_data)

    def handle_ctcp_version(self, sending_user, recipient, message, parameters):
        """
            Handles a CTCP VERSION command.

            :param sending_user: The name of the user that had sent the CTCP command.
            :param recipient: The name of the recipient. If a channel, then this is preceded with a #.
            :param message: The full CTCP command parameters as a single string.
            :param parameters: The full CTCP command parameters as a list.
        """
        if recipient == self.username:
            self.send_ctcp_reply_to(name=sending_user, command="VERSION", string="PyBridge Bot")

    def handle_ctcp_time(self, sending_user, recipient, message, parameters):
        """
            Handles a CTCP TIME command.

            :param sending_user: The name of the user that had sent the CTCP command.
            :param recipient: The name of the recipient. If a channel, then this is preceded with a #.
            :param message: The full CTCP command parameters as a single string.
            :param parameters: The full CTCP command parameters as a list.
        """
        if recipient == self.username:
            self.send_ctcp_reply_to(name=sending_user, command="TIME", string=str(datetime.datetime.now()))

    def handle_quit(self, message, components):
        """
            Handles a QUIT invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        hostmask = components[0]
        username = hostmask.split("!", 1)[0]
        message = " ".join(components[2:])[1:]

        left_channels = set()
        for channel_name, channel_users in zip(self.channel_users.keys(), self.channel_users.values()):
            if username in channel_users:
                left_channels.add(channel_name)
                channel_users.remove(username)

        self.logger.debug("%s left the server." % username)
        self.dispatch_event("OnQuit", username=username, message=message, hostmask=hostmask, channels=left_channels)

    def handle_nick(self, message, components):
        """
            Handles a NICK invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        hostmask = components[0]
        old_username = hostmask.split("!", 1)[0]
        new_username = components[2][1:]

        self.logger.debug("'%s' changed their name to '%s'." % (old_username, new_username))

        channels = set()
        for channel_name, channel_users in zip(self.channel_users.keys(), self.channel_users.values()):
            if old_username in channel_users:
                channels.add(channel_name)
                channel_users.remove(old_username)
                channel_users.add(new_username)

        self.dispatch_event("OnUsernameChange", old_username=old_username, new_username=new_username, hostmask=hostmask, channels=channels)

    def handle_part(self, message, components):
        """
            Handles a PART invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """

        channel = components[2].lstrip("#").lower()
        if channel in self.channels:
            hostmask = components[0]
            username = hostmask.split("!", 1)[0]
            message = " ".join(components[3:])[1:]

            self.logger.debug("%s left channel %s." % (username, channel))
            if username == self.username:
                return

            if username in self.channel_users[channel]:
                self.channel_users[channel].remove(username)

            self.dispatch_event("OnPart", username=username, hostmask=hostmask, channel=channel, message=message)

    def handle_pong(self, message, components):
        """
            Handles a PONG invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """

    def handle_join(self, message, components):
        """
            Handles a JOIN invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        channel = components[2].lstrip("#").lower()
        if channel in self.channels:
            hostmask = components[0]
            username = hostmask.split("!", 1)[0]

            self.logger.debug("%s joined channel %s." % (username, channel))
            if username == self.username:
                return

            self.channel_users[channel].add(username)
            self.dispatch_event("OnJoin", username=username, hostmask=hostmask, channel=channel)

    def handle_user_list(self, message, components):
        """
            Handles a 353 (user list) invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        channel_name = components[4][1:].lower()
        users = components[5:]
        users[0] = users[0][1:]

        self.logger.debug("Received user list for channel %s: %s" % (channel_name, ", ".join(users)))
        for user in users:
            self.channel_users.setdefault(channel_name, set())
            self.channel_users[channel_name].add(user)
        self.dispatch_event("OnUserListPopulate", usernames=self.channel_users[channel_name], channel=channel_name)

    def handle_server_information(self, message, components):
        """
            Handles a 004 (server information) invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        self.logger.debug("Successfully established a connection to the IRC server. Joining channels and requesting userlists.")

        channels = ",".join(["#%s" % channel for channel in self.channels])
        self.send("JOIN %s" % channels)
        self.send("NAMES %s" % channels)

    def handle_notice(self, message, components):
        """
            Handles a NOTICE invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        if "nickserv" in components[0].lower() and not self.performed_identification and "registered" in message and self.password is not None:
            self.logger.debug("IRC server has requested authentication. Attempting to authenticate.")

            if self.password is not None:
                self.say_to("NickServ", "IDENTIFY %s" % self.password)
                self.performed_identification = True
                self.password = None
            else:
                self.logger.error("IRC server requested authentication but there is currently no password set.")

    def handle_join(self, message, components):
        """
            Handles a JOIN invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        channel = components[2].lstrip("#").lower()
        if channel in self.channels:
            hostmask = components[0]
            username = hostmask.split("!", 1)[0]

            if username == self.username:
                return

            self.channel_users[channel].add(username)
            self.dispatch_event("OnJoin", username=username, hostmask=hostmask, channel=channel)

    def handle_privmsg(self, message, components):
        """
            Handles a PRIVMSG invocation.

            :param message: The full message string.
            :param components: The components of the message string.
        """
        recipient = components[2]
        sending_user = components[0].split("!")
        sending_user = sending_user[0]

        # If this appears to be a CTCP message, handle it accordingly
        if components[3][:2] == ":\x01":
            ctcp_command = components[3].lstrip(":\x01")
            command_parameters = components[4:]

            if len(command_parameters) != 0:
                command_parameters[-1] = command_parameters[-1].rstrip("\x01")

            ctcp_command = ctcp_command.rstrip("\x01")
            command_message = " ".join(command_parameters)

            if ctcp_command in self.ctcp_handlers.keys():
                self.logger.debug("Processing CTCP command '%s' from '%s'" % (ctcp_command, sending_user))
                self.ctcp_handlers[ctcp_command](sending_user=sending_user, recipient=recipient, message=command_message, parameters=command_parameters)
            else:
                self.logger.error("Received unknown CTCP command '%s' from '%s'" % (ctcp_command, sending_user))
            return

        is_channel = recipient[0] == "#"
        if is_channel:
            channel = recipient[1:].lower()

            if channel in self.channels:
                message_data = message[message.find(":") + 1:]
                message_data = " ".join(components[3:])[1:]
                self.dispatch_event("OnReceive", username=sending_user, message=message_data, channel=channel)
        else:
            message_data = " ".join(components[3:])[1:]
            self.dispatch_event("OnReceivePrivate", username=sending_user, message=message_data)

    def __init__(self, address, port, username, channels, password=None, ping_delay=None, real_name="PyBridge", server_name="Bots",
                 host_name="Python", timeout_delay=datetime.timedelta(seconds=60), logger=None, receive_length=4096, event_handlers={}):
        """
            Initializes a new IRC connection.

            :param address: The hostname or IP address of the server to connect to.
            :param port: The port number to connect on.
            :param username: The username to use for the bot.
            :param channels: A list of channel names to connect to.
            :param password: If specified, then this will be the password that the bot will authenticate itself with.
            :param ping_delay: If specified, a datetime.timedelta object representing how long between pings the bot should wait before pining.
            :param real_name: The "real name" of the bot to advertise.
            :param server_name: The server name for the bot to specify.
            :param host_name: The host name for the bot to specify.
            :param timeout_delay: A datetime.timedelta object representing the length of time when communications stop with the server to consider
                it a timeout.
            :param logger: The python logger object to use with this connection. If not specified, then a basic one is initialized.
            :param receive_length: The input for the socket recv function.
            :param event_handlers: A dictionary mapping event names to their respective handlers.
        """

        self.protocol_handlers = {
            "PING": self.handle_ping,
            "QUIT": self.handle_quit,
            "NICK": self.handle_nick,
            "PART": self.handle_part,
            "NOTICE": self.handle_notice,
            "PRIVMSG": self.handle_privmsg,
            "353": self.handle_user_list,
            "PONG": self.handle_pong,
            "JOIN": self.handle_join,
            "004": self.handle_server_information,
        }

        self.ctcp_handlers = {
            "PING": self.handle_ctcp_ping,
            "TIME": self.handle_ctcp_time,
            "ACTION": self.handle_ctcp_action,
            "VERSION": self.handle_ctcp_version
        }

        # Initialize event declarations
        self.port = port
        self.host = address
        self.host_name = host_name
        self.real_name = real_name
        self.server_name = server_name
        self.logger = logger if logger is not None else logging.basicConfig()
        self.username = username
        self.timeout_delay = timeout_delay
        self.receive_length = receive_length
        self.nickname = "%s %s %s :%s" % (self.username, self.host_name, self.server_name, self.real_name)
        self.channels = channels
        self.password = password
        self.ping_delay = ping_delay
        self.connection_info = (address, port)
        self.event_handlers = event_handlers
        self.last_ping_time = datetime.datetime.now()
        self.total_timeout_time = datetime.timedelta(seconds=0)
        self.debug_prints_enabled = False

        self.channel_users = {channel: set() for channel in channels}

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
        self.logger.debug("Establishing connection to IRC server.")

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
        """
            Sends a string to the specified IRC channel.

            :param string: The message data to send. If it contains newlines, it is automatically split up as multiple
                messages.
            :param channel: The name of the channel to send to.
        """
        for string in util.chunk_string(string, 450):
            lines = string.split("\n")
            for line in lines:
                self.socket.send(bytes("PRIVMSG #%s :%s\r\n" % (channel, line), "utf8"))

    def say_to(self, name, string):
        """
            Sends a message to the specified IRC user.

            :param name: The name of the user to send to.
            :param string: The message string to send. If it contains newlines, they are automatically split up
                as multiple messages.
        """
        for string in util.chunk_string(string, 450):
            lines = string.split("\n")
            for line in lines:
                self.socket.send(bytes("PRIVMSG %s :%s\r\n" % (name, line), "utf8"))

    def send_notice_to(self, name, string):
        """
            Sends a NOTICE to he specified user.

            :param name: The name of the user to send the notice to.
            :param string: The NOTICE string data to send.
        """
        for string in util.chunk_string(string, 450):
            self.socket.send(bytes("NOTICE %s :%s\r\n" % (name, string), "utf8"))

    def send_ctcp_reply_to(self, name, command, string):
        """
            Sends a CTCP command reply to the specified IRC user.

            :param name: The name of the IRC user to send the reply to.
            :param command: The CTCP command reply name.
            :param string: The CTCP reply data.
        """
        self.send_notice_to(name=name, string="\x01%s %s\x01" % (command, string))

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
                        self.logger.error("Server connection has timed out -- attempting reconnection ...")
                    self.reconnect()
        except socket.error as e:
            error = e.args[0]
            if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
                return

            if self.debug_prints_enabled is True:
                self.logger.error("Disconnected from server -- attempting reconnection ...")
                self.logger.error("Reason: %s" % str(e))

            self.reconnect()
        except BlockingIOError as e:
            pass

        if "\r\n" in self.buffer:
            split = self.buffer.split("\r\n")
            self.buffer = split.pop()

            for return_buffer in split:
                # print(return_buffer)
                return_buffer = return_buffer[1:]

                components = return_buffer.split()
                if len(components) >= 3:
                    if self.debug_prints_enabled is True and components[1] != "PONG":
                        print(components)

                    # If this exists as a command, process it
                    if components[1] in self.protocol_handlers.keys():
                        self.logger.debug("Handling '%s' command." % components[1])
                        self.protocol_handlers[components[1]](return_buffer, components)
                    else:
                        self.logger.debug("Unknown command: '%s'" % components[1])
