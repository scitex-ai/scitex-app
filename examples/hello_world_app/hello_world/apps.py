from scitex_app.embed import ScitexAppConfig


class HelloWorldConfig(ScitexAppConfig):
    """A SciTeX app is a Django app whose AppConfig comes from the SDK.

    Subclassing ``ScitexAppConfig`` rather than ``django.apps.AppConfig`` is
    what makes this a SciTeX app: it loads and validates the ``manifest.json``
    beside this file.

    There is deliberately NO ``try/except ImportError`` fallback to plain
    ``AppConfig`` here. A fallback lets the app keep running while silently
    ceasing to be a SciTeX app — the contract evaporates at exactly the moment
    it goes missing, and everything downstream still believes it is in force.
    Let the ImportError be the error.
    """

    name = "hello_world"
    label = "hello_world"
    verbose_name = "Hello World"
