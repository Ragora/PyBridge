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
import datetime
import traceback
import importlib

import irc

class Application(object):
    connections = None
    loaded_addons = None
    should_run = None

    def __init__(self):
        self.should_run = True
        self.loaded_addons = []
        self.connections = []

    def setup_and_run(self, configuration_data):
        # Build server blocks and initialize the connections
        for server_configuration in configuration_data["servers"]:
            connection = irc.Connection(configuration_data, server_configuration)
            connection.debug_prints_enabled = True
            self.connections.append(connection)

        # Load the addons
        self.loaded_addons = []
        for addon_configuration in configuration_data["configurations"]:
            addon_name = addon_configuration["addon"]

            try:
                module = importlib.import_module(addon_name)

                addon_instance = module.Addon(configuration_data["servers"], addon_configuration)
                self.loaded_addons.append(addon_instance)

                # Register the addon with all relevant connections
                for connection_index in addon_configuration["connections"]:
                    if connection_index < 0 or connection_index >= len(self.connections):
                        print("!!! Invalid connection: %u" % connection_index)
                        return

                    addon_instance.register_connection(self.connections[connection_index])
            except ImportError as e:
                print(e)

        for loaded_addon in self.loaded_addons:
            loaded_addon.start()

        process_sleepms = datetime.timedelta(milliseconds=configuration_data["sleepms"])

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

    def main(self):
        home_path = os.path.expanduser("~") + "/.pyIRCBot/"
        home_exists = os.path.exists(home_path)
        if (home_exists is False):
            os.system("mkdir %s" % home_path)

        # Load the configurations
        try:
            with open("configuration.json", "r") as handle:
                configuration_data = json.loads(handle.read())
        except json.decoder.JSONDecodeError as e:
            print("!!! Failed to load configuration.json: %s" % str(e))
            return

        if configuration_data["autorestart"] is True:
            while configuration_data["autorestart"] is True:
                try:
                    self.setup_and_run(configuration_data)
                except Exception as e:
                    traceback_text = traceback.format_exc()
                    print("!!! Encountered an unhandled exception: %s" % traceback_text)

                    # Stop all running addons
                    for addon in self.loaded_addons:
                        addon.stop()

                    # Stop all connections
                    for connection in self.connections:
                        connection.disconnect()

                    self.connections = []
        else:
            self.setup_and_run(configuration_data)

if __name__ == "__main__":
    Application().main()
