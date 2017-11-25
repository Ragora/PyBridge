"""
    Python programming for the MessageBase class.
"""


class MessageBase(object):
    """
        A class representing a specialized message for a given service. All bridges should derive a class
        from this class and implement all functions and properties.
    """

    sender = None
    """
        The UserBase object that had sent this message.
    """

    raw_text = None
    """
        The raw text of the message provided by the service.
    """

    clean_text = None
    """
        The cleaned up version of the raw message text. The expected conversion here is all non-standard sequences
        (on Eg. Discord) representing emoticons and similar should be converted to their actual unicode representation
        and all username, channel and server references converted to their generalized representation.
    """

    channels = None
    """
        A list of ChannelBase objects representing the original destination channels of this message on the service
        this message is associated with.
    """

    date = None
    """
        A datetime.datetime object representing when this message was sent and received. This is primarily used
        for memory optimization by cleaning out sufficiently old messages from the edit/delete association table.
    """

    pinned = None
    """
        A boolean representing that this message is pinned on the service it is associated with. This should be None
        if message pinning is not supported.
    """

    def __init__(self, sender=None, raw_text=None, channels=None, pinned=None, clean_text=None):
        """
            Initializes a MessageBase object.

            :param sender: The UserBase object that has sent this message.
            :param raw_text: The raw, unmolested message text.
            :param channels: A list of ChannelBase objects that this message was sent to.
            :param pinned: Whether or not this message was pinned.
            :param clean_text: The cleaned up version of raw_text if available.
        """
        self.sender = sender
        self.pinned = pinned
        self.raw_text = raw_text
        self.clean_text = clean_text
        self.channels = channels if hasattr(channels, "__iter__") else [channels]

    def pin(self, pinned=True):
        """
            Pins the message in the service it is associated with. If this is not supported in the service then this should
            be approximated as closely as possible.

            :param pinned: Whether or not this message was pinned.
        """
        raise NotImplementedError("Cannot pin: Not implemented.")

    def edit(self, new_text):
        """
            Changes the message text on the service it is associated with. Note this does not actually change
            the message on all bridged services, therefore this should be called across all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should
            approximate the behavior as closely as possible.

            :param new_text: The new text of this message.
        """
        raise NotImplementedError("Cannot edit: Not implemented.")

    def delete(self):
        """
            Deletes the message from the service it is associated with. Note this does not actually delete the
            message on all bridged services, therefore this should be called on all linked messages.

            If this functionality is not supported on the end service (Eg. IRC), then this function should approximate
            the behavior as closely as possible.
        """
        raise NotImplementedError("Cannot delete: Not implemented.")
