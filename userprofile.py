class UserProfile:
    def __init__(self, id=0, first_name=None, last_name=None, screen_name=None, photo=None, online=0):
        self._id = id
        self.first_name = first_name
        self.last_name = last_name
        self.screen_name = screen_name
        self.photo = photo
        self.online = online

    def get_name(self):
        return "%s %s (%s)" % (self.last_name, self.first_name, self.screen_name)