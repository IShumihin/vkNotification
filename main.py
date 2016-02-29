from vk_api import *
import json
from message import Message
from userprofile import UserProfile
from chat import Chat
import os
import requests


class Main:
    # указать свои данные для авторизации

    __users = {}  # множество профилей пользователей
    __chats = {}  # множество бесед
    platforms = {  # платформы
        1: 'mobile',
        2: 'iphone',
        3: 'ipad',
        4: 'android',
        5: 'wphone',
        6: 'windows',
        7: 'web'
    }

    def __init__(self, login, password, debug=None, loop=False):
        self.codes = {  # ответы
            # 0: lambda u: 'Сообение %s удалено' % u[1],
            # 1: lambda u: 'Замена флагов сообщения %s на %s' % (u[1], u[2]),
            # 2: lambda u: 'Установка флагов сообщени %s на %s' % (u[1], u[2]),
            # 3: lambda u: 'сброс флагов сообщения %s на %s' % (u[1], u[2]),
            # 4: lambda u: 'Добавление нового сообщения %s' % (u[1]),
            # 6: lambda u: 'Вы прочитали все входящие сообщения от %s  по %s' % (get_user(vk, u[1]).get_name(), u[2]),
            7: lambda u: '%s прочитал все исходящие сообщения по %s' % (self.__get_name(u[1]), u[2]),
            8: lambda u: '%s онлайн (%s)' % (self.__get_user(u[1]).get_name(), self.platforms.get(u[2] % 256)),
            9: lambda u: '%s оффлайн (%s)' % (self.__get_user(u[1]).get_name(), ("вышел" if u[1] == 0 else "ушёл")),
            # 10: lambda u: 'сброс флагов фильтрации по папкам для чата/собеседника с %s' % (u[1]),
            # 11: lambda u: 'замена флагов фильтрации по папкам для чата/собеседника с %s' % (u[1]),
            # 12: lambda u: 'установка флагов фильтрации по папкам для чата/собеседника с %s' % (u[1]),
            # 13: lambda u: 'замена флагов всех сообщений с заданным %s' % (u[1]),
            # 14: lambda u: 'установка флагов всех сообщений с заданным %s' % (u[1]),
            # 15: lambda u: 'сброс флагов всех сообщений с заданным %s' % (u[1]),
            # 51: lambda u: 'один из параметров (состав, тема) беседы %s были изменены' % (u[1]),
            61: lambda u: '%s печатает текст в диалоге' % (self.__get_user(u[1]).get_name()),
            62: lambda u: '%s печатает текст в беседе %s' % (
                self.__get_user(u[1]).get_name(), self.__get_chat(u[2]).get_name()),
            # 70: lambda u, vk: 'пользователь %s совершил звонок имеющий идентификатор %s' %
            #                   (get_user(vk, u[1]).get_name(), u[2]),
            # 80: lambda u, vk: 'новый счетчик непрочитанных в левом меню стал равен %s' % (u[1]),
            # 114: lambda u, vk: 'изменились настройки оповещений %s' % (u[1]),
        }
        self.get_long_poll = lambda: self.vk.method('messages.getLongPollServer', {'need_pts': 1})
        self.long_poll_url = lambda: 'http://%s?act=a_check&key=%s&ts=%s&wait=%s&mode=64' % (
            self.server, self.key, self.ts, self.time_wait)
        self.title = "vkNoty"
        self.debug = debug
        self.vk = vk_api.VkApi(login, password)

        try:
            self.vk.authorization()
        except vk_api.AuthorizationError as error_msg:
            print(error_msg)
            return
        poll = self.get_long_poll()

        self.__log(poll)
        self.notification(None, self.title, "Оповещения ВК готовы к работе")
        self.server, self.key, self.ts, self.pts = self.__get_config_poll(poll)
        self.time_wait = 25
        self.loop_cond = loop
        self.main_loop()

    def main_loop(self):
        while self.loop_cond:
            self.loop()

    def enable(self):
        self.loop_cond = True
        return self

    def disable(self):
        self.loop_cond = False
        return self

    def loop(self):
        response = requests.get(self.long_poll_url())
        if not self.__check_fail_long_poll(response):
            return
        data = json.loads(response.text)
        self.ts = data['ts']
        events = data.get('updates')
        self.__events(events)
        messages, self.pts = self.__get_long_poll_history()
        self.__message(messages)

    def __log(self, msg):
        if self.debug >= 1:
            print(msg)

    def __events(self, updates):
        for up in updates:
            upd = self.__check_updates(up)
            if upd is not None:
                self.notification(None, self.title, upd)
                self.__log(upd)

    def __message(self, messages):
        for message in messages:
            self.__log(message.get_message_formated())
            msg = message.get_message_for_notification()
            if msg is not None:
                self.notification(message.user.photo, msg[0], msg[1])

    def __check_fail_long_poll(self, response):
        if response.status_code != 200:
            return False
        else:
            data = json.loads(response.text)
            fail = data.get('failed')
            if fail is not None:
                if fail == 1:
                    self.ts = data['ts']
                elif fail == 2 | fail == 3:
                    poll = self.get_long_poll()
                    self.server, self.key, self.ts, self.pts = self.__get_config_poll(poll)
                return False
        return True

    @staticmethod
    def __get_config_poll(poll):
        return poll.get('server'), poll.get('key'), poll.get('ts'), poll.get('pts')

    def __get_long_poll_history(self, fields='photo,online,screen_name'):
        data = self.vk.method('messages.getLongPollHistory', {'ts': self.ts, 'pts': self.pts, 'fields': fields})
        messages_raw = data.get('messages')
        profiles = data.get('profiles')
        pts = data.get('new_pts')
        for user in profiles:
            self.__users[user.get('id')] = self.__create_user(user)

        messages = []
        for message in messages_raw.get('items'):
            messages.append(
                Message(
                    message.get('id'), message.get('date'),
                    message.get('out'), message.get('user_id'),
                    message.get('read_state'), message.get('title'),
                    message.get('body'), self.__get_user(message.get('user_id'))
                )
            )
        return [messages, pts]

    def __check_updates(self, update):
        code = self.codes.get(update[0])
        if code is not None:
            return code(update)

    def __get_name(self, _id):
        _id = abs(_id)
        if _id > 2000000000:
            _id -= 2000000000
            return self.__get_chat(_id).get_name()
        else:
            return self.__get_user(_id).get_name()

    def __get_user(self, _id):
        _id = abs(_id)
        user = self.__users.get(_id)
        if user is None:
            fields = 'photo,online,screen_name'
            _user = self.vk.method('users.get', {'user_ids': _id, 'fields': fields})
            user = self.__create_user(_user[0])
            self.__users[_id] = user
        return user

    def __get_chat(self, _id):
        chat = self.__chats.get(_id)
        if chat is None:
            _chat = self.vk.method('messages.getChat', {'chat_id': _id})
            chat = Chat(_chat.get('id'), _chat.get('type'),
                        _chat.get('title'), _chat.get('admin_id'),
                        _chat.get('users'))
            self.__chats[_id] = chat
        return chat

    @staticmethod
    def __create_user(user):
        return UserProfile(
            user.get('id'), user.get('first_name'),
            user.get('last_name'), user.get('screen_name'),
            user.get('photo'), user.get('online'))

    def notification(self, img_url, title, message):
        if img_url:
            icon = self.__get_photo(img_url)
            cmd = "notify-send -i %s '%s' '%s'" % (icon, title, message)
        else:
            cmd = "notify-send '%s' '%s'" % (title, message)
        os.system(cmd)

    @staticmethod
    def __get_photo(url):
        ind = url.rindex("/")
        _name = url[ind + 1:]
        _dir = os.path.abspath(os.path.dirname(__file__))
        if not os.path.isdir(_dir + "/cache"):
            os.system('mkdir ' + _dir + '/cache')
        if not os.path.exists(_dir + "/cache/" + _name):
            r = requests.get(url, stream=True)
            if r.status_code == 200:
                with open(_dir + '/cache/' + _name, 'wb') as f:
                    for chunk in r:
                        f.write(chunk)
        return _dir + '/cache/' + _name
