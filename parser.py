import os
import sys
import json
import pathlib
import requests
import pandas as pd
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

Path(pathlib.Path.cwd(), "json", "teachers").mkdir(parents=True, exist_ok=True)
Path(pathlib.Path.cwd(), "json", "events").mkdir(parents=True, exist_ok=True)
Path(pathlib.Path.cwd(), "EXCEL").mkdir(parents=True, exist_ok=True)
teachers_path = os.path.join(pathlib.Path.cwd(), 'json', 'teachers')
events_path = os.path.join(pathlib.Path.cwd(), 'json', 'events')
xlsx_path = os.path.join(pathlib.Path.cwd(), 'EXCEL')

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

# GET запрос базового url для парсинга токена формы
response = s.get(url, params=params, headers=headers)

# Создание DOM объекта страницы с формой входа
dom = html.fromstring(response.content)
user_form = dom.xpath("//div[@class='col-md-9']/form")

# Парсим токен из формы
for item in user_form:
    ReturnUrl = item.xpath("input[@name='ReturnUrl']/@value")[0]
    RequestVerificationToken = item.xpath("input[@name='__RequestVerificationToken']/@value")[0]

# Формируем параметры url и данные для POST запроса авторизации
params = {
    "ReturnUrl": ReturnUrl
}
data = {
    "Login": LOGIN,
    "Pass": PASSWD,
    "button": "login",
    "__RequestVerificationToken": RequestVerificationToken,
}

# Авторизуемся
print('Parsing.. Страница авторизации')
response = s.post(login_url, params=params, data=data, headers=headers)

# Создаем объект скрытой формы, сформированной в ответе на форму авторизации, для проверки данных.
# Парсим данные из скрытой формы для проверки и передачи необходимых параметров
dom_2 = html.fromstring(response.content)
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

# Проходим проверку
check_response = s.post(check_url, data=check_data, headers=headers)

print('Parsing.. Страница модулей')

# Парсим страницу "Курсы" для поиска url перехода на следующую страницу
dom = html.fromstring(check_response.content).xpath(f"{path}/a/@href")[0]

# Формируем url для перехода на следующую страницу
online_url = base_url + dom

# GET запрос следующей страницы
online = s.get(online_url)

# Парсим страницу "Код будущего" для поиска url перехода на следующую страницу
dom = html.fromstring(online.content).xpath(path)
href = dom[0].xpath('a/@href')[0]

# Формируем url для перехода на следующую страницу
course_url = base_url + href

# GET запрос следующей страницы
response = s.get(course_url)

print('Parsing.. Формируем карточки.')

# Парсим страницу "Онлайн" для формирования списка доступных модулей
dom = html.fromstring(response.content).xpath(path)
cards = []

# Находим все доступные модули и формируем словарь с наименованием курса и ссылкой для перехода
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

# Формируем наименование выбранного модуля и ссылку для перехода
try:
    get_card = list(cards[sel].values())[0]
    card_names = list(cards[sel].keys())[0]
except (IndexError,):
    print('Нет такого модуля.')
    sys.exit()

# Переходим на страницу выбранного модуля
response = s.get(get_card)

# Парсим страницу модуля для формирования ссылки на журнал
get_card_url = base_url + html.fromstring(response.content).xpath("//a[@id='training-Progress']/@href")[0]
trainings = f'{trainings_url}/{get_card_url.split("/")[5]}'
get_trainings = f'{trainings}/groups'

# Переходим в журнал и получаем json объект всех преподавателей модуля
teachers = s.get(get_trainings).json()

# Создание файла json со списком преподавателей текущей группы
with open(os.path.join(f'{teachers_path}', f"{card_names}.json"), 'w+', encoding="utf8") as f:
    json.dump(teachers, f, ensure_ascii=False, indent=4)

keys = {}

# Ищем в списке преподавателей свою фамилию и формируем словарь с id и фамилией
for teacher in teachers:
    teach_id = list(teacher.values())

    if teach_id[1].startswith(NAME):
        keys[teach_id[1]] = teach_id[0]

key = 0

# Если на данном направлении несколько групп, разрешаем выбор необходимой группы
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

# Если группа только одна
elif len(keys) == 1:
    key = list(keys.values())[0]
    FULL_NAME = list(keys.keys())[0]

# Если группа еще не сформирована, либо отсутствует
else:
    print('В данной группе нет учеников.')
    sys.exit()

# Создаем словарь параметров для фильтрации по фамилии, в качестве ключа передаем id преподавателя.
# Кол-во записей на странице - 50
data = {
    'start': 0,
    'length': 50,
    'search[value]': '',
    'search[regex]': 'false',
    'group': key,
    'work': '20, 30'
}

print('\nParsing.. Ожидаем ответ от сервера.')

# Фильтруем страницу
try:
    response = s.post(f'{trainings}/ProgressLightweight', params=data)
    print('Parsing.. Ответ получен.')
except ConnectionError:
    print('Вышло время ожидания.... (')

# Создание файла журнала текущей группы в формате json
with open(os.path.join(f'{events_path}', f"{FULL_NAME}.json"), 'w', encoding='utf8') as f:
    json.dump(response.json(), f, ensure_ascii=False, indent=4)

# ========================================================
#      Парсим json и формируем журнал в формате xlsx
# ========================================================
data = response.json().get('data')

columns = []
for i in range(1, len(data[0].get('exercises')) + 1):
    columns.append(i)

students = []
values = []

for student_dict in data:
    val = []

    surname = student_dict.get('surname')
    firstname = student_dict.get('firstname')
    patronymic = student_dict.get('patronymic')
    student_name = f'{surname} {firstname} {patronymic}'
    students.append(student_name)

    exercises = student_dict.get('exercises')  # Получаем список с домашними заданиями ученика
    for i in exercises:
        if i.get('light') == 'text-gray':
            val.append('-')
        if i.get('light') == 'text-green':
            val.append(str(round(float(i.get('average')), 2)))
        if i.get('light') == 'text-red':
            val.append('Сдано')
    values.append(val)

df = pd.DataFrame(values, index=students, columns=columns)
df.to_excel(os.path.join(f'{xlsx_path}', f'{card_names}.xlsx'),
            sheet_name='events')  # Название файла по наименованию направления
# df.to_excel(os.path.join(f'{xlsx_path}', f'{FULL_NAME}.xlsx'),
            # sheet_name='events') # Название файла по преподавателю
print('Parsing.. Done.')
