"""
    Python programming for the Message class.
"""

from bridgesystem import MessageBase

class Message(MessageBase):
    """
        A class representing sent and received messages on the Telegram bridge.
    """

    connection = None
    """
        The telegram connection object used for sending messages.
    """

    message_instance = None
    """
        The telegram message instance.
    """

    def __init__(self, sender, message_instance, connection, channels, text=None):
        """
            Initializes a new Telegram message.

            :param connection: The IRC connection object used for sending messages.
            :param sender: The UserBase object that has sent this message.
            :param raw_text: The IRC message text.
            :param channels: A list of ChannelBase objects that this message was sent to.
        """

        text = text if text is not None else message_instance.text
        super(Message, self).__init__(raw_text=text, channels=channels, sender=sender, pinned=message_instance.pinned_message is not None)
        self.connection = connection
        self.message_instance = message_instance

    def pin(self, pinned=True):
        """
            Pins this IRC message. IRC does not support message pinning, so this is ignored.

            :param pinned: Whether or not this message was pinned.
        """
        if pinned:
            self.connection.pin_chat_message(chat_id=self.message_instance.chat.id, message_id=self.message_instance.id)
        else:
            self.connection.unpin_chat_message(chat_id=self.message_instance.chat.id, message_id=self.message_instance.id)
        self.pinned = pinned

    def edit(self, new_text):
        """
            Changes the message text on the service it is associated with. Note this does not actually change
            the message on all bridged services, therefore this should be called across all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should
            approximate the behavior as closely as possible.

            :param new_text: The new text of this message.
        """
        self.message_instance = self.message_instance.edit_text(text=new_text)

    def delete(self):
        """
            Deletes the message from the service it is associated with. Note this does not actually delete the
            message on all bridged services, therefore this should be called on all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should approximate
            the behavior as closely as possible.
        """
        self.message_instance.delete()
