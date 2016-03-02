from vk_api import *
import json
from message import Message
from userprofile import UserProfile
from chat import Chat
import os
import requests
import logging


class Main:
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

    def __init__(self, login, password, debug_stream=logging.ERROR, debug_file=logging.DEBUG, loop=False):
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
        logging.basicConfig(filename='vk.log', level=logging.DEBUG)
        # получить сервер событий
        self.get_long_poll = lambda: self.vk.method('messages.getLongPollServer', {'need_pts': 1})
        # урл сервера событий
        self.long_poll_url = lambda: 'http://%s?act=a_check&key=%s&ts=%s&wait=%s&mode=64' % (
            self.server, self.key, self.ts, self.time_wait)
        self.title = "vkNoty"  # заголовок для обычных событий
        self.debug = debug_stream  # уровень дебага
        self.log = debug_file  # уровень записи в файл
        self.logger = logging.getLogger('vk')
        self.init_logger()
        self.vk = vk_api.VkApi(login, password)  # создаём объект для работы с API

        try:
            self.vk.authorization()  # пытаемся авторизоваться
        except vk_api.AuthorizationError as error_msg:
            print(error_msg)
            return
        poll = self.get_long_poll()  # получаем настройки сервер событий

        self.__log(poll)  # выводим в лог данные сервера событий
        self.notification(None, self.title, "Оповещения ВК готовы к работе")  # говорим, что готовы
        self.server, self.key, self.ts, self.pts = self.__get_config_poll(poll)  # задаём настройки сервера событий
        self.time_wait = 25  # время ожидания событий
        self.loop_cond = loop  # запускаться ли сразу
        self.main_loop()  # запускаем главную петлю

    def main_loop(self):  # главная пется
        while self.loop_cond:  # если можно
            self.loop()  # то запускаем петлю

    def enable(self):  # включаем петлю
        self.loop_cond = True
        return self

    def disable(self):  # выключаем петлю
        self.loop_cond = False
        return self

    def loop(self):  # петля. Все действия тут
        try:
            response = requests.get(self.long_poll_url())  # получаем события с сервера событий
        except Exception as e:  # при запросепроизошла непредвиденная ошибка
            print(e)  # выводим её
            return  # и пропускае
        self.__degug(response.text)
        if not self.__check_fail_long_poll(response):  # проверяем на ошибки
            return  # если они есть, то пропускаем
        data = json.loads(response.text)  # получаем данные с сервера событий в словарь
        self.ts = data['ts']  # получаем новый временной штамп
        events = data.get('updates')  # получаем события
        self.__events(events)  # проверяем события
        messages, self.pts = self.__get_long_poll_history()  # получаем лс
        self.__message(messages)  # выводим лс

    def __log(self, msg):  # логи, если они включены
        self.logger.log(logging.CRITICAL, msg)

    def __error(self, msg):  # серьёзные ошибки, если они включены
        self.logger.error(msg)

    def __warning(self, msg):  # разные предупреждения, если они включены
        self.logger.warning(msg)

    def __info(self, msg):  # информация, если они включены
        self.logger.info(msg)

    def __degug(self, msg):  # отладка, если они включены
        self.logger.debug(msg)

    def __events(self, updates):  # обработка событий
        for up in updates:  # по всем событиям
            upd = self.__check_event(up)  # проверяем событие, не все события надо выводить
            if upd is not None:  # если событие обрабатываемое
                self.notification(None, self.title, upd)  # оповещаем
                self.__log(upd)  # в лог

    def __message(self, messages):  # обработка сообщений
        for message in messages:  # сообщений может быть больше 1
            self.__log(message.get_message_formated())  # в лог
            msg = message.get_message_for_notification()  # подготавливаем сообщене
            if msg is not None:  # если подготовилось
                self.notification(message.user.photo, msg[0], msg[1])  # выводим

    def __check_fail_long_poll(self, response):  # не провалился ли сервер событий
        if response.status_code != 200:  # получили не 200:ОК
            self.__error('Ошибка запроса, получен ответ %s' % response.status_code)
            return False
        else:
            data = json.loads(response.text)
            self.__info(data)
            fail = data.get('failed')  # получили провал
            if fail is not None:  # если есть фейл
                poll = self.get_long_poll()  # тупо перезапустим сервер событий
                self.__log(poll)  # выводим в лог данные сервера событий
                self.notification(None, self.title, "Получен новый сервер событий")  # говорим, что готовы
                self.server, self.key, self.ts, self.pts = self.__get_config_poll(poll)
                self.__warning('Запрос сфейлился: %s' % fail)
                return False
        return True

    @staticmethod
    def __get_config_poll(poll):  # получаем настройки сервера событий из запроса настроек сервера событий
        return poll.get('server'), poll.get('key'), poll.get('ts'), poll.get('pts')

    def __get_long_poll_history(self, fields='photo,online,screen_name'):  # получаем историю ЛС
        data = self.vk.method('messages.getLongPollHistory', {'ts': self.ts, 'pts': self.pts, 'fields': fields})
        self.__degug(data)
        messages_raw = data.get('messages')  # получаем сообещния
        profiles = data.get('profiles')  # получаем профили
        pts = data.get('new_pts')  # получаем новую метку
        for user in profiles:  # пройдёмся по всем профилям
            self.__users[user.get('id')] = self.__create_user(user)  # обновим информацию

        messages = []
        for message in messages_raw.get('items'):  # пройдёмся по всем сообещниям
            messages.append(  # запишем сообщения в очередб
                Message(
                    message.get('id'), message.get('date'),
                    message.get('out'), message.get('user_id'),
                    message.get('read_state'), message.get('title'),
                    message.get('body'), self.__get_user(message.get('user_id'))
                )
            )
        return [messages, pts]

    def __check_event(self, event):  # нужно ли выводить событие
        code = self.codes.get(event[0])  # пробуем получить обработчик события
        if code is not None:  # если получили
            return code(event)  # возвращаем обработанный результат

    def __get_name(self, _id):  # получаем имя по ID
        _id = abs(_id)  # id должен быть положительным
        if _id > 2000000000:  # если это беседа
            _id -= 2000000000
            return self.__get_chat(_id).get_name()  # получаем имя беседы
        else:  # иначе
            return self.__get_user(_id).get_name()  # получаемимя пользователя

    def __get_user(self, _id):  # получаем пользователя
        _id = abs(_id)
        user = self.__users.get(_id)  # пробуем взять пользователя из кеша
        if user is None:  # если не удачно
            fields = 'photo,online,screen_name'
            _user = self.vk.method('users.get', {'user_ids': _id, 'fields': fields})  # запрашиваем пользователя
            user = self.__create_user(_user[0])  # и добавляем в кеш
            self.__users[_id] = user
        return user

    def __get_chat(self, _id):  # получаем беседу
        chat = self.__chats.get(_id)  # пробуем получить беседу
        if chat is None:  # если не удачно
            _chat = self.vk.method('messages.getChat', {'chat_id': _id})  # запрашиваем беседу
            chat = Chat(_chat.get('id'), _chat.get('type'),
                        _chat.get('title'), _chat.get('admin_id'),
                        _chat.get('users'))
            self.__chats[_id] = chat  # добавляем в кеш
        return chat

    @staticmethod
    def __create_user(user):  # создаёмпользователя по ответу
        return UserProfile(
            user.get('id'), user.get('first_name'),
            user.get('last_name'), user.get('screen_name'),
            user.get('photo'), user.get('online'))

    def notification(self, img_url, title, message):  # кидаем оповещение
        if img_url:  # если нужно иконку
            icon = self.__get_photo(img_url)  # получаем иконку
            cmd = "notify-send -i %s '%s' '%s'" % (icon, title, message)
        else:
            cmd = "notify-send '%s' '%s'" % (title, message)
        self.__degug(cmd)
        os.system(cmd)  # шлём оповещение

    @staticmethod
    def __get_photo(url):  # получаем иконку по ссылке
        ind = url.rindex("/")  # получаем позицию последнего /
        _name = url[ind + 1:]  # обрезаем строку от последнего /
        _dir = os.path.abspath(os.path.dirname(__file__))  # получаем абсолютный путь до себя
        if not os.path.isdir(_dir + "/cache"):  # при еобходимости создадим папку с иконками
            os.makedirs(_dir + '/cache')
        if not os.path.exists(_dir + "/cache/" + _name):  # если иконки нет
            r = requests.get(url, stream=True)  # делаем магию
            if r.status_code == 200:
                with open(_dir + '/cache/' + _name, 'wb') as f:
                    for chunk in r:
                        f.write(chunk)
        return _dir + '/cache/' + _name  # возвращаем абсолютный путь до иконки

    def init_logger(self):

        self.logger.setLevel(self.log)
        fh = logging.FileHandler('vk.log')
        fh.setLevel(self.log)
        ch = logging.StreamHandler()
        ch.setLevel(self.debug)
        formatter = logging.Formatter('%(asctime)s: [%(levelname)s] %(message)s', '%d.%m.%Y %H:%M:%S')
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        self.logger.addHandler(ch)
        self.logger.addHandler(fh)
