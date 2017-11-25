"""
    A plugin implementing a chat command framework.
"""

from bridgesystem import PluginBase


class ChatCommandsPlugin(PluginBase):
    """
        Class representing the plugin to be called by the main programming.
    """

    command_prefix = "]"
    """
        The prefix that should be used to indicate a chat command. If this is a list, then all items in the list will be valid prefixes.
    """

    command_mapping = None
    """
        A dictionary mapping chat command names to their resolvers for when chat commands are invoked in a channel. These are case insensitive.
    """

    private_command_mapping = None
    """
        A dictionary mapping chat command names to their resolvers for when chat commands are invoked in a private message. These are case insensitive.
    """

    class CommandEntry(object):
        privilege = None
        """
             The minimum administrative privilege level required to execute this command. All clients default to
             0, unprivileged.
        """

        description = None
        """
            The description of the command.
        """

        category = None
        """
            The category this command falls under. If a list, then the command falls under multiple categories.
        """

        handler = None
        """
            The function to call for resolving this command. It must match the following signature:
                message=:MessageBase:, sender=:SenderBase:, components=[:str:]
        """

        def __init__(self, handler, privilege, description, category):
            """
                Initializes a new CommandEntry instance.

                :param handler: The function to call for resolving this command. It must match the following signature:
                    message=:MessageBase:, sender=:SenderBase:, components=[:str:]
                :param privilege: The minimum administrative privilege level required to execute this command. All clients default to
                    0, unprivileged.
                :param description: The description of the command.
                :param category: The category this command falls under. If a list, then the command falls under multiple categories.
            """
            self.handler = handler
            self.category = category
            self.privilege = privilege
            self.description = description

    def __init__(self, application, logger, home_path, configuration, global_configuration, event_handler):
        """
            Initializes a new Plugin. Here you should perform basic initialization of your plugin.
        """
        super(ChatCommandsPlugin, self).__init__(application=application, event_handler=event_handler, logger=logger,
                                                 home_path=home_path, configuration=configuration, global_configuration=global_configuration)

        self.command_mapping = {}
        self.private_command_mapping = {}

    def load_configuration(self, configuration, global_configuration):
        """
            Called when the system configuration file is being loaded or reloaded due to changes.

            :param configuration: The plugin configuration.
            :param global_configuration: The global configuration data.
        """
        super(ChatCommandsPlugin, self).load_configuration(configuration=configuration, global_configuration=global_configuration)
        if "commandPrefix" in self.configuration.plugin_internal_config:
            self.command_prefix = self.configuration.plugin_internal_config["commandPrefix"]
        self.command_prefix = [self.command_prefix] if type(self.command_prefix) is not list else self.command_prefix

    def start(self):
        """
            Called when the plugin should actually startup and begin operation.
        """
        self.event_handler.register_event(self.event_handler.Events.OnReceiveMessage, self.on_receive_message)
        self.event_handler.register_event(self.event_handler.Events.OnReceiveMessagePrivate, self.on_receive_private_message)

        self.register_private_command_handler("help", self.handle_help_command, description="Displays this help text.")
        self.register_command_handler("help", lambda message, components: [channel.send_message("@%s Please private message me to see help." % message.sender.username) for channel in message.channels],
                                      description="The bot tells you to message it with the help command.")

    def stop(self):
        """
            Called when the plugin should stop all operational functions to be unloaded.
        """

    def update(self, delta_time):
        """
            Called when the plugin should update any internals it may have on an update pulse.
            This is called once per iteration of the main program loop.

            :param delta_time: A datetime.timedelta object representing how much realtime has passed
                since the last update.
        """

    def handle_help_command(self, message, components):
        # Output channel commands first
        result = ""
        if len(self.command_mapping) != 0:
            result = "Available Channel Commands\n"

            categories = set([command.category for command in self.command_mapping.values()])
            categorized = {category: [(name, self.command_mapping[name]) for name in self.command_mapping.keys()] for category in categories}

            for category, commands in zip(categorized.keys(), categorized.values()):
                category = "Uncategorized" if category is None else category

                result += "    Category '%s'\n" % category
                for name, meta in commands:
                    command_entry = "%s%s" % (self.command_prefix[0], name)

                    if meta.description is not None:
                        command_entry += " - %s" % meta.description
                    result += "        %s\n" % command_entry
        message.sender.send_message(result)

    def register_command_handler(self, command, handler, privilege=0, description=None, category=None):
        """
            Registers a chat command handler for when they are invoked in a channel.

            :param command: The name of the command.
            :param handler: The function to call for resolving this command. It must match the following signature:
                message=:MessageBase:, components=[:str:]
            :param privilege: The minimum administrative privilege level required to execute this command. All clients default to
                0, unprivileged.
            :param description: The description of the command.
            :param category: The category this command falls under. If a list, then the command falls under multiple categories.
        """
        self.command_mapping[command.lower()] = ChatCommandsPlugin.CommandEntry(privilege=privilege, handler=handler, description=description, category=category)

    def register_private_command_handler(self, command, handler, privilege=0, description=None, category=None):
        """
            Registers a chat command handler for when they are invoked in a private message.

            :param command: The name of the command.
            :param handler: The function to call for resolving this command. It must match the following signature:
                message=:MessageBase:, components=[:str:]
            :param privilege: The minimum administrative privilege level required to execute this command. All clients default to
                0, unprivileged.
            :param description: The description of the command.
            :param category: The category this command falls under. If a list, then the command falls under multiple categories.
        """
        self.private_command_mapping[command.lower()] = ChatCommandsPlugin.CommandEntry(privilege=privilege, handler=handler, description=description, category=category)

    def on_receive_message(self, emitter, message):
        """
            A callback handler for when the bot receives a regular text message in a channel.

            :param bridge: The sending bridge.
            :param message: The message that was sent.
        """
        if message.raw_text is None:
            return

        for prefix in self.command_prefix:
            # We are processing a chat command
            if message.raw_text[:len(prefix)] == prefix:
                components = message.raw_text.split()
                command = components[0][len(prefix):].lower()
                components = components[1:]

                if command in self.command_mapping.keys():
                    self.command_mapping[command].handler(components=components, message=message)
                else:
                    [channel.send_message("@%s Invalid chat command '%s'" % (message.sender.username, command)) for channel in message.channels]
                    self.logger.debug("Received invalid chat command '%s'" % command)
                break

    def on_receive_private_message(self, emitter, message):
        """
            A callback handler for when the bot receives a private text message.

            :param bridge: The sending bridge.
            :param message: The message that was sent.
        """
        if message.raw_text is None:
            return

        for prefix in self.command_prefix:
            # We are processing a chat command
            if message.raw_text[:len(prefix)] == prefix:
                components = message.raw_text.split()
                command = components[0][len(prefix):].lower()
                components = components[1:]

                if command in self.private_command_mapping.keys():
                    self.private_command_mapping[command].handler(components=components, message=message)
                else:
                    message.sender.send_message("Invalid chat command '%s'." % command)
                    self.logger.debug("Received invalid private chat command '%s'" % command)
                break
