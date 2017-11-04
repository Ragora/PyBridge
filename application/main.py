#!/usr/bin/python3
"""
    PyIRCBot is a bot written in Python that is designed to be simple to use.

    The technical design of the software is addon-oriented, therefore it is quite
    simple to add and remove functionality to the system as deemed necessary.

    This software is licensed under the MIT license, refer to LICENSE.txt for
    more information.

    Copyright (c) 2016 Robert MacGregor
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import datetime
import traceback
import importlib
import mimetypes
import bridgesystem
# from bridgebase import AddonConfigurationError

class Application(object):
    """
        The main application class.
    """

    connections = None
    loaded_addons = None
    should_run = None
    """
        Whether or not the bridging application should continue to run.
    """

    logger = None

    connection_bridges = None

    def __init__(self):
        self.should_run = True
        self.loaded_addons = []
        self.connections = []
        self.connection_bridges = {}

    def on_receive_join(self, sender, joined_name, target_channels):
        print(joined_name)

    def setup_and_run(self, configuration_data):
        """
            Configures the main bridging system and then loads all addons requested by the configuration file before
            starting everything.
        """

        # Configure the home path.
        home_path = os.path.expanduser("~") + "/.pyBridge/"
        home_exists = os.path.exists(home_path)
        if home_exists is False:
            os.mkdir(home_path)

        # Load the addons
        self.loaded_addons = []

        # Process each bridge and load the appropriate bridge code and assemble the broadcast domains.
        for domain in configuration_data.domains:
            domain_bridges = []
            for bridge in domain.bridges:
                bridge_name = bridge.bridge

                try:
                    module = importlib.import_module("bridges.%s" % bridge_name)

                    # Initialize logging for thid bridge
                    logger = logging.getLogger(bridge.name)
                    stream_handle = logging.StreamHandler()
                    formatter = logging.Formatter(bridge.name + " at %(asctime)s: %(message)s")
                    stream_handle.setFormatter(formatter)
                    logger.addHandler(stream_handle)
                    if configuration_data.global_configuration.process_internal.debug:
                        logger.setLevel(logging.DEBUG)

                    addon_instance = module.Bridge(self, logger, home_path, bridge, configuration_data)
                    self.loaded_addons.append(addon_instance)

                    domain_bridges.append(addon_instance)
                except ImportError as e:
                    print("!!! Failed to initialize bridge '%s': " % bridge_name)
                    print(traceback.format_exc())
                    return False

            # For all bridges, construct the domain
            for added_bridge in domain_bridges:
                for target_bridge in domain_bridges:
                    if added_bridge is target_bridge:
                        continue

                    self.connection_bridges.setdefault(target_bridge, [])
                    self.connection_bridges[target_bridge].append(added_bridge)

        # Once everything is mapped, start up all of the loaded addons.
        for loaded_addon in self.loaded_addons:
            loaded_addon.start()

        # Initilize other libs
        # FIXME: This is a quick hack to ensure jpeg gets a reasonable extension
        if ".jpe" in mimetypes.types_map:
            del mimetypes.types_map[".jpe"]

        process_sleepms = datetime.timedelta(milliseconds=configuration_data.global_configuration.process_internal.sleep_ms)

        # Handle sigterm to tear everything down
        def termination_handler(signum, frame):
            self.should_run = False
        signal.signal(signal.SIGTERM, termination_handler)

        last_time = datetime.datetime.now()
        while self.should_run:
            current_time = datetime.datetime.now()
            delta_time = current_time - last_time

            for addon in self.loaded_addons:
                addon.update(delta_time)

            for connection in self.connections:
                connection.update(delta_time)

            if delta_time < process_sleepms:
                slept_time = process_sleepms - delta_time
                time.sleep(slept_time.total_seconds())

            last_time = current_time

        print("!!! Deinitializing Bot ....")

        # Stop all running addons
        for addon in self.loaded_addons:
            addon.stop()

        # Stop all connections
        for connection in self.connections:
            connection.disconnect()
        return True

    def broadcast_event(self, name, sender, *args, **kwargs):
        """
            Broadcasts an event globally across all addons.

            :param name: The event to broadcast. Addons that don't know about this event simply ignore it.
            :param sender: The addon instance that dispatched this event. This is used for mapping broadcast domains.
            :param args: The positional arguments to pass to the addons.
            :param kwargs: The keyword arguments to pass to the addons.
        """
        for addon in self.connection_bridges[sender]:
            addon.receive_event(sender=sender, name=name, *args, **kwargs)

    def main(self):
        """
            Main process entry point. Performs configuration parsing and init.
        """

        # Compute defaults
        default_configuration_path = os.path.join(os.getcwd(), "configuration.json")

        # Process commandline parameters
        parser = argparse.ArgumentParser()
        parser.add_argument("--configuration", default=default_configuration_path, help="If specified, then this will be the full path to the configuration file to use. Otherwise, it is assumed to be in the current working directory: %s" % default_configuration_path)
        result = vars(parser.parse_args())

        # Load the configuration file and go
        configuration_data = bridgesystem.Configuration.from_file(result["configuration"])

        # Initialize logging
        self.logger = logging.getLogger("main")
        stream_handle = logging.StreamHandler()
        formatter = logging.Formatter("Main at %(asctime)s: %(message)s")
        stream_handle.setFormatter(formatter)
        self.logger.addHandler(stream_handle)
        if configuration_data.global_configuration.process_internal.debug:
            self.logger.setLevel(logging.DEBUG)

        self.logger.info("Bridging bot initializing ...")
        if configuration_data.global_configuration.process_internal.auto_restart is True:
            while configuration_data.global_configuration.process_internal.auto_restart is True:
                try:
                    self.setup_and_run(configuration_data)
                except Exception as e:
                    traceback_text = traceback.format_exc()
                    self.logger.error("!!! Encountered an unhandled exception: %s" % traceback_text)

                    # Stop all running addons
                    for addon in self.loaded_addons:
                        addon.stop()

                    # Stop all connections
                    for connection in self.connections:
                        connection.disconnect()

                    self.connections = []
        else:
            try:
                self.setup_and_run(configuration_data)
            except Exception as e:
                traceback_text = traceback.format_exc()
                self.logger.error("!!! Encountered an unhandled exception: %s" % traceback_text)
                self.logger.error("!!! Exiting because autorestart is not enabled!")

                # Stop all running addons
                for addon in self.loaded_addons:
                    addon.stop()

                # Stop all connections
                for connection in self.connections:
                    connection.disconnect()

if __name__ == "__main__":
    Application().main()
