#noinspection PyMissingConstructor
class Env(dict):
    """
    A dictionnary whose objects can be accessed by '.' notation, saving a few
    keystrokes.
    """

    def __init__(self, label=None, **kw):
        #self.bread_crumbs = self.breadcrumbs = make_bread_crumbs(label=label)
        for key, value in kw.items():
            self[key] = value

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, key):
        return self[key]
