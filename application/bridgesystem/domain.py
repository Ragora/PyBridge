"""
    Python programming for the Domain class.
"""

class Domain(object):
    """
        A class representing a broadcast domain in the bridging bot.
    """

    name = None
    """
        The name of this domain.
    """

    event_handler = None
    """
        The event handler for this domain.
    """

    plugins = None
    """
        The list of plugins loaded for this domain.
    """

    bridges = None
    """
        The list of bridges loaded for this domain.
    """

    def __init__(self, name, plugins, bridges, event_handler):
        """
            Initializes a new Domain instance.

            :param name: The name of this Domain.
            :param plugins: The list of plugins loaded for this domain.
            :param bridges: The list of bridges loaded for this domain.
            :param event_handler: The event handler for this domain.
        """
        self.name = name
        self.plugins = plugins
        self.bridges = bridges
        self.event_handler = event_handler

    def update(self, delta_time):
        """
            Updates all plugins and bridges in this Domain.

            :param delta_time: The datetime.timedelta object representing how much time has passed since the last update.
        """
        for bridge in self.bridges:
            bridge.update(delta_time)
        for plugin in self.plugins:
            plugin.update(delta_time)

    def stop(self):
        """
            Stops all plugins and bridges in this Domain.
        """
        for plugin in self.plugins:
            plugin.stop()
        for bridge in self.bridges:
            bridge.stop()

    def start(self):
        """
            Starts all plugins and bridges in this Domain.
        """
        for bridge in self.bridges:
            bridge.start()
        for plugin in self.plugins:
            plugin.start()
