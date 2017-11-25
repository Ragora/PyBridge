"""
    Python programming for the Channel class.
"""

from .message import Message
from bridgesystem import ChannelBase

class Channel(ChannelBase):
    """
        A class representing an Discord channel in the bot.
    """

    connection = None
    """
        The Discord connection object used to send and receive messages from the server.
    """

    channel_instance = None
    """
        The channel object associated with this Channel.
    """

    event_loop = None

    def __init__(self, connection, event_loop, channel_instance, members=None):
        """
            :param connection: The IRC connection object used to send and receive messages from the server.
            :param name: The raw name of this channel.
            :param display_name: The name of this channel without any service specific decorators such as IRC #channelName.
            :param description: The description associated with this channel. If None or not supported by this service, then this
                should be None.
            :param members: A list of UserBase objects representing all members in this channel.
        """
        members = [] if members is None else members
        super(Channel, self).__init__(name=channel_instance.name, display_name=channel_instance.name, description=channel_instance.topic if hasattr(channel_instance, "topic") else None, members=members)
        self.connection = connection
        self.event_loop = event_loop
        self.channel_instance = channel_instance

    def send_message(self, message):
        """
            Sends a message to this channel.

            :param message: The message text to send to this channel.

            :rtype: MessageBase
            :return: A MessageBase instance representing the generated message.
        """
        self.event_loop.create_task(self.connection.send_message(self.channel_instance, message))
        return None
