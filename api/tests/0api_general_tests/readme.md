# Admin API General Tests - CRUD Operations

Testiranje svih CRUD operacija (Create, Read, Update, Delete) iz perspektive admin usera.
Cilj: Provjeriti može li admin kreirati/čitati/ažurirati/brisati svaki model preko API-ja.

## Status oznake:
- ✅ = Završeno
- 🔄 = U tijeku
- ⏸️ = Zaustavljeno (označava gdje sam stao)
- ❌ = Neuspješno/Bloker

---

## 1. User Model (UserViewSet)
**Endpoint:** `/api/users/`

- [ ] CREATE - Admin kreira novog usera
- [ ] READ (list) - Admin vidi sve usere
- [ ] READ (detail) - Admin vidi pojedinog usera
- [ ] UPDATE (full) - Admin ažurira usera
- [ ] UPDATE (partial) - Admin parcijalno ažurira usera
- [ ] DELETE - Admin briše usera

---

## 2. Guard Model (GuardViewSet)
**Endpoint:** `/api/guards/`

- [ ] CREATE - Admin kreira novog guarda
- [ ] READ (list) - Admin vidi sve guardove
- [ ] READ (detail) - Admin vidi pojedinog guarda
- [ ] UPDATE (full) - Admin ažurira guarda
- [ ] UPDATE (partial) - Admin parcijalno ažurira guarda
- [ ] DELETE - Admin briše guarda

---

## 3. Exhibition Model (ExhibitionViewSet)
**Endpoint:** `/api/exhibitions/`

- [ ] CREATE - Admin kreira novu izložbu
- [ ] READ (list) - Admin vidi sve izložbe
- [ ] READ (detail) - Admin vidi pojedinu izložbu
- [ ] UPDATE (full) - Admin ažurira izložbu
- [ ] UPDATE (partial) - Admin parcijalno ažurira izložbu
- [ ] DELETE - Admin briše izložbu

---

## 4. Position Model (PositionViewSet)
**Endpoint:** `/api/positions/`

- [ ] CREATE - Admin kreira novu poziciju
- [ ] READ (list) - Admin vidi sve pozicije
- [ ] READ (detail) - Admin vidi pojedinu poziciju
- [ ] UPDATE (full) - Admin ažurira poziciju
- [ ] UPDATE (partial) - Admin parcijalno ažurira poziciju
- [ ] DELETE - Admin briše poziciju

---

## 5. PositionHistory Model (PositionHistoryViewSet)
**Endpoint:** `/api/position-history/`

- [ ] CREATE - Admin kreira novi history entry
- [ ] READ (list) - Admin vidi svu position history
- [ ] READ (detail) - Admin vidi pojedini history entry
- [ ] UPDATE (full) - Admin ažurira history entry
- [ ] UPDATE (partial) - Admin parcijalno ažurira history entry
- [ ] DELETE - Admin briše history entry

---

## 6. Point Model (PointViewSet)
**Endpoint:** `/api/points/`

- [ ] CREATE - Admin kreira novi point entry
- [ ] READ (list) - Admin vidi sve pointove
- [ ] READ (detail) - Admin vidi pojedini point entry
- [ ] UPDATE (full) - Admin ažurira point entry
- [ ] UPDATE (partial) - Admin parcijalno ažurira point entry
- [ ] DELETE - Admin briše point entry

---

## 7. PositionSwapRequest Model (PositionSwapRequestViewSet)
**Endpoint:** `/api/position-swap-requests/`

- [ ] CREATE - Admin kreira novi swap request
- [ ] READ (list) - Admin vidi sve swap requestove
- [ ] READ (detail) - Admin vidi pojedini swap request
- [ ] UPDATE (full) - Admin ažurira swap request
- [ ] UPDATE (partial) - Admin parcijalno ažurira swap request
- [ ] DELETE - Admin briše swap request

---

## 8. AdminNotification Model (AdminNotificationViewSet)
**Endpoint:** `/api/admin-notifications/`

- [ ] CREATE - Admin kreira novu notifikaciju
- [ ] READ (list) - Admin vidi sve notifikacije
- [ ] READ (detail) - Admin vidi pojedinu notifikaciju
- [ ] UPDATE (full) - Admin ažurira notifikaciju
- [ ] UPDATE (partial) - Admin parcijalno ažurira notifikaciju
- [ ] DELETE - Admin briše notifikaciju

---

## 9. Report Model (ReportViewSet)
**Endpoint:** `/api/reports/`

- [ ] CREATE - Admin kreira novi report
- [ ] READ (list) - Admin vidi sve reportove
- [ ] READ (detail) - Admin vidi pojedini report
- [ ] UPDATE (full) - Admin ažurira report
- [ ] UPDATE (partial) - Admin parcijalno ažurira report
- [ ] DELETE - Admin briše report

---

## 10. SystemSettings Model (SystemSettingsViewSet)
**Endpoint:** `/api/system-settings/`

- [ ] CREATE - Admin kreira nove settings (ako dozvoljeno)
- [ ] READ (list) - Admin vidi sve settings
- [ ] READ (detail) - Admin vidi pojedine settings
- [ ] UPDATE (full) - Admin ažurira settings
- [ ] UPDATE (partial) - Admin parcijalno ažurira settings
- [ ] DELETE - Admin briše settings (ako dozvoljeno)

---

## 11. NonWorkingDay Model
**Endpoint:** `/api/non-working-days/` (ako postoji ViewSet)

- [ ] CREATE - Admin kreira novi non-working day
- [ ] READ (list) - Admin vidi sve non-working days
- [ ] READ (detail) - Admin vidi pojedini non-working day
- [ ] UPDATE (full) - Admin ažurira non-working day
- [ ] UPDATE (partial) - Admin parcijalno ažurira non-working day
- [ ] DELETE - Admin briše non-working day

---

## 12. GuardExhibitionPreference Model
**Endpoint:** `/api/guard-exhibition-preferences/` (ako postoji ViewSet)

- [ ] CREATE - Admin kreira novu preferencu
- [ ] READ (list) - Admin vidi sve preferencije
- [ ] READ (detail) - Admin vidi pojedinu preferencu
- [ ] UPDATE (full) - Admin ažurira preferencu
- [ ] UPDATE (partial) - Admin parcijalno ažurira preferencu
- [ ] DELETE - Admin briše preferencu

---

## 13. GuardDayPreference Model
**Endpoint:** `/api/guard-day-preferences/` (ako postoji ViewSet)

- [ ] CREATE - Admin kreira novu day preferencu
- [ ] READ (list) - Admin vidi sve day preferencije
- [ ] READ (detail) - Admin vidi pojedinu day preferencu
- [ ] UPDATE (full) - Admin ažurira day preferencu
- [ ] UPDATE (partial) - Admin parcijalno ažurira day preferencu
- [ ] DELETE - Admin briše day preferencu

---

## 14. AuditLog Model (AuditLogViewSet)
**Endpoint:** `/api/audit-logs/`

- [ ] CREATE - Admin kreira novi audit log (obično automatski)
- [ ] READ (list) - Admin vidi sve audit logove
- [ ] READ (detail) - Admin vidi pojedini audit log
- [ ] UPDATE (full) - Admin ažurira audit log (obično ne bi trebao)
- [ ] UPDATE (partial) - Admin parcijalno ažurira audit log
- [ ] DELETE - Admin briše audit log (obično ne bi trebao)

---

## 15. HourlyRateHistory Model
**Endpoint:** `/api/hourly-rate-history/` (ako postoji ViewSet)

- [ ] CREATE - Admin kreira novu hourly rate history entry
- [ ] READ (list) - Admin vidi sve hourly rate history
- [ ] READ (detail) - Admin vidi pojedinu hourly rate entry
- [ ] UPDATE (full) - Admin ažurira hourly rate entry
- [ ] UPDATE (partial) - Admin parcijalno ažurira hourly rate entry
- [ ] DELETE - Admin briše hourly rate entry

---

## Napomene:

- Neki modeli možda nemaju ViewSet (npr. GuardAvailablePositions, GuardWorkPeriod) - preskočiti
- Očekivani rezultati: 
  - 200/201 za uspješne operacije
  - 403 Forbidden ako admin nema pravo
  - 405 Method Not Allowed ako endpoint ne podržava operaciju
  - 400 Bad Request za validacijske greške
- Svaki test file: `test_crud_{model_name}.py`
- Struktura: TestAdminCRUD{ModelName} klasa s 6 test metoda
