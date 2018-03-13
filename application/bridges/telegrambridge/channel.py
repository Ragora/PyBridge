"""
    Python programming for the Channel class.
"""

from .message import Message
from bridgesystem import ChannelBase

class Channel(ChannelBase):
    """
        A class representing an Telegram channel in the bot.
    """

    connection = None
    """
        The Telegram connection object used to send and receive messages from the server.
    """

    chat_instance = None
    """
        The chat instance.
    """

    def __init__(self, connection, chat_instance, name=None):
        """
            :param connection: The Telegram connection object used to send and receive messages from the server.
            :param chat_instance: The telegram chat instance this channel is associated with.
        """
        self.connection = connection
        self.chat_instance = chat_instance

        name = name if name is not None else self.chat_instance.title
        super(Channel, self).__init__(name=name, display_name=None, description=None, members=[])

    def send_message(self, message):
        """
            Sends a message to this channel.

            :param message: The message text to send to this channel.

            :rtype: MessageBase
            :return: A MessageBase instance representing the generated message.
        """
        return Message(message_instance=self.connection.send_message(text=message, chat_id=self.chat_instance.id),
                       sender=None, connection=self.connection, channels=[self])
