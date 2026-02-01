POZADINSKE CELERY FUNKCIONALNOSTI

    GLAVNE FUNKCIONALNOSTI

    1. shift_weekly_periods()

        - mijenja next_week u this_week i generira novi next_week i time označava početak novog tjednog ciklusa (next_week_start ... ) -> svi su readonly polja, nitko ih ne moze mijenjati
        - izvršava se ponedjeljom u ponoć (prve minute svakog ponedjeljka)

    1. generate_weekly_positions()

        - Generira pozicije na temelju aktivnih izložbi. Kreira 2 smjene po danu (jutarnja i popodnevna) za
        svaku poziciju jedne izložbe (ovisno o broju pozicija koji jedna izložba zahtjeva).
        - Ne generira pozicije za neradne dane ili neradne dijelove dana
        - izvršava se druge minute svakog ponedjeljka, nakon shift_weekly_periods
        - pozicije se brišu ako admin naknadno doda NonWorkingDay koji se poklapa s njima ->
            NonWorkingDay.delete_affected_positions() (model method)
        -> one izložbe koje su jednodnevni događaji, odnosno posebni doagađaji (otvorenja, konerti itd) se također generiraju, kod njih se ne provjerava padaju li na neki neradni dan, pretpostavlja se da je admin svjesno postavio taj događaj na neradni dan
        - ako se izložbe dodaju naknadno, a this week i next week su definirani, pozicije će se generirati po spremanju nove izložbe u bazu, bilo da je izložba regularna ili poseban događaj
        ->

---

# PYTEST TEST INFRASTRUCTURE

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run specific test file
pytest api/tests/1model_tests/test_user.py

# Run specific test class
pytest api/tests/1model_tests/test_user.py::TestUserModelSaveLogic

# Run specific test method
pytest api/tests/1model_tests/test_user.py::TestUserModelSaveLogic::test_admin_role_automatically_sets_staff_flag

# Run tests with specific marker
pytest -m unit              # Only unit tests
pytest -m integration       # Only integration tests
pytest -m "not slow"        # Skip slow tests

# Run with coverage
pytest --cov=api --cov-report=html

# Run in parallel (faster)
pytest -n auto

# Run with verbose output
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Run last failed tests
pytest --lf

# Run tests matching pattern
pytest -k "assign"          # Run tests with "assign" in name
pytest -k "user or guard"   # Run tests with "user" OR "guard" in name
```

## Test Structure

- **conftest.py**: Shared fixtures (users, settings, positions)
- **pytest.ini**: Configuration (markers, database reuse)
- Unit tests: Fast, isolated logic (no API calls)
- Integration tests: API endpoints, multiple components
  @receiver(post_save, sender=Exhibition)
  def generate_positions_on_exhibition_create(sender, instance, created, \*\*kwargs)
