class LineItemDoesNotExist(Exception):
    def __init__(self, resource):
        self.resource = resource
