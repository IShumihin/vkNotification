from vk_api import *
import json
from message import Message
from userprofile import UserProfile
from chat import Chat
import os
import requests

# указать свои данные для авторизации
login, password = '', ''
users = {}  # множество профилей пользователей
chats = {}  # множество бесед
platforms = {  # платформы
    1: 'mobile',
    2: 'iphone',
    3: 'ipad',
    4: 'android',
    5: 'wphone',
    6: 'windows',
    7: 'web'
}

codes = {  # ответы
    # 0: lambda u, vk: 'Сообение %s удалено' % u[1],
    # 1: lambda u, vk: 'Замена флагов сообщения %s на %s' % (u[1], u[2]),
    # 2: lambda u, vk: 'Установка флагов сообщени %s на %s' % (u[1], u[2]),
    # 3: lambda u, vk: 'сброс флагов сообщения %s на %s' % (u[1], u[2]),
    # 4: lambda u, vk: 'Добавление нового сообщения %s' % (u[1]),
    # 6: lambda u, vk: 'Вы прочитали все входящие сообщения от %s  по %s' % (get_user(vk, u[1]).get_name(), u[2]),
    7: lambda u, vk: '%s прочитал все исходящие сообщения по %s' % (get_user(vk, u[1]).get_name(), u[2]),
    # 8: lambda u, vk: '%s онлайн (%s)' % (get_user(vk, u[1]).get_name(), platforms[u[2] % 256]),
    # 9: lambda u, vk: '%s оффлайн (%s)' % (get_user(vk, u[1]).get_name(), ("вышел" if u[1] == 0 else "ушёл")),
    # 10: lambda u, vk: 'сброс флагов фильтрации по папкам для чата/собеседника с %s' % (u[1]),
    # 11: lambda u, vk: 'замена флагов фильтрации по папкам для чата/собеседника с %s' % (u[1]),
    # 12: lambda u, vk: 'установка флагов фильтрации по папкам для чата/собеседника с %s' % (u[1]),
    # 13: lambda u, vk: 'замена флагов всех сообщений с заданным %s' % (u[1]),
    # 14: lambda u, vk: 'установка флагов всех сообщений с заданным %s' % (u[1]),
    # 15: lambda u, vk: 'сброс флагов всех сообщений с заданным %s' % (u[1]),
    # 51: lambda u, vk: 'один из параметров (состав, тема) беседы %s были изменены' % (u[1]),
    61: lambda u, vk: '%s печатает текст в диалоге' % (get_user(vk, u[1]).get_name()),
    62: lambda u, vk: '%s печатает текст в беседе %s' % (get_user(vk, u[1]).get_name(), get_chat(vk,u[2]).get_name()),
    # 70: lambda u, vk: 'пользователь %s совершил звонок имеющий идентификатор %s' % (get_user(vk, u[1]).get_name(), u[2]),
    # 80: lambda u, vk: 'новый счетчик непрочитанных в левом меню стал равен %s' % (u[1]),
    # 114: lambda u, vk: 'изменились настройки оповещений %s' % (u[1]),

}


def main():
    vk_session = vk_api.VkApi(login, password)
    try:
        vk_session.authorization()
    except vk_api.AuthorizationError as error_msg:
        print(error_msg)
        return
    # vk = vk_session.get_api()
    # response = vk.wall.get(count=1)
    # response = vk_session.method("messages.get",{'count':'10'})
    # response = vk.messages.get(count=10)
    pool = get_long_poll(vk_session)
    print(pool)
    notification2(None, "Событие", "Оповещения ВК готовы к работе")
    time_wait = 25
    server, key, ts, pts, = pool.get('server'), pool.get('key'), pool.get('ts'), pool.get('pts')
    while True:

        response = requests.get('http://%s?act=a_check&key=%s&ts=%s&wait=%s&mode=64' %
                                (server, key, ts, time_wait))
        data = json.loads(response.text)
        ts = data['ts']
        fail = data.get('failed')
        if fail is not None:
            if fail == 1:
                ts = data['ts']
            elif fail == 2 | fail == 3:
                pool = get_long_poll(vk_session)
                server, key, ts, pts = pool.get('server'), pool.get('key'), pool.get('ts'), pool.get('pts')
            continue
        updates = data.get('updates')
        for up in updates:
            checked_update = check_updates(vk_session, up)
            if checked_update is not None:
                notification2(None, 'событие', checked_update)
                print(checked_update)
        messages, pts = get_long_poll_history(vk_session, ts, pts)
        for message in messages:
            print(message.get_message_formated())
            msg = message.get_message_for_notification()
            if msg is not None:
                notification2(message.user.photo, msg[0], msg[1])


"""
Получаем соеденение с ожиданием ответа
"""


def get_long_poll(vk_session):
    return vk_session.method('messages.getLongPollServer', {'need_pts': 1})


"""
Получаем историю сообщений
"""


def get_long_poll_history(vk_session, ts, pts, fields='photo,online,screen_name'):
    data = vk_session.method('messages.getLongPollHistory', {'ts': ts, 'pts': pts, 'fields': fields})
    messages_raw = data.get('messages')
    profiles = data.get('profiles')
    pts = data.get('new_pts')
    for user in profiles:
        users[user.get('id')] = create_user(user)

    messages = []
    for message in messages_raw.get('items'):
        messages.append(
            Message(
                message.get('id'), message.get('date'),
                message.get('out'), message.get('user_id'),
                message.get('read_state'), message.get('title'),
                message.get('body'), get_user(vk_session, message.get('user_id'))
            )
        )
    return [messages, pts]


"""
Проверка обновлений
"""


def check_updates(vk_session, update):
    code = codes.get(update[0])
    if code is not None:
        return code(update, vk_session)


"""
Получаем пользователя из списка или через запрос

"""


def get_user(vk_session, _id):
    _id = abs(_id)
    if _id > 2000000000:
        _id -= 2000000000
        return get_chat(vk_session, _id)
    else:
        user = users.get(_id)
        if user is None:
            fields = 'photo,online,screen_name'
            _user = vk_session.method('users.get', {'user_ids': _id, 'fields': fields})
            user = create_user(_user[0])
            users[_id] = user
        return user


def get_chat(vk_session, _id):
    chat = chats.get(_id)
    if chat is None:
        _chat = vk_session.method('messages.getChat', {'chat_id': _id})
        chat = Chat(_chat.get('id'), _chat.get('type'),
                    _chat.get('title'), _chat.get('admin_id'),
                    _chat.get('users'))
        chats[_id] = chat
    return chat


def create_user(_user):
    user = UserProfile(
        _user.get('id'), _user.get('first_name'),
        _user.get('last_name'), _user.get('screen_name'),
        _user.get('photo'), _user.get('online'))
    return user


def notification(icon, title, text):
    if icon:
        cmd = "notify-send -i %s '%s' '%s'" % (icon, title, text)
    else:
        cmd = "notify-send '%s' '%s'" % (title, text)
    os.system(cmd)


def notification2(img_url, title, message):
    if img_url:
        icon = get_photo(img_url)
        cmd = "notify-send -i %s '%s' '%s'" % (icon, title, message)
    else:
        cmd = "notify-send '%s' '%s'" % (title, message)
    os.system(cmd)


def get_photo(url):
    ind = url.rindex("/")
    name = url[ind+1:]
    _dir = os.path.abspath(os.path.dirname(__file__))
    if not os.path.isdir(_dir + "/cache"):
        os.system('mkdir ' + _dir + '/cache')
    if not os.path.exists(_dir + "/cache/" + name):
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            with open(_dir + '/cache/' + name, 'wb') as f:
                for chunk in r:
                    f.write(chunk)
    return _dir + '/cache/' + name


if __name__ == '__main__':
    main()
