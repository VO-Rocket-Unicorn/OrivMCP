"""Third-party usage instrumentation plugins.

Only :class:`UsagePlugin` is re-exported here. Concrete plugins live in
submodules that require optional extras and should be imported directly,
e.g.::

    from lib_oriv_telemetry.instrumentation.dspy import DSPyPredictionUsagePlugin
    from lib_oriv_telemetry.instrumentation.mistralai import OCRUsagePlugin
"""

from lib_oriv_telemetry.instrumentation.base import UsagePlugin

__all__ = ["UsagePlugin"]
