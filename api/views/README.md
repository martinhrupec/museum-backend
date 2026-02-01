# API Views Refactoring

## Struktura

Stari `api/views.py` (1970 linija) razdvojen je na manje module:

```
api/views/
├── __init__.py                             # Centralni import point
├── general_views.py                         # Standalone funkcije (session_login, session_logout, session_check)
├── user_viewset.py                          # UserViewSet
├── guard_viewset.py                         # GuardViewSet (sa 4 custom actions)
├── exhibition_viewset.py                    # ExhibitionViewSet
├── position_viewset.py                      # PositionViewSet
├── position_history_viewset.py              # PositionHistoryViewSet (assign, cancel, report_lateness, bulk_cancel)
├── non_working_day_viewset.py               # NonWorkingDayViewSet
├── point_viewset.py                         # PointViewSet
├── admin_notification_viewset.py            # AdminNotificationViewSet
├── report_viewset.py                        # ReportViewSet
├── system_settings_viewset.py               # SystemSettingsViewSet
├── guard_exhibition_preference_viewset.py   # GuardExhibitionPreferenceViewSet
└── guard_day_preference_viewset.py          # GuardDayPreferenceViewSet
```

## Korištenje

### Import u drugim modulima

```python
# Automatski importa sve ViewSets i funkcije
from api import views

# Ili specifično
from api.views import UserViewSet, GuardViewSet, session_login
```

### URLs

`api/urls.py` nije trebao promjene - već koristi `from . import views`.

## Backup

Originalni fajl spremljen kao `api/views_old.py` za sigurnost.

## Benefiti

1. **Lakše navigiranje** - svaki ViewSet u svom fajlu
2. **Brže učitavanje** - IDE-ovi bolje rade s manjim fajlovima
3. **Jednostavnije održavanje** - izmjene lokalizirane na mali fajl
4. **Bolje testiranje** - jasna separacija odgovornosti
5. **Team rad** - manje merge konflikata

## Testing

```bash
# Django check
python manage.py check

# Test imports
python -c "from api.views import UserViewSet; print('OK')"
```
