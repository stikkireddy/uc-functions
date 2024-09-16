class DatabricksSecret:

    def __init__(self, scope, key, *, default_value):
        self.scope = scope
        self.key = key
        self.default_value = default_value
