import os
import sys
import json
import pathlib
import requests
from lxml import html
from pathlib import Path
from dotenv import load_dotenv
from requests.exceptions import ConnectionError

load_dotenv()

ReturnUrl = None
RequestVerificationToken = None
NAME = os.getenv('NAME')
LOGIN = os.getenv('LOGIN')
PASSWD = os.getenv('PASSWORD')
FULL_NAME = None

code = None
scope = None
state = None
session_state = None
key_teacher = None
Path(pathlib.Path.cwd(), "teachers").mkdir(parents=True, exist_ok=True)
Path(pathlib.Path.cwd(), "events").mkdir(parents=True, exist_ok=True)
teachers_path = os.path.join(pathlib.Path.cwd(), 'teachers')
events_path = os.path.join(pathlib.Path.cwd(), 'events')

path = "//div[@class='events-left-block w-100 col-lg-6 mb-4xl']"

with open('version', encoding='utf8') as f:
    VERSION = f.read()

base_url = 'https://learn.innopolis.university'
url = 'https://learn.innopolis.university/Account/Login'
login_url = 'https://auth.lms.innopolis.university/Account/Login'
check_url = 'https://learn.innopolis.university/signin-oidc'
instructors_url = 'https://learn.innopolis.university/Instructors'
trainings_url = 'https://learn.innopolis.university/api/instructors/trainings'

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
}

params = {'back': ''}

s = requests.Session()

print(f'Версия парсера {VERSION}')
print('Парсер запущен ...')

response = s.get(url, params=params, headers=headers)

dom = html.fromstring(response.content)
user_form = dom.xpath("//div[@class='col-md-9']/form")

for item in user_form:
    ReturnUrl = item.xpath("input[@name='ReturnUrl']/@value")[0]
    RequestVerificationToken = item.xpath("input[@name='__RequestVerificationToken']/@value")[0]

params = {
    "ReturnUrl": ReturnUrl
}
data = {
    "Login": LOGIN,
    "Pass": PASSWD,
    "button": "login",
    "__RequestVerificationToken": RequestVerificationToken,
}

print('Parsing.. Страница авторизации')
response_2 = s.post(login_url, params=params, data=data, headers=headers)

dom_2 = html.fromstring(response_2.content)
sign_form = dom_2.xpath('//form')

for item in sign_form:
    code = item.xpath("input[@name='code']/@value")[0]
    scope = item.xpath("input[@name='scope']/@value")[0]
    state = item.xpath("input[@name='state']/@value")[0]
    session_state = item.xpath("input[@name='session_state']/@value")[0]

check_data = {
    'code': code,
    'scope': scope,
    'state': state,
    'session_state': session_state
}

check_response = s.post(check_url, data=check_data, headers=headers)

print('Parsing.. Страница модулей')

dom = html.fromstring(check_response.content).xpath(f"{path}/a/@href")[0]
online_url = base_url + dom
online = s.get(online_url)

dom = html.fromstring(online.content).xpath(path)
href = dom[0].xpath('a/@href')[0]

course_url = base_url + href
response = s.get(course_url)

print('Parsing.. Формируем карточки.')

dom = html.fromstring(response.content).xpath(path)
cards = []

for card in dom:
    card_url = card.xpath("a/@href")[0]
    card_name = card.xpath(
        "a/div[@class='card border-0 bg-white h-100 shadow rounded-lg p-0']"
        "/div[@class='card-body p-4 h-100 d-flex flex-column']"
        "/div[@class='card-title text-dark mb-4 row justify-content-between no-gutters flex-nowrap']/h5/text()")[0]
    cards.append({
        card_name: base_url + card_url
    })

print(f"\nУ вас {len(dom)} модуля.")
print('=' * 50)

for i in range(len(cards)):
    print(f'{i}. {[key for key in cards[i].keys()][0]}')

print('=' * 50)

sel = int(input('Какой модуль использовать? _ '))

try:
    get_card = list(cards[sel].values())[0]
    card_names = list(cards[sel].keys())[0]
except (IndexError,):
    print('Нет такого модуля.')
    sys.exit()

response = s.get(get_card)
get_card_url = base_url + html.fromstring(response.content).xpath("//a[@id='training-Progress']/@href")[0]
trainings = f'{trainings_url}/{get_card_url.split("/")[5]}'
get_trainings = f'{trainings}/groups'
teachers = s.get(get_trainings).json()

with open(os.path.join(f'{teachers_path}', f"{card_names}.json"), 'w+', encoding="utf8") as f:
    json.dump(teachers, f, ensure_ascii=False, indent=4)

keys = {}

for teacher in teachers:
    teach_id = list(teacher.values())

    if teach_id[1].startswith(NAME):
        keys[teach_id[1]] = teach_id[0]

key = 0

if len(keys) > 1:
    print(f"\nУ вас {len(keys)} группы в данном модуле.")
    print('=' * 50)

    for i, item in enumerate(keys.keys()):
        print(f'{i} - {item}')

    print('=' * 50)

    sel_group = int(input('Какую группу использовать? _ '))
    try:
        key = list(keys.values())[sel_group]
        FULL_NAME = list(keys.keys())[sel_group]
    except (IndexError,):
        print('Нет такой группы.')
        sys.exit()
elif len(keys) == 1:
    key = list(keys.values())[0]
    FULL_NAME = list(keys.keys())[0]
else:
    print('В данной группе нет учеников.')
    sys.exit()

data = {
    'start': 0,
    'length': 50,
    'search[value]': '',
    'search[regex]': 'false',
    'group': key,
    'work': '20, 30'
}
print('\nParsing.. Ожидаем ответ от сервера.')
try:
    response = s.post(f'{trainings}/ProgressLightweight', params=data)
    print('Parsing.. Ответ получен.')
except ConnectionError:
    print('Вышло время ожидания.... (')

with open(os.path.join(f'{events_path}', f"{FULL_NAME}.json"), 'w', encoding='utf8') as f:
    json.dump(response.json(), f, ensure_ascii=False, indent=4)
