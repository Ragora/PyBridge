"""
    Python programming for the Message class.
"""

from bridgesystem import MessageBase

class Message(MessageBase):
    """
        A class representing sent and received messages on the IRC bridge.
    """

    connection = None
    """
        The IRC connection object used for sending messages.
    """

    def __init__(self, sender, raw_text, channels, connection):
        """
            Initializes a new IRC message.

            :param connection: The IRC connection object used for sending messages.
            :param sender: The UserBase object that has sent this message.
            :param raw_text: The IRC message text.
            :param channels: A list of ChannelBase objects that this message was sent to.
        """
        super(Message, self).__init__(raw_text=raw_text, channels=channels, sender=sender)
        self.connection = connection

    def pin(self, pinned=True):
        """
            Pins this IRC message. IRC does not support message pinning, so this is ignored.

            :param pinned: Whether or not this message was pinned.
        """

    def edit(self, new_text):
        """
            Changes the message text on the service it is associated with. Note this does not actually change
            the message on all bridged services, therefore this should be called across all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should
            approximate the behavior as closely as possible.

            :param new_text: The new text of this message.
        """

    def delete(self):
        """
            Deletes the message from the service it is associated with. Note this does not actually delete the
            message on all bridged services, therefore this should be called on all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should approximate
            the behavior as closely as possible.
        """
