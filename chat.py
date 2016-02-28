class Chat:
    def __init__(self, id=0, type=None, title='', admin_id=0, users=None):
        self.id = id
        self.type = type
        self.title = title
        self.admin_id = admin_id
        self.users = users

    def get_name(self):
        return "%s" % self.title
