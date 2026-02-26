"""KloudKut — AWS Cost Optimization Tool."""
try:
    from importlib.metadata import version
    __version__ = version("kloudkut")
except Exception:
    __version__ = "5.1.0"
