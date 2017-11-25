"""
    Python programming for the EventHandler class.
"""

import inspect


class EventHandler(object):
    """
        A class representing an object that handles events that are raised globally within the bot. This is the backbone of the
        bridging system and is the primary method of communication between the loaded bridges within a given domain.
    """

    event_map = None
    """
        A dictionary mapping event names to a list of responders.
    """

    event_result_hook_map = None
    """
        A dictionary mapping event names to a list of result hooks.
    """

    class Events(object):
        """
            An enumeration representing the standard event set supported by the bot. It is not strictly necessary to only use these;
            you can implement custom events should it fit your uses.
        """

        OnReceivePosePrivate = "OnReceivePosePrivate"
        """
            An event representing when a user sends a private pose to the bot.
        """

        OnReceiveMessagePrivate = "OnReceiveMessagePrivate"
        """
            An event representing when a user sends a private message to the bot.
        """

        OnReceivePose = "OnReceivePose"
        """
            An event representing when a user sends a pose to a channel. Most typically this is a /me command
            of some form.
        """

        OnReceiveMessage = "OnReceiveMessage"
        """
            An event representing when a user sends a message to a channel.
        """

        OnReceiveLeave = "OnReceiveLeave"
        """
            An event representing when a user leaves a channel.
        """

        OnReceiveJoin = "OnReceiveJoin"
        """
            An event representing when a user joins a channel.
        """

        OnMessageEdit = "OnMessageEdit"
        """
            An event representing when a message is edited.
        """

        OnMessageDelete = "OnMessageDelete"
        """
            An event representing when a message is deleted.
        """

    def __init__(self):
        """
            Initializes a new EventHandler.
        """
        self.event_map = {}
        self.event_result_hook_map = {}

    def receive_event(self, name, *args, **kwargs):
        """
            Raises an event within this bridge.

            :param name: The name of the event to raise. If there is no event going by this name, nothing happens.
            :param *args: All positional args to pass to the events.
            :param kwargs: All key word args to pass to the events.

            :rtype: list
            :return: A list of all return values produced by all responders listening for this event.
        """
        # Quietly do nothing because there isn't any responder for this.
        if name not in self.event_map:
            return

        result = []
        for responder in self.event_map[name]:
            #try:
            result.append(responder(*args, **kwargs))
            #except BaseException as e:
            #    pass
                # FIXME: Process and log the error in some way.

        if name in self.event_result_hook_map.keys():
            try:
                for responder in self.event_result_hook_map[name]:
                    responder(result)
            except BaseException as e:
                pass
        return result

    def broadcast_event(self, name, emitter, *args, **kwargs):
        """
            Broadcasts an event globally across all addons.

            :param name: The event to broadcast. Addons that don't know about this event simply ignore it.
            :param sender: The bridge instance that dispatched this event. This is used for mapping broadcast domains.
            :param args: The positional arguments to pass to the addons.
            :param kwargs: The keyword arguments to pass to the addons.

            :rtype: list
            :return: A list of all return values produced by all called responders.
        """
        return self.receive_event(emitter=emitter, name=name, *args, **kwargs)

    def register_event_result_hook(self, name, responder):
        """
            Registers an event result hook to the system. The responder function will be called with the result set of the
            event.

            :param name: The name of the event. This can be any identifier that can be used as a dictionary key.
            :param responder: The function to call for when this event is raised.
        """
        responder_argument_count = responder.__code__.co_argcount
        if inspect.ismethod(responder):
            responder_argument_count -= 1

        if responder_argument_count != 1:
            raise AddonMismatchedEventArgsError("Attempted to register a responder to event '%s' using a function accepting %u parameters! Expected 1." % (name, responder.__code__.co_argcount))

        self.event_result_hook_map.setdefault(name, [])
        self.event_result_hook_map[name].append(responder)

    def register_event(self, name, responder):
        """
            Registers an event responder. If the responder is the first responder being registed for an event
            type, it defines the expected function signature for all further registered responders.

            :param name: The name of the event. This can be any identifier that can be used as a dictionary key.
            :param responder: The function to call for when this event is raised.
        """
        self.event_map.setdefault(name, [])

        # Verify that all functions have the same signature if we have any events defined already
        if len(self.event_map[name]) != 0:
            first_responder = self.event_map[name][0]

            responder_argument_count = responder.__code__.co_argcount
            if inspect.ismethod(responder):
                responder_argument_count -= 1

            #if first_responder.__code__.co_argcount != responder_argument_count:
            #    raise BaseException("Attempted to register a responder to event '%s' using a function accepting %u parameters! Expected %u." % (name, responder.__code__.co_argcount, first_responder.__code__.co_argcount))
        self.event_map[name].append(responder)
