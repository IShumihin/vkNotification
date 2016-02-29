class Message:
    def __init__(self, id=0, date=None, out=0, user_id=0, read_state=0, title='...', body='', user=None):
        self.id = id
        self.date = date
        self.out = out
        self.user_id = user_id
        self.read_state = read_state
        self.title = title
        self.body = body
        self.user = user

    def get_message_formated(self):
        if self.title == ' ... ':
            to = 'К' if self.out == 1 else 'От'
            text = '%s %s: %s' % (to, self.user.get_name(), self.body)
        else:
            if self.out == 1:
                text = 'В %s: %s' % (self.title, self.body)
            else:
                text = 'Из %s от %s: %s' % (self.title, self.user.get_name(), self.body)
        return text

    def get_message_for_notification(self):
        if self.out == 0:
            if self.title == ' ... ':
                text = self.user.get_name(), self.body
            else:
                text = 'Из %s от %s' % (self.title, self.user.get_name()), self.body
            return text
