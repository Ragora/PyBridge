"""
    Python programming for the User class.
"""

from .message import Message

from bridgesystem import UserBase

class User(UserBase):
    """
        A class representing an Telegram user.
    """

    connection = None
    """
        The Telegram connection used for sending messages.
    """

    user_instance = None
    """
        The telegram user instance.
    """

    def __init__(self, connection, user_instance):
        """
            Initializes a new Telegram User.

            :param connection: The IRC connection used for sending messages.
        """
        super(User, self).__init__(username=user_instance.name)
        self.connection = connection
        self.user_instance = user_instance

    def send_message(self, message):
        """
            Sends a message to this IRC User object.

            :param message: The message text to send.

            :rtype: MessageBase
            :return: The generated MessageBase.
        """
        chat_instance = self.connection.get_chat(chat_id=self.user_instance.id)
        return Message(sender=None, message_instance=self.connection.send_message(text=message, chat_id=chat_instance.id), connection=self.connection, channels=None)
