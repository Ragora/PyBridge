"""
    Python programming for the User class.
"""

from .message import Message

from bridgesystem import UserBase

class User(UserBase):
    """
        A class representing a Discord user.
    """

    connection = None
    """
        The Discord connection used for sending messages.
    """

    user_instance = None
    """
        The user instance associated with this User.
    """

    event_loop = None

    def __init__(self, connection, user_instance, event_loop):
        """
            Initializes a new Discord User.

            :param connection: The IRC connection used for sending messages.
        """
        super(User, self).__init__(username=user_instance.name)
        self.connection = connection
        self.user_instance = user_instance
        self.event_loop = event_loop

    def send_message(self, message):
        """
            Sends a message to this IRC User object.

            :param message: The message text to send.

            :rtype: MessageBase
            :return: The generated MessageBase.
        """
        self.event_loop.create_task(self.connection.send_message(self.user_instance, message))
        return None
