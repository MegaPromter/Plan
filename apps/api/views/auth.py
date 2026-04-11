"""
API для публичной регистрации и публичных справочников.

POST    /api/register_public  -- самостоятельная регистрация (role='user')
GET     /api/dirs_public      -- справочники для формы регистрации (без авторизации)
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.models import Department, Employee, NTCCenter, Sector

User = get_user_model()
logger = logging.getLogger(__name__)

_POSITION_FIELD_RULES = {
    "Руководитель НТЦ": "ntc",
    "Зам. руководителя НТЦ": "ntc",
    "Начальник отдела": "dept",
    "Зам. начальника отдела": "dept",
    "Техник-конструктор": "both",
    "Техник-конструктор 2 кат.": "both",
    "Техник-конструктор 1 кат.": "both",
    "Специалист": "both",
    "Специалист 2 кат.": "both",
    "Специалист 1 кат.": "both",
    "Ведущий специалист": "both",
    "Инженер-конструктор": "both",
    "Инженер-конструктор 3 кат.": "both",
    "Инженер-конструктор 2 кат.": "both",
    "Инженер-конструктор 1 кат.": "both",
    "Ведущий инженер-конструктор": "both",
    "Ведущий инженер по направлению 3 класса": "both",
    "Ведущий инженер по направлению 2 класса": "both",
    "Ведущий инженер - координатор группы": "both",
    "Начальник бюро": "both",
    "Младший научный сотрудник": "both",
    "Старший научный сотрудник": "both",
    "Ведущий научный сотрудник": "both",
    "Начальник сектора": "both",
    "Зам. начальника отдела – начальник сектора": "both",
    "Руководитель направления": "both",
}

_POSITION_TO_ROLE = {
    "ntc_head": Employee.ROLE_NTC_HEAD,
    "ntc_deputy": Employee.ROLE_NTC_DEPUTY,
    "dept_head": Employee.ROLE_DEPT_HEAD,
    "dept_deputy": Employee.ROLE_DEPT_DEPUTY,
    "dept_deputy_sector": Employee.ROLE_SECTOR_HEAD,
    "sector_head": Employee.ROLE_SECTOR_HEAD,
}


class DirsPublicView(APIView):
    """
    GET -- публичные справочники для формы регистрации.
    Не требует авторизации.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        center_values = list(
            NTCCenter.objects.order_by("code").values_list("code", flat=True)
        )

        depts_by_center = {}
        dept_values = []
        for d in Department.objects.select_related("ntc_center").order_by("code"):
            dept_values.append(d.code)
            if d.ntc_center:
                depts_by_center.setdefault(d.ntc_center.code, []).append(d.code)
            else:
                depts_by_center.setdefault("", []).append(d.code)

        sectors_by_dept = {}
        for s in Sector.objects.select_related("department").order_by("code"):
            if s.department:
                sectors_by_dept.setdefault(s.department.code, []).append(s.code)

        position_values = [label for _, label in Employee.POSITION_CHOICES]

        return Response(
            {
                "dept": dept_values,
                "depts_by_center": depts_by_center,
                "sectors_by_dept": sectors_by_dept,
                "position": position_values,
                "center": center_values,
            }
        )


class RegisterPublicView(APIView):
    """
    POST -- публичная регистрация нового пользователя.
    Создаёт User + Employee с role='user'.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        username = data.get("username", "").strip()
        password = data.get("password", "")
        last_name = data.get("last_name", "").strip()
        first_name = data.get("first_name", "").strip()
        patronymic = data.get("patronymic", "").strip()
        position = data.get("position", "").strip()
        center = data.get("center", "").strip()
        dept = data.get("dept", "").strip()
        sector = data.get("sector", "").strip()
        email = data.get("email", "").strip()

        if not last_name:
            return Response({"error": "Введите фамилию"}, status=400)
        if not first_name:
            return Response({"error": "Введите имя"}, status=400)
        if not patronymic:
            return Response({"error": "Введите отчество"}, status=400)
        if not position:
            return Response({"error": "Выберите должность"}, status=400)

        position_display = position
        for key, label in Employee.POSITION_CHOICES:
            if key == position:
                position_display = label
                break

        field_rule = _POSITION_FIELD_RULES.get(position_display, "")
        if field_rule == "ntc" and not center:
            return Response({"error": "Укажите НТЦ"}, status=400)
        if field_rule in ("dept", "both") and not dept:
            return Response({"error": "Укажите отдел"}, status=400)
        if field_rule == "both" and not sector:
            return Response({"error": "Укажите сектор"}, status=400)

        if not username:
            return Response({"error": "Логин обязателен"}, status=400)

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjValidationError

        try:
            validate_password(password)
        except DjValidationError as e:
            return Response({"error": "; ".join(e.messages)}, status=400)

        dept_obj = None
        sector_obj = None
        center_obj = None

        if dept:
            dept_obj, _ = Department.objects.get_or_create(
                code=dept, defaults={"name": ""}
            )
        if sector and dept_obj:
            sector_obj, _ = Sector.objects.get_or_create(
                department=dept_obj, code=sector, defaults={"name": ""}
            )
        if center:
            center_obj, _ = NTCCenter.objects.get_or_create(
                code=center, defaults={"name": ""}
            )

        position_key = _resolve_position_key(position)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                )
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
            return Response(
                {"error": e.message if hasattr(e, "message") else str(e)},
                status=400,
            )
        except IntegrityError:
            logger.warning("register_public: дубликат логина '%s'", username)
            return Response(
                {"error": "Пользователь с таким логином уже существует"},
                status=400,
            )

        logger.info(
            "register_public: создан пользователь '%s' (role=%s, %s, %s)",
            username,
            role,
            dept,
            sector,
        )
        return Response({"ok": True, "id": user.pk}, status=201)


from apps.api.utils import resolve_position_key as _resolve_position_key
