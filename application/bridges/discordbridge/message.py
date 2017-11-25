"""
    Python programming for the Message class.
"""

from bridgesystem import MessageBase

class Message(MessageBase):
    """
        A class representing sent and received messages on the Discord bridge.
    """

    connection = None
    """
        The Discord connection object used for sending messages.
    """

    message_instance = None
    """
        The Discord message instance.
    """

    event_loop = None

    def __init__(self, message_instance, sender, event_loop, channels, connection):
        """
            Initializes a new Discord message.

            :param connection: The IRC connection object used for sending messages.
            :param sender: The UserBase object that has sent this message.
            :param raw_text: The IRC message text.
            :param channels: A list of ChannelBase objects that this message was sent to.
        """
        super(Message, self).__init__(raw_text=message_instance.clean_content if message_instance is not None else None, channels=channels, sender=sender)
        self.connection = connection
        self.event_loop = event_loop
        self.message_instance = message_instance

    def pin(self, pinned=True):
        """
            Pins this Discord message.

            :param pinned: Whether or not this message was pinned.
        """
        if self.message_instance is not None:
            if pinned:
                self.event_loop.create_task(self.connection.pin_message(self.message_instance))
            else:
                self.event_loop.create_task(self.connection.unpin_message(self.message_instance))
            self.pinned = pinned

    def edit(self, new_text):
        """
            Changes the message text on the service it is associated with. Note this does not actually change
            the message on all bridged services, therefore this should be called across all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should
            approximate the behavior as closely as possible.

            :param new_text: The new text of this message.
        """
        if self.message_instance is not None:
            self.event_loop.create_task(self.connection.edit_message(self.message_instance, new_content=new_text))

    def delete(self):
        """
            Deletes the message from the service it is associated with. Note this does not actually delete the
            message on all bridged services, therefore this should be called on all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should approximate
            the behavior as closely as possible.
        """
        if self.message_instance is not None:
            self.event_loop.create_task(self.connection.delete_message(self.message_instance))
