"""
API для публичной регистрации и публичных справочников.

POST    /api/register_public  -- самостоятельная регистрация (role='user')
GET     /api/dirs_public      -- справочники для формы регистрации (без авторизации)
"""
# Стандартный логгер Python
import logging
# os — для чтения переменных окружения (DEFAULT_ROLE)
import os

# get_user_model — получаем модель пользователя (кастомную или стандартную)
from django.contrib.auth import get_user_model
# ValidationError — исключение при нарушении бизнес-правил (model.clean)
from django.core.exceptions import ValidationError
# settings — доступ к DEBUG и другим настройкам проекта
from django.conf import settings
# IntegrityError — исключение при нарушении ограничений БД (уникальный login)
from django.db import IntegrityError, transaction
# JsonResponse — HTTP-ответ с JSON-телом
from django.http import JsonResponse
# method_decorator — применение декоратора к методу класса
from django.utils.decorators import method_decorator
# View — базовый класс для CBV
from django.views import View
# csrf_exempt — отключение CSRF-проверки (публичные эндпоинты)
from django.views.decorators.csrf import csrf_exempt

# Парсер JSON-тела запроса
from apps.api.mixins import parse_json_body
# Модели сотрудников: отдел, сотрудник, НТЦ-центр, сектор
from apps.employees.models import (
    Department,
    Employee,
    NTCCenter,
    Sector,
)

# Активная модель пользователя Django (обычно auth.User)
User = get_user_model()
# Логгер для данного модуля
logger = logging.getLogger(__name__)

# Правила полей подразделения по display-имени должности:
#   'ntc'  — только НТЦ
#   'dept' — только Отдел
#   'both' — Отдел + Сектор
#   ''     — ничего не требуется
# Используется для валидации обязательных полей на форме регистрации
_POSITION_FIELD_RULES = {
    # НТЦ
    'Руководитель НТЦ':                          'ntc',   # требует только НТЦ
    'Зам. руководителя НТЦ':                     'ntc',
    # Только отдел
    'Начальник отдела':                           'dept',  # требует только отдел
    'Зам. начальника отдела':                     'dept',
    # Отдел + сектор
    'Техник-конструктор':                         'both',  # требует отдел + сектор
    'Техник-конструктор 2 кат.':                 'both',
    'Техник-конструктор 1 кат.':                 'both',
    'Специалист':                                 'both',
    'Специалист 2 кат.':                         'both',
    'Специалист 1 кат.':                         'both',
    'Ведущий специалист':                         'both',
    'Инженер-конструктор':                        'both',
    'Инженер-конструктор 3 кат.':                'both',
    'Инженер-конструктор 2 кат.':                'both',
    'Инженер-конструктор 1 кат.':                'both',
    'Ведущий инженер-конструктор':               'both',
    'Ведущий инженер по направлению 3 класса':   'both',
    'Ведущий инженер по направлению 2 класса':   'both',
    'Ведущий инженер - координатор группы':      'both',
    'Начальник бюро':                             'both',
    'Младший научный сотрудник':                  'both',
    'Старший научный сотрудник':                  'both',
    'Ведущий научный сотрудник':                  'both',
    'Начальник сектора':                          'both',
    'Зам. начальника отдела – начальник сектора': 'both',
    'Руководитель направления':                   'both',
}

# Маппинг ключа должности → роль (только для продакшена, DEBUG=False).
# На деплое регистрация сразу назначает соответствующую роль,
# локально — всегда role='user', роли назначает администратор.
_POSITION_TO_ROLE = {
    'ntc_head':           Employee.ROLE_NTC_HEAD,
    'ntc_deputy':         Employee.ROLE_NTC_DEPUTY,
    'dept_head':          Employee.ROLE_DEPT_HEAD,
    'dept_deputy':        Employee.ROLE_DEPT_DEPUTY,
    'dept_deputy_sector': Employee.ROLE_SECTOR_HEAD,
    'sector_head':        Employee.ROLE_SECTOR_HEAD,
}


# ── GET /api/dirs_public ─────────────────────────────────────────────────────

# Отключаем CSRF (публичный эндпоинт — авторизация не нужна)
@method_decorator(csrf_exempt, name='dispatch')
class DirsPublicView(View):
    """
    GET -- публичные справочники для формы регистрации.
    Не требует авторизации.
    Возвращает: {dept: [...], sectors_by_dept: {...}, position: [...], center: [...]}
    """

    def get(self, request):
        # НТЦ-центры: список кодов всех центров
        center_values = list(
            NTCCenter.objects.order_by('code').values_list('code', flat=True)
        )

        # Отделы, сгруппированные по НТЦ (для каскадного выпадающего списка)
        depts_by_center = {}  # {center_code: [dept_code, ...]}
        dept_values = []       # плоский список всех кодов отделов
        for d in Department.objects.select_related('ntc_center').order_by('code'):
            dept_values.append(d.code)
            if d.ntc_center:
                # Группируем отдел по коду его НТЦ
                depts_by_center.setdefault(d.ntc_center.code, []).append(d.code)
            else:
                # Отдел без НТЦ — помещаем в группу с пустым ключом
                depts_by_center.setdefault('', []).append(d.code)

        # Секторы, сгруппированные по отделу (для каскадного выпадающего списка)
        sectors_by_dept = {}  # {dept_code: [sector_code, ...]}
        for s in Sector.objects.select_related('department').order_by('code'):
            if s.department:
                # Группируем сектор по коду его отдела
                sectors_by_dept.setdefault(s.department.code, []).append(s.code)

        # Должности из POSITION_CHOICES модели Employee (список строк-label)
        position_values = [label for _, label in Employee.POSITION_CHOICES]

        # Возвращаем все справочники одним объектом
        return JsonResponse({
            'dept': dept_values,              # все коды отделов (плоский список)
            'depts_by_center': depts_by_center,  # отделы по НТЦ
            'sectors_by_dept': sectors_by_dept,  # секторы по отделу
            'position': position_values,      # список должностей
            'center': center_values,          # коды НТЦ-центров
        })


# ── POST /api/register_public ────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class RegisterPublicView(View):
    """
    POST -- публичная регистрация нового пользователя.
    Создаёт User + Employee с role='user'.
    """

    def post(self, request):
        # Парсим JSON-тело запроса
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        # Извлекаем и очищаем поля из запроса
        username = data.get('username', '').strip()     # логин
        password = data.get('password', '')             # пароль (без strip — могут быть пробелы)
        last_name = data.get('last_name', '').strip()   # фамилия
        first_name = data.get('first_name', '').strip() # имя
        patronymic = data.get('patronymic', '').strip() # отчество
        position = data.get('position', '').strip()     # должность
        center = data.get('center', '').strip()         # код НТЦ-центра
        dept = data.get('dept', '').strip()             # код отдела
        sector = data.get('sector', '').strip()         # код сектора
        email = data.get('email', '').strip()            # корп. email (необязательно)

        # Валидация обязательных персональных данных
        if not last_name:
            return JsonResponse({'error': 'Введите фамилию'}, status=400)
        if not first_name:
            return JsonResponse({'error': 'Введите имя'}, status=400)
        if not patronymic:
            return JsonResponse({'error': 'Введите отчество'}, status=400)
        if not position:
            return JsonResponse({'error': 'Выберите должность'}, status=400)

        # Определяем display-имя должности (если пришёл ключ — конвертируем в label)
        position_display = position
        for key, label in Employee.POSITION_CHOICES:
            if key == position:
                # Нашли соответствие ключа — берём label
                position_display = label
                break

        # Определяем, какие поля подразделения обязательны для данной должности
        field_rule = _POSITION_FIELD_RULES.get(position_display, '')
        if field_rule == 'ntc' and not center:
            # Для руководителей НТЦ обязателен НТЦ
            return JsonResponse({'error': 'Укажите НТЦ'}, status=400)
        if field_rule in ('dept', 'both') and not dept:
            # Для нач. отдела и исполнителей обязателен отдел
            return JsonResponse({'error': 'Укажите отдел'}, status=400)
        if field_rule == 'both' and not sector:
            # Для исполнителей обязателен сектор
            return JsonResponse({'error': 'Укажите сектор'}, status=400)

        if not username:
            return JsonResponse({'error': 'Логин обязателен'}, status=400)
        # Валидация пароля через Django password validators
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_password(password)
        except DjValidationError as e:
            return JsonResponse(
                {'error': '; '.join(e.messages)}, status=400,
            )

        # Находим / создаём только нужные подразделения
        dept_obj = None    # объект Department
        sector_obj = None  # объект Sector
        center_obj = None  # объект NTCCenter

        if dept:
            # get_or_create: находим отдел или создаём с пустым именем
            dept_obj, _ = Department.objects.get_or_create(
                code=dept, defaults={'name': ''}
            )
        if sector and dept_obj:
            # Сектор создаём только если известен отдел (иерархия)
            sector_obj, _ = Sector.objects.get_or_create(
                department=dept_obj, code=sector, defaults={'name': ''}
            )
        if center:
            # Аналогично — НТЦ-центр
            center_obj, _ = NTCCenter.objects.get_or_create(
                code=center, defaults={'name': ''}
            )

        # Определяем код должности (position в Employee — это ключ choices)
        # Ищем подходящий ключ по отображаемому имени
        position_key = _resolve_position_key(position)

        try:
            # Атомарная транзакция: User и Employee создаются вместе,
            # чтобы не оставить «осиротевшего» User без профиля
            with transaction.atomic():
                # Создаём пользователя Django с хешированным паролем
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                )
                # Создаём связанный профиль Employee
                # На продакшене роль определяется по должности,
                # локально — всегда 'user' (роли назначает админ)
                if not settings.DEBUG:
                    role = _POSITION_TO_ROLE.get(position_key, Employee.ROLE_USER)
                else:
                    role = Employee.ROLE_USER
                Employee.objects.create(
                    user=user,
                    role=role,
                    last_name=last_name,
                    first_name=first_name,
                    patronymic=patronymic,
                    position=position_key,
                    ntc_center=center_obj,
                    department=dept_obj,
                    sector=sector_obj,
                    email_corp=email,
                )
        except ValidationError as e:
            return JsonResponse(
                {'error': e.message if hasattr(e, 'message') else str(e)},
                status=400,
            )
        except IntegrityError:
            # Нарушение ограничения уникальности: логин уже занят
            return JsonResponse(
                {'error': 'Пользователь с таким логином уже существует'},
                status=400,
            )

        # Логируем успешную регистрацию
        logger.info(
            "register_public: создан пользователь '%s' (role=%s, %s, %s)",
            username, role, dept, sector,
        )
        # Возвращаем успех с ID нового пользователя
        return JsonResponse({'ok': True, 'id': user.pk}, status=201)


from apps.api.utils import resolve_position_key as _resolve_position_key
