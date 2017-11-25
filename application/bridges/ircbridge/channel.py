"""
    Python programming for the Channel class.
"""

from .message import Message
from bridgesystem import ChannelBase

class Channel(ChannelBase):
    """
        A class representing an IRC channel in the bot.
    """

    connection = None
    """
        The IRC connection object used to send and receive messages from the server.
    """

    def __init__(self, connection, name, display_name, description=None, members=None):
        """
            :param connection: The IRC connection object used to send and receive messages from the server.
            :param name: The raw name of this channel.
            :param display_name: The name of this channel without any service specific decorators such as IRC #channelName.
            :param description: The description associated with this channel. If None or not supported by this service, then this
                should be None.
            :param members: A list of UserBase objects representing all members in this channel.
        """
        members = [] if members is None else members
        super(Channel, self).__init__(name=name.lower(), display_name=display_name, description=description, members=members)
        self.connection = connection

    def send_message(self, message):
        """
            Sends a message to this channel.

            :param message: The message text to send to this channel.

            :rtype: MessageBase
            :return: A MessageBase instance representing the generated message.
        """
        result = Message(sender=None, raw_text=message, connection=self.connection, channels=[self])
        self.connection.say(channel=self.name, string=message)
        return result
