import os
import sys
import json
import pathlib
import pandas as pd
from lxml import html
from pathlib import Path
from authorization import auth
from dotenv import load_dotenv
from requests.exceptions import ConnectionError
import io
import zipfile

load_dotenv()

NAME = os.getenv('NAME')
LOGIN = os.getenv('LOGIN')
PASSWD = os.getenv('PASSWORD')
IS_LOAD = True if os.getenv('IS_LOAD') == 'True' else False
FULL_NAME = None

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
instructors_url = 'https://learn.innopolis.university/Instructors'
trainings_url = 'https://learn.innopolis.university/api/instructors/trainings'
files_url = 'https://learn.innopolis.university/Instructors/Trainings/{}/Results/Files?work=00000000-0000-0000-0000-000000000000&exercise={}&student={}'

print(f'Версия парсера {VERSION}')
print('Парсер запущен ...')

s, response = auth(LOGIN, PASSWD)

if not response.ok:
    print('Безуспешная попытка авторизации.')
    sys.exit()

print('Parsing.. Авторизация - ОК.')
print('Parsing.. Страница модулей')

# Парсим страницу "Курсы" для поиска url перехода на следующую страницу
dom = html.fromstring(response.content).xpath(f"{path}/a/@href")[0]

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
    print(f'{i}. {list(cards[i].keys())[0]}')

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
card_id = get_card_url.split("/")[5]  # ID модуля
trainings = f'{trainings_url}/{card_id}'
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
    'group': key,
    'work': '20,30'
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
    student_id = student_dict.get('id')
    surname = student_dict.get('surname')
    firstname = student_dict.get('firstname')
    patronymic = student_dict.get('patronymic')
    student_name = f'{surname} {firstname} {patronymic}'
    students.append(student_name)

    exercises = student_dict.get('exercises')  # Получаем список с домашними заданиями ученика
    for pos, i in enumerate(exercises, 1):
        light = i.get('light')
        if light == 'text-gray':
            val.append('')
        if light == 'text-green':
            val.append(f'{i.get("average"):.2f}')
        if light == 'text-red':
            if IS_LOAD:
                file = s.get(files_url.format(card_id, i.get('id'), student_id))
                with file, zipfile.ZipFile(io.BytesIO(file.content)) as archive:
                    archive.extractall('homework_files')
                print(f'{student_name}: ДЗ №{pos} загружено.')
            val.append('Сдано')
    values.append(val)

df = pd.DataFrame(values, index=students, columns=columns)
df.to_excel(os.path.join(f'{xlsx_path}', f'{card_names}.xlsx'),
            sheet_name='events')  # Название файла по наименованию направления
# df.to_excel(os.path.join(f'{xlsx_path}', f'{FULL_NAME}.xlsx'), sheet_name='events') # Название файла по преподавателю
print('Parsing.. Done.')
