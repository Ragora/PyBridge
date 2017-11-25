"""
    Python programming for the PluginBase class.
"""


class PluginBase(object):
    logger = None
    """
        The logger associated with this plugin.
    """

    home_path = None
    """
        The home path to use for any persistent storage.
    """

    application = None
    """
        The application object.
    """

    configuration = None
    """
        The plugin configuration.
    """

    global_configuration = None
    """
        The bot global configuration.
    """

    event_handler = None
    """
        The event handler for this domain.
    """

    def __init__(self, application, logger, home_path, configuration, global_configuration, event_handler):
        self.logger = logger
        self.home_path = home_path
        self.application = application
        self.configuration = configuration
        self.event_handler = event_handler
        self.global_configuration = global_configuration

        self.long_block_buffers = {}
        self.last_long_block_process = {}

    def load_configuration(self, configuration, global_configuration):
        """
            Called when the system configuration file is being loaded or reloaded due to changes.

            :param configuration: The plugin configuration.
            :param global_configuration: The global configuration data.
        """
        self.configuration = configuration
        self.global_configuration = global_configuration

    def start(self):
        """
            Called when the plugin should startup and configure itself for runtime operation.
        """
        raise NotImplementedError("Cannot start plugin: Not implemented.")

    def stop(self):
        """
            Called when the plugin should stop all operational functions to be unloaded.
        """
        raise NotImplementedError("Cannot stop plugin: Not implemented.")

    def update(self, delta_time):
        """
            Called when the plugin should update any internals it may have on an update pulse.
            This is called once per iteration of the main program loop.

            :param delta_time: A datetime.timedelta object representing how much realtime has passed
                since the last update.
        """
        raise NotImplementedError("Cannot update plugin: Not implemented.")
