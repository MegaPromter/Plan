"""
API для публичной регистрации и публичных справочников.

POST    /api/register_public  -- самостоятельная регистрация (role='user')
GET     /api/dirs_public      -- справочники для формы регистрации (без авторизации)
"""
import logging
import os

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.api.mixins import parse_json_body
from apps.employees.models import (
    Department,
    Employee,
    NTCCenter,
    Sector,
)

User = get_user_model()
logger = logging.getLogger(__name__)

# Правила полей подразделения по display-имени должности:
#   'ntc'  — только НТЦ
#   'dept' — только Отдел
#   'both' — Отдел + Сектор
#   ''     — ничего не требуется
_POSITION_FIELD_RULES = {
    # НТЦ
    'Руководитель НТЦ':                          'ntc',
    'Зам. руководителя НТЦ':                     'ntc',
    # Только отдел
    'Начальник отдела':                           'dept',
    'Зам. начальника отдела':                     'dept',
    # Отдел + сектор
    'Техник-конструктор':                         'both',
    'Техник-конструктор 2 кат.':                 'both',
    'Техник-конструктор 1 кат.':                 'both',
    'Специалист':                                 'both',
    'Специалист 2 кат.':                         'both',
    'Специалист 1 кат.':                         'both',
    'Инженер-конструктор':                        'both',
    'Инженер-конструктор 3 кат.':                'both',
    'Инженер-конструктор 2 кат.':                'both',
    'Инженер-конструктор 1 кат.':                'both',
    'Ведущий инженер-конструктор':               'both',
    'Начальник сектора':                          'both',
    'Зам. начальника отдела – начальник сектора': 'both',
    'Руководитель направления':                   'both',
}


# ── GET /api/dirs_public ─────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class DirsPublicView(View):
    """
    GET -- публичные справочники для формы регистрации.
    Не требует авторизации.
    Возвращает: {dept: [...], sectors_by_dept: {...}, position: [...], center: [...]}
    """

    def get(self, request):
        # НТЦ-центры
        center_values = list(
            NTCCenter.objects.order_by('code').values_list('code', flat=True)
        )

        # Отделы, сгруппированные по НТЦ
        depts_by_center = {}
        dept_values = []
        for d in Department.objects.select_related('ntc_center').order_by('code'):
            dept_values.append(d.code)
            if d.ntc_center:
                depts_by_center.setdefault(d.ntc_center.code, []).append(d.code)
            else:
                depts_by_center.setdefault('', []).append(d.code)

        # Секторы, сгруппированные по отделу
        sectors_by_dept = {}
        for s in Sector.objects.select_related('department').order_by('code'):
            if s.department:
                sectors_by_dept.setdefault(s.department.code, []).append(s.code)

        # Должности из POSITION_CHOICES модели Employee
        position_values = [label for _, label in Employee.POSITION_CHOICES]

        return JsonResponse({
            'dept': dept_values,
            'depts_by_center': depts_by_center,
            'sectors_by_dept': sectors_by_dept,
            'position': position_values,
            'center': center_values,
        })


# ── POST /api/register_public ────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class RegisterPublicView(View):
    """
    POST -- публичная регистрация нового пользователя.
    Создаёт User + Employee с role='user'.
    """

    def post(self, request):
        data = parse_json_body(request)

        username = data.get('username', '').strip()
        password = data.get('password', '')
        last_name = data.get('last_name', '').strip()
        first_name = data.get('first_name', '').strip()
        patronymic = data.get('patronymic', '').strip()
        position = data.get('position', '').strip()
        center = data.get('center', '').strip()
        dept = data.get('dept', '').strip()
        sector = data.get('sector', '').strip()

        # Валидация
        if not last_name:
            return JsonResponse({'error': 'Введите фамилию'}, status=400)
        if not first_name:
            return JsonResponse({'error': 'Введите имя'}, status=400)
        if not patronymic:
            return JsonResponse({'error': 'Введите отчество'}, status=400)
        if not position:
            return JsonResponse({'error': 'Выберите должность'}, status=400)

        # Определяем display-имя должности (если пришёл ключ — конвертируем)
        position_display = position
        for key, label in Employee.POSITION_CHOICES:
            if key == position:
                position_display = label
                break

        field_rule = _POSITION_FIELD_RULES.get(position_display, '')
        if field_rule == 'ntc' and not center:
            return JsonResponse({'error': 'Укажите НТЦ'}, status=400)
        if field_rule in ('dept', 'both') and not dept:
            return JsonResponse({'error': 'Укажите отдел'}, status=400)
        if field_rule == 'both' and not sector:
            return JsonResponse({'error': 'Укажите сектор'}, status=400)

        if not username or len(password) < 4:
            return JsonResponse(
                {'error': 'Логин и пароль (мин. 4 символа) обязательны'},
                status=400,
            )

        # Находим / создаём только нужные подразделения
        dept_obj = None
        sector_obj = None
        center_obj = None

        if dept:
            dept_obj, _ = Department.objects.get_or_create(
                code=dept, defaults={'name': ''}
            )
        if sector and dept_obj:
            sector_obj, _ = Sector.objects.get_or_create(
                department=dept_obj, code=sector, defaults={'name': ''}
            )
        if center:
            center_obj, _ = NTCCenter.objects.get_or_create(
                code=center, defaults={'name': ''}
            )

        # Определяем код должности (position в Employee -- это ключ choices)
        # Ищем подходящий ключ по отображаемому имени
        position_key = _resolve_position_key(position)

        try:
            user = User.objects.create_user(
                username=username,
                password=password,
            )
            Employee.objects.create(
                user=user,
                role=os.environ.get('DEFAULT_ROLE', 'user'),
                last_name=last_name,
                first_name=first_name,
                patronymic=patronymic,
                position=position_key,
                ntc_center=center_obj,
                department=dept_obj,
                sector=sector_obj,
            )
        except IntegrityError:
            return JsonResponse(
                {'error': 'Пользователь с таким логином уже существует'},
                status=400,
            )

        logger.info(
            "register_public: создан пользователь '%s' (%s, %s)",
            username, dept, sector,
        )
        return JsonResponse({'ok': True, 'id': user.pk}, status=201)


def _resolve_position_key(display_name):
    """
    Преобразует отображаемое название должности в ключ POSITION_CHOICES.
    Если совпадение не найдено, возвращает пустую строку.
    """
    if not display_name:
        return ''
    display_lower = display_name.lower().strip()
    for key, label in Employee.POSITION_CHOICES:
        if label.lower() == display_lower:
            return key
    # Если пришёл сам ключ (например 'eng_3')
    valid_keys = {k for k, _ in Employee.POSITION_CHOICES}
    if display_name in valid_keys:
        return display_name
    return ''
