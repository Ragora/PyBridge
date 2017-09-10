"""
    Configuration loader programming.
"""

import json
import datetime

class ConfigurationBase(object):
    class ConfigurationValue(object):
        value = None
        """
            The final resolved value.
        """

        default = None
        """
            The default value.
        """

        value_type = None
        """
            The type this value should be.
        """

        value_constructor = None
        """
            The type constructor used to initialize the value.
        """

        validator = None
        """
            The validator to ensure sanity.
        """

        name = None
        """
            The name of the configuration key. If None, then the attribute name is utilized.
        """

        def __init__(self, name=None, default=None, value_type=None, value_constructor=None, validator=None):
            """
                Initializes a ConfigurationValue instance.

                :param default: The default value this configuration value should have.
                :param value_type: The type this configuration value should be. This is only a type comparison.
                :param value_constructor: If the value type passes or is None then this is used to construct the value.
                :param validator: If type validation passes then this validator is ran to ensure there's a valid value. Should be callable.
            """
            self.name = name
            self.default = default
            self.validator = validator
            self.value_type = value_type
            self.value_constructor = value_constructor

    def __init__(self, configuration={}):
        """
            Initializes a new configuration object.

            :param configuration: The raw decoded configuration from the configuration file.
        """

        def process_configuration_attribute(attribute_name, attribute_value):
            if type(attribute_value) is Configuration.ConfigurationValue:
                config_meta = attribute_value

                validator = config_meta.validator
                value_type = config_meta.value_type
                resolved_value = config_meta.default
                value_constructor = config_meta.value_constructor

                # Utilize the attribute value if no name is specified.
                config_name = config_meta.name if config_meta.name is not None else attribute_name

                # Resolve the value if there us ab ebtry here
                resolved_value = configuration[config_name] if config_name in configuration else resolved_value

                # If the constructor is specified and our key exists in config, decode it.
                if value_constructor is not None and config_name in configuration:
                    resolved_value = value_constructor(resolved_value)

                # If the type check is specified and our key exists in config, verify it.
                if value_type is not None and type(resolved_value) is not value_type:
                    print(resolved_value)
                    raise TypeError("Validation failed for configuration '%s'. Expected a %s." % (config_name, value_type))

                # If the validator exists, ensure our value is sane.
                if validator is not None and validator(resolved_value) is False:
                    raise RuntimeError("Validation failed for configuration '%s'." % config_name)

                setattr(self, attribute_name, resolved_value)

        for attribute_name, attribute_value in zip(self.__dict__.keys(), self.__dict__.values()):
            process_configuration_attribute(attribute_name, attribute_value)
        for attribute_name, attribute_value in zip(self.__class__.__dict__.keys(), self.__class__.__dict__.values()):
            process_configuration_attribute(attribute_name, attribute_value)

class Domain(ConfigurationBase):
    name = None
    """
        The name of the domain.
    """

    bridges = None
    """
        All bridges on this domain.
    """

    class Bridge(ConfigurationBase):
        name = None
        """
            The name of this bridge.
        """

        bridge =  None
        """
            The name of the bridge to use.
        """

        bridge_generic_config = None
        """
            The generic configuration for this bridge.
        """

        bridge_internal_config = None
        """
            The bridge specific configuration.
        """

        class BridgeGenericConfig(ConfigurationBase):
            """
                A class representing the bridge generic config sections on a per bridge basis.
            """

            ignore_senders = ConfigurationBase.ConfigurationValue(name="ignoreSenders", default=None, value_constructor=list)

            broadcast_name_changes = ConfigurationBase.ConfigurationValue(name="broadcastNameChanges", default=None, value_constructor=bool)
            broadcast_messages = ConfigurationBase.ConfigurationValue(name="broadcastMessages", default=None, value_constructor=bool)
            broadcast_join_leaves = ConfigurationBase.ConfigurationValue(name="broadcastJoinLeaves", default=None, value_constructor=bool)
            broadcasting_channels = ConfigurationBase.ConfigurationValue(name="broadCastingChannels", default=None, value_constructor=list)
            receiving_channels = ConfigurationBase.ConfigurationValue(name="receivingChannels", default=None, value_constructor=list)
            large_block_delay_seconds = ConfigurationBase.ConfigurationValue(name="largeBlockDelaySeconds", default=None, value_constructor=float)

            def __init__(self, configuration={}):
                super(Domain.Bridge.BridgeGenericConfig, self).__init__(configuration)

        def __init__(self, configuration={}):
            self.name = ConfigurationBase.ConfigurationValue(name="name", value_constructor=str)
            self.bridge = ConfigurationBase.ConfigurationValue(name="bridge", value_constructor=str)
            self.bridge_generic_config = ConfigurationBase.ConfigurationValue(name="bridgeGenericConfig", value_constructor=Domain.Bridge.BridgeGenericConfig)
            self.bridge_internal_config = ConfigurationBase.ConfigurationValue(name="bridgeInternalConfig", value_constructor=dict)
            super(Domain.Bridge, self).__init__(configuration)

    def __init__(self, configuration={}):
        self.name = ConfigurationBase.ConfigurationValue(name="name", value_constructor=str)
        self.bridges = ConfigurationBase.ConfigurationValue(name="bridges", value_constructor=lambda elements: [Domain.Bridge(element) for element in elements])
        super(Domain, self).__init__(configuration)

class Configuration(ConfigurationBase):
    """
        Root configuration object.
    """

    global_configuration = None
    """
        Global configuration data.
    """

    domains = None
    """
        The list of domain configurations.
    """

    def __init__(self, configuration={}):
        self.domains = ConfigurationBase.ConfigurationValue(name="domains", value_constructor=lambda elements: [Domain(element) for element in elements])
        self.global_configuration = ConfigurationBase.ConfigurationValue(name="globalConfiguration", value_constructor=GlobalConfiguration)
        super(Configuration, self).__init__(configuration)

        # For every generic config set to None we load it from the defaults
        bridge_default_config = self.global_configuration.bridge_default_generic_config
        for domain in self.domains:
            for bridge in domain.bridges:
                bridge_generic_config = bridge.bridge_generic_config

                for class_attribute, class_value in zip(bridge_generic_config.__class__.__dict__.keys(), bridge_generic_config.__class__.__dict__.values()):
                    current_value = getattr(bridge_generic_config, class_attribute)
                    if type(class_value) is ConfigurationBase.ConfigurationValue and current_value is None:
                        setattr(bridge_generic_config, class_attribute, getattr(bridge_default_config, class_attribute))

    @staticmethod
    def from_file(path):
        with open(path, "r") as handle:
            return Configuration.from_configuration_data(json.loads(handle.read()))

    @staticmethod
    def from_configuration_data(configuration):
        return Configuration(configuration)

class GlobalConfiguration(ConfigurationBase):
    """
        A class representing the global configuration data.
    """

    class ProcessInternal(ConfigurationBase):
        def __init__(self, configuration={}):
            self.sleep_ms = ConfigurationBase.ConfigurationValue(name="sleepMS", default=32, value_type=int)
            self.auto_restart = ConfigurationBase.ConfigurationValue(name="autoRestart", default=False, value_type=bool)

            super(GlobalConfiguration.ProcessInternal, self).__init__(configuration)

        sleep_ms = None
        """
            How long the process should sleep between ticks.
        """

        auto_restart = None
        """
            If an internal error occurs, should the process attempt to restart itself.
        """

    class ImageHosting(ConfigurationBase):
        def __init__(self, configuration={}):
            self.enabled = ConfigurationBase.ConfigurationValue(name="enabled", default=False, value_type=bool)
            self.image_path_base = ConfigurationBase.ConfigurationValue(name="imagePathBase", value_type=str)
            self.image_url_base = ConfigurationBase.ConfigurationValue(name="imageURLBase", value_type=str)

            super(GlobalConfiguration.ImageHosting, self).__init__(configuration)

        enabled = None
        """
            If image hosting is enabled.
        """

    class BridgeDefaultGenericConfig(ConfigurationBase):
        ignore_senders = ConfigurationBase.ConfigurationValue(name="ignoreSenders", default=[], value_constructor=list)
        broadcast_messages = ConfigurationBase.ConfigurationValue(name="broadcastMessages", default=True, value_constructor=bool)
        broadcast_join_leaves = ConfigurationBase.ConfigurationValue(name="broadcastJoinLeaves", default=True, value_constructor=bool)
        broadcasting_channels = ConfigurationBase.ConfigurationValue(name="broadCastingChannels", default=[], value_constructor=list)
        receiving_channels = ConfigurationBase.ConfigurationValue(name="receivingChannels", default=[], value_constructor=list)
        large_block_delay_seconds = ConfigurationBase.ConfigurationValue(name="largeBlockDelaySeconds", default=datetime.timedelta(seconds=2), value_constructor=lambda input: datetime.timedelta(seconds=input))
        broadcast_name_changes = ConfigurationBase.ConfigurationValue(name="broadcastNameChanges", default=True, value_constructor=bool)

        def __init__(self, configuration={}):
            super(GlobalConfiguration.BridgeDefaultGenericConfig, self).__init__(configuration)

    process_internal = None
    """
        Process internal configuration data.
    """

    image_hosting = None
    """
        Image hosting configuration data.
    """

    bridge_default_generic_config = None
    """
        Default bridge configuration data.
    """

    def __init__(self, configuration={}):
        self.process_internal = ConfigurationBase.ConfigurationValue(name="processInternal", default=GlobalConfiguration.ProcessInternal(), value_constructor=GlobalConfiguration.ProcessInternal)
        self.image_hosting = ConfigurationBase.ConfigurationValue(name="imageHosting", value_constructor=GlobalConfiguration.ImageHosting)
        self.bridge_default_generic_config = ConfigurationBase.ConfigurationValue(name="bridgeDefaultGenericConfig", default=GlobalConfiguration.BridgeDefaultGenericConfig(), value_constructor=GlobalConfiguration.BridgeDefaultGenericConfig)
        super(GlobalConfiguration, self).__init__(configuration)
