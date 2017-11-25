"""
    Python programming for the User class.
"""

from .message import Message

from bridgesystem import UserBase

class User(UserBase):
    """
        A class representing an IRC user.
    """

    connection = None
    """
        The IRC connection used for sending messages.
    """

    def __init__(self, connection, username):
        """
            Initializes a new IRC User.

            :param connection: The IRC connection used for sending messages.
        """
        super(User, self).__init__(username=username)
        self.connection = connection

    def send_message(self, message):
        """
            Sends a message to this IRC User object.

            :param message: The message text to send.

            :rtype: MessageBase
            :return: The generated MessageBase.
        """
        result = Message(sender=None, raw_text=message, connection=self.connection, channels=[self])
        self.connection.say_to(name=self.username, string=message)
        return result
