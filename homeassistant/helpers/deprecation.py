"""Deprecation helpers for Home Assistant."""

import inspect
import logging


def deprecated_substitute(substitute_name):
    """Help migrate properties to new names.

    When a property is added to replace an older property, this decorator can
    be added to the new property, listing the old property as the substitute.
    If the old property is defined, it's value will be used instead, and a log
    warning will be issued alerting the user of the impending change.
    """
    def decorator(func):
        """Decorator function."""
        def func_wrapper(self):
            """Wrapper for original function."""
            if hasattr(self, substitute_name):
                # If this platform is still using the old property, issue
                # a logger warning once with instructions on how to fix it.
                warnings = getattr(func, '_deprecated_substitute_warnings', {})
                module_name = self.__module__
                if not warnings.get(module_name):
                    logger = logging.getLogger(module_name)
                    logger.warning(
                        "{0} is deprecated. Please rename {0} to "
                        "{1} in '{2}' to ensure future support.".format(
                            substitute_name, func.__name__,
                            inspect.getfile(self.__class__)))
                    warnings[module_name] = True
                    func._deprecated_substitute_warnings = warnings

                # Return the old property
                return getattr(self, substitute_name)
            else:
                return func(self)
        return func_wrapper
    return decorator


def get_deprecated(config, new_name, old_name, default=None):
    """Allow an old config name to be deprecated with a replacement.

    If the new config isn't found, but the old one is, the old value is used
    and a warning is issued to the user.
    """
    if old_name in config:
        module_name = inspect.getmodule(inspect.stack()[1][0]).__name__
        logger = logging.getLogger(module_name)
        logger.warning(
            "{0} is deprecated. Please rename {0} to {1} in your "
            "configuration file.".format(old_name, new_name))
        return config.get(old_name)
    return config.get(new_name, default)
