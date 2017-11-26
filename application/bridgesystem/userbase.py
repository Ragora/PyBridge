"""
    Python proghramming representing a generalized system service user.
"""


class UserBase(object):
    """
        The base class for specialized user objects. All bridges should derive a child class
        from this and implement all functions and properties.
    """

    display_name = None
    """
        The display name of this user. Note this is the actual displayed name on services
        where this can be different than their actual username.
    """

    username = None
    """
        The username that the service identifies this user by. The display_name should be preferred
        if it is available.
    """

    def __init__(self, username, display_name=None):
        """
            Initializes a new UserBase instance.

            :param username: The username that the service identifies this user by. The display_name should be preferred
                if it is available.
            :param display_name: The display name of this user. Note this is the actual displayed name on services
                where this can be different than their actual username.
        """
        self.username = username
        self.display_name = display_name

    def send_message(self, message):
        """
            Sends a message to this Userbase object.

            :param message: The message text to send.

            :rtype: MessageBase
            :return: The generated MessageBase.
        """
        raise NotImplementedError("Cannot send_message: Not implemented.")

    def send_reply(self, message, channels=None):
        """
            Sends a reply message to this UserBase object.

            :param message: The message text to send.
            :message channels: A list of channels to send the reply to. If None, then the reply is sent directly to the user.
        """
        if channels is None:
            return self.send_message(message=message)
        message = "@%s: %s" % (self.username, message)
        return [channel.send_message(message=message) for channel in channels]
