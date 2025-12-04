# Museum Backend - Development Roadmap

## ✅ Phase 1: Foundation (COMPLETED)
- [x] Django project setup
- [x] Database models (User, Guard, Exhibition, Position, etc.)
- [x] Model relationships and constraints
- [x] Migrations applied
- [x] Preference system (GuardExhibitionPreference, GuardPositionPreference)

## 🚧 Phase 2: DRF API (CURRENT)
### Step 1: Serializers
Create `api/serializers.py` with:
- UserSerializer (basic + detail versions)
- GuardSerializer
- ExhibitionSerializer (list + detail)
- PositionSerializer
- PreferenceSerializers (for drag-drop preference setting)
- Nested serializers where needed

### Step 2: ViewSets & Views
Create DRF viewsets in `api/views.py`:
- UserViewSet (register, profile, list guards)
- GuardViewSet (CRUD, availability)
- ExhibitionViewSet (CRUD, positions list)
- PositionViewSet (CRUD, available guards)
- PreferenceViewSet (CRUD preferences, reorder endpoints)

### Step 3: URL Routing
Update `api/urls.py`:
- Use DRF Router for automatic REST endpoints
- Custom endpoints for special actions (preferences, assignments)

### Step 4: Permissions
Create `api/permissions.py`:
- IsAdminUser - only admins can create/edit exhibitions
- IsGuardOwner - guards can only edit their own data
- IsAuthenticatedGuard - guard-specific actions
- IsAuthenticatedAdmin - admin-specific actions

### Step 5: Authentication
Install & configure JWT:
```bash
pip install djangorestframework-simplejwt
```
- Login endpoint (POST /api/auth/login/)
- Token refresh endpoint
- User registration (optional - admins create users?)

## 📝 Phase 3: Business Logic
### Assignment Algorithm
Create `api/assignment_algorithm.py`:
- Calculate scores for guard-position matches
- Use preferences (ordinal_number → normalized priority)
- Respect availability, constraints
- Generate optimal assignments

### Point System
Create `api/point_system.py`:
- Award/deduct points based on SystemSettings
- Auto-calculate on position completion/cancellation
- Weekly point expiration logic

### Notifications
Create notification system:
- Admin notifications for important events
- Email/push notifications (optional)

## 🎨 Phase 4: React Admin Frontend
- Authentication flow (login, JWT storage)
- Admin dashboard (exhibitions, positions, guards)
- Guard preference UI (drag-drop reordering)
- Assignment review & manual override
- Reports & analytics

## 🧪 Phase 5: Testing
### API Tests (`api/tests/`)
- Model tests (validation, signals, methods)
- Serializer tests (data transformation)
- ViewSet tests (CRUD operations, permissions)
- Assignment algorithm tests (scoring logic)
- Integration tests (full workflows)

### Manual Testing
- Postman/Thunder Client collection
- Test scenarios document

## 🚀 Phase 6: Deployment
- Production settings (DEBUG=False, ALLOWED_HOSTS)
- PostgreSQL optimization (indexes, queries)
- Static file collection
- CORS configuration for React frontend
- Environment variables (.env handling)
- Docker containerization (optional)
- CI/CD pipeline (optional)

---

## Current Status: **Phase 2, Step 1**
**Next immediate task:** Create serializers for all models

## Notes:
- Django admin can be removed once React admin is complete
- Consider adding CORS headers early for frontend dev
- JWT authentication is already in requirements.txt
- Point system should run on celery tasks (scheduled jobs)
