"""
    Python programming implementing the ChannelBase class.
"""


class ChannelBase(object):
    """
        A base class representing a channel. All bridges should derive a class from this channel and implement all functions
        and properties.
    """

    name = None
    """
        The raw name of this channel.
    """

    display_name = None
    """
        The name of this channel without any service specific decorators such as IRC #channelName.
    """

    description = None
    """
        The description associated with this channel. If None or not supported by this service, then this
        should be None.
    """

    members = None
    """
        A list of UserBase objects representing all members in this channel.
    """

    def __init__(self, name, display_name, description, members):
        """
            Initializes a new ChannelBase object.

            :param name: The raw name of this channel.
            :param display_name: The name of this channel without any service specific decorators such as IRC #channelName.
            :param description: The description associated with this channel. If None or not supported by this service, then this
                should be None.
            :param members: A list of UserBase objects representing all members in this channel.
        """
        self.name = name
        self.members = members
        self.description = description
        self.display_name = display_name

    def send_message(self, message):
        """
            Sends a message to this channel.

            :param message: The message text to send to this channel.

            :rtype: MessageBase
            :return: A MessageBase instance representing the generated message.
        """
        raise NotImplementedError("Cannot send_message: Not implemented.")
