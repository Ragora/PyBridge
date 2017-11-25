#!/usr/bin/python3
"""
    PyIRCBot is a bot written in Python that is designed to be simple to use.

    The technical design of the software is addon-oriented, therefore it is quite
    simple to add and remove functionality to the system as deemed necessary.

    This software is licensed under the MIT license, refer to LICENSE.txt for
    more information.

    Copyright (c) 2017 Robert MacGregor
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


class Application(object):
    """
        The main application class.
    """

    loaded_bridges = None

    loaded_plugins = None
    """
        A list of PluginBase instances representing loaded plugins.
    """

    should_run = None
    """
        Whether or not the bridging application should continue to run.
    """

    logger = None

    domains = None
    """
        A dictionary mapping domain names to a list of bridges that all are interconnected.
    """

    bridge_domains = None
    """
        A dictionary mapping bridge instances to the domain objects that they are in.
    """

    domain_event_handlers = None
    """
        A dictionary mapping domain names to their event handlers.
    """

    def __init__(self):
        """
            Initializes a new Application instance.
        """
        self.should_run = True
        self.domains = {}
        self.loaded_bridges = []
        self.bridge_domains = {}
        self.domain_event_handlers = {}

    def setup_and_run(self, configuration_data):
        """
            Configures the main bridging system and then loads all addons requested by the configuration file before
            starting everything.

            :param configuration_data: The parsed configuration data.
        """

        # Configure the home path.
        home_path = os.path.expanduser("~") + "/.pyBridge/"
        home_exists = os.path.exists(home_path)
        if home_exists is False:
            os.mkdir(home_path)

        # Load the bridges and plugins
        self.loaded_bridges = []
        self.loaded_plugins = []

        # Process each bridge and load the appropriate bridge code and assemble the broadcast domains.
        for domain in configuration_data.domains:
            event_handler = bridgesystem.EventHandler()
            self.domain_event_handlers[domain.name] = event_handler

            # load bridges first
            for bridge in domain.bridges:
                bridge_name = bridge.bridge

                try:
                    module = importlib.import_module("bridges.%s" % bridge_name)

                    # Initialize logging for this bridge
                    logger = logging.getLogger(bridge.name)
                    stream_handle = logging.StreamHandler()
                    formatter = logging.Formatter("(" + bridge.name + " Bridge in domain '" + domain.name + "') %(filename)s:%(lineno)d/%(funcName)s at %(asctime)s (%(levelname)s): %(message)s")
                    stream_handle.setFormatter(formatter)
                    logger.addHandler(stream_handle)

                    # If there's a logfile location in the config, add that
                    if configuration_data.global_configuration.process_internal.logfile is not None:
                        file_handle = logging.FileHandler(configuration_data.global_configuration.process_internal.logfile)
                        file_handle.setFormatter(formatter)
                        logger.addHandler(file_handle)

                    if configuration_data.global_configuration.process_internal.debug:
                        logger.setLevel(logging.DEBUG)

                    bridge_instance = module.Bridge(self, logger, home_path, bridge, configuration_data, event_handler=event_handler)
                    self.loaded_bridges.append(bridge_instance)

                    self.domains.setdefault(domain, [])
                    self.domains[domain].append(bridge_instance)
                    self.bridge_domains[bridge_instance] = domain
                except ImportError as e:
                    self.logger.error("!!! Failed to initialize bridge '%s': " % bridge_name)
                    self.logger.error(traceback.format_exc())
                    return False

            # Load plugins
            for plugin in domain.plugins:
                plugin_name = plugin.plugin
                module = importlib.import_module("plugins.%s" % plugin_name)

                # Initialize logging for this plugin
                logger = logging.getLogger("%s.%s" % (domain.name, plugin_name))
                stream_handle = logging.StreamHandler()
                formatter = logging.Formatter("(" + plugin_name + " Plugin in domain '" + domain.name + "') %(filename)s:%(lineno)d/%(funcName)s at %(asctime)s (%(levelname)s): %(message)s")
                stream_handle.setFormatter(formatter)
                logger.addHandler(stream_handle)

                # If there's a logfile location in the config, add that
                if configuration_data.global_configuration.process_internal.logfile is not None:
                    file_handle = logging.FileHandler(configuration_data.global_configuration.process_internal.logfile)
                    file_handle.setFormatter(formatter)
                    logger.addHandler(file_handle)

                if configuration_data.global_configuration.process_internal.debug:
                    logger.setLevel(logging.DEBUG)

                # Initialize the plugin instance and load configuration data
                plugin_instance = module.Plugin(self, logger, home_path, plugin, configuration_data, event_handler=event_handler)
                plugin_instance.load_configuration(configuration=plugin, global_configuration=configuration_data.global_configuration)
                self.loaded_plugins.append(plugin_instance)

                #self.domains.setdefault(domain, [])
                #self.domains[domain].append(bridge_instance)
                #self.bridge_domains[bridge_instance] = domain

        # Once everything is mapped, start up all of the loaded bridges and addons.
        for bridge in self.loaded_bridges:
            bridge.start()

        for plugin in self.loaded_plugins:
            plugin.start()

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
        try:
            while self.should_run:
                current_time = datetime.datetime.now()
                delta_time = current_time - last_time

                for bridge in self.loaded_bridges:
                    bridge.update(delta_time)

                if delta_time < process_sleepms:
                    slept_time = process_sleepms - delta_time
                    time.sleep(slept_time.total_seconds())

                last_time = current_time
        except KeyboardInterrupt as e:
            self.logger.info("Deinitializing bot because of KeyboardInterrupt.")
        self.logger.info("Deinitializing Bot ....")
        return True

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

        # Always initialize logging with a stream handler.
        self.logger = logging.getLogger("main")
        stream_handle = logging.StreamHandler()
        formatter = logging.Formatter("(Main System) - %(filename)s:%(lineno)d/%(funcName)s at %(asctime)s (%(levelname)s): %(message)s")
        stream_handle.setFormatter(formatter)
        self.logger.addHandler(stream_handle)

        # If there's a logfile location in the config, add that
        if configuration_data.global_configuration.process_internal.logfile is not None:
            file_handle = logging.FileHandler(configuration_data.global_configuration.process_internal.logfile)
            file_handle.setFormatter(formatter)
            self.logger.addHandler(file_handle)

        # Enable debug logging as per the config
        if configuration_data.global_configuration.process_internal.debug:
            self.logger.setLevel(logging.DEBUG)

        self.logger.info("Bridging bot initializing ...")
        while True:
            try:
                result = self.setup_and_run(configuration_data)

                if result is False:
                    self.logger.info("Bridging bot shutting down.")
                else:
                    self.logger.error("Bridging bot shutting down due to previous errors.")
            except BaseException as e:
                self.logger.error("!!! Encountered an unhandled exception: %s" % traceback.format_exc())

                if configuration_data.global_configuration.process_internal.auto_restart is False:
                    self.logger.error("!!! Exiting because autorestart is not enabled!")
                    break

            # Stop all running bridges and plugins
            for plugin in self.loaded_plugins:
                try:
                    plugin.stop()
                except BaseException as e:
                    self.logger.error("!!! Error stopping plugin '%s': \n%s" % (plugin.configuration.name, traceback.format_exc()))

            for bridge in self.loaded_bridges:
                try:
                    bridge.stop()
                except BaseException as e:
                    self.logger.error("!!! Error stopping bridge '%s': \n%s" % (bridge.configuration.name, traceback.format_exc()))

            # All else fails, force the python interpreter to full exit
            if configuration_data.global_configuration.process_internal.auto_restart is False:
                sys.exit(1)


if __name__ == "__main__":
    Application().main()
