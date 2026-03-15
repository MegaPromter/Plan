"""
Контекстные процессоры — добавляют переменные в контекст каждого шаблона.
"""


def active_nav(request):
    """Определяет active_nav по текущему URL для подсветки пункта сайдбара."""
    path = request.path
    mapping = [
        ('/works/projects/', 'projects'),
        ('/works/production-plan/', 'pp'),
        ('/works/plan/', 'plan'),
        ('/works/notices/', 'notices'),
        ('/works/business-trips/', 'business_trips'),
        ('/works/work-calendar/', 'work_calendar'),
        ('/employees/vacations/', 'vacation_plan'),
        ('/employees/', 'employees'),
        ('/accounts/dashboard/', 'dashboard'),
    ]
    for prefix, nav in mapping:
        if path.startswith(prefix):
            return {'active_nav': nav}
    if path == '/':
        return {'active_nav': 'dashboard'}
    return {'active_nav': ''}
