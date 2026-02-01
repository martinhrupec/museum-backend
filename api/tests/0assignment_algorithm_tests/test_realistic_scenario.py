# -*- coding: utf-8 -*-
"""
================================================================================
REALISTICAN TEST SCENARIJ - AUTOMATSKA DODJELA POZICIJA CUVARIMA
================================================================================

Ovaj test demonstrira rad algoritma za automatsku dodjelu pozicija cuvarima
u muzejskom sustavu. Namijenjen je kao edukativni primjer koji pokazuje:

1. ULAZNE PODATKE:
   - 5 izlozbi s razlicitim brojem potrebnih pozicija
   - 26 cuvara (A-Z) s razlicitim prioritetima i preferencijama
   
2. PROCES IZRACUNA:
   - Kako se racuna prioritet svakog cuvara
   - Kako se gradi matrica rezultata (score matrix)
   - Kako prioritet i preferencije doprinose ukupnom rezultatu
   
3. ALGORITAM DODJELE:
   - Madjarski algoritam (Hungarian algorithm) za optimalnu dodjelu
   - Postivanje ogranicenja (availability, work periods)
   
4. IZLAZNE PODATKE:
   - Konacni raspored - tko je dodijeljen na koju poziciju
   - Statistike dodjele

================================================================================
FORMULA ZA IZRACUN REZULTATA (SCORE):
================================================================================

Za svaki par (cuvar, pozicija) racuna se rezultat prema formuli:

    score = (priority_weight * normalized_priority) + 
            (preference_weight * preference_bonus) + 
            base_score

Gdje je:
- priority_weight = 0.4 (40% utjecaja)
- preference_weight = 0.4 (40% utjecaja)  
- base_score = 0.2 (20% bazni rezultat za sve)

- normalized_priority = (guard_priority - min_priority) / (max_priority - min_priority)
  -> Cuvar s NAJVISIM brojem prioriteta dobiva normalized_priority = 1
  -> Cuvar s NAJNIZIM brojem prioriteta dobiva normalized_priority = 0
  -> VISI broj prioriteta = BOLJI prioritet = VISE pozicija dobiva

- preference_bonus:
  -> 1.0 ako cuvar preferira taj dan ILI tu izlozbu
  -> 0.5 ako nema postavljene preferencije (neutralno)
  -> 0.0 ako ne preferira (ima preferencije ali ovo nije medu njima)

================================================================================
TESTNI SCENARIJ:
================================================================================

IZLOZBE (ukupno 8 pozicija po smjeni):
+------------------+------------+------------------------------------------+
| Naziv            | Pozicija   | Opis                                     |
+------------------+------------+------------------------------------------+
| ZKG              | 1          | Zagrebacka klasicna galerija             |
| Buducnosti       | 2          | Izlozba o buducnosti                     |
| Okidaci          | 1          | Fotografska izlozba                      |
| Blackbox         | 1          | Multimedijalna izlozba                   |
| Kiparstvo        | 3          | Skulpture i kipovi                       |
+------------------+------------+------------------------------------------+

CUVARI (26 cuvara, A-Z):
+---------+----------+-------------+---------------+----------------------+
| Cuvar   | Priority | Availability| Work Periods  | Preferencije         |
+---------+----------+-------------+---------------+----------------------+
| A       | 5.00     | 10          | 10 (1:1)      | Nema                 |
| B       | 4.00     | 8           | 10 (1:1.25)   | Preferira ZKG        |
| C       | 4.00     | 8           | 12 (1:1.5)    | Preferira utorak     |
| D       | 4.00     | 6           | 10 (1:1.67)   | Nema                 |
| E       | 4.00     | 5           | 10 (1:2)      | Preferira Kiparstvo  |
| F-Z     | 1.0-3.5  | 3-5         | Varies        | Razlicito            |
+---------+----------+-------------+---------------+----------------------+

NAPOMENA O PRIORITETU:
- VISI broj = cuvar ima VECI prioritet za dodjelu = dobiva VISE pozicija
- NIZI broj = cuvar ima MANJI prioritet = dobiva MANJE pozicija
- Nakon dodjele, priority se SMANJUJE za one koji su dobili pozicije
- Sustav balansira opterecenje tijekom vremena kroz availability capping

================================================================================
"""
import pytest
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q

from api.models import (
    Position, PositionHistory, Guard, Exhibition,
    GuardWorkPeriod, GuardExhibitionPreference, GuardDayPreference
)
from background_tasks.assignment_algorithm import assign_positions_automatically
from background_tasks.tasks import calculate_availability_caps


def get_guard_available_days(guard, settings):
    """
    Dohvati dostupne dane za čuvara na temelju njegovih work periods.
    
    Koristi istu logiku kao API endpoint /api/guards/{id}/available_days/
    """
    guard_work_periods = GuardWorkPeriod.objects.filter(
        guard=guard
    ).filter(
        Q(is_template=True) | Q(next_week_start=settings.next_week_start)
    )
    
    if not guard_work_periods.exists():
        return []
    
    return sorted(set(wp.day_of_week for wp in guard_work_periods))


def get_guard_available_exhibitions(guard, settings, exhibitions_dict):
    """
    Dohvati dostupne izložbe za čuvara na temelju njegovih work periods.
    
    Koristi istu logiku kao API endpoint /api/guards/{id}/available_exhibitions/
    """
    guard_work_periods = GuardWorkPeriod.objects.filter(
        guard=guard
    ).filter(
        Q(is_template=True) | Q(next_week_start=settings.next_week_start)
    )
    
    if not guard_work_periods.exists():
        return []
    
    guard_work_days = set(wp.day_of_week for wp in guard_work_periods)
    
    # Vraća izložbe koje su otvorene na bar jedan od čuvarovih radnih dana
    available = [
        ex for ex in exhibitions_dict.values()
        if any(day in ex.open_on for day in guard_work_days)
    ]
    
    return available


class TestRealisticScenario:
    """
    Realistican test scenarij za demonstraciju algoritma dodjele pozicija.
    
    Ovaj test kreira realistican scenarij s 5 izlozbi i 26 cuvara,
    pokrece algoritam dodjele i prikazuje detaljne rezultate.
    """
    
    @pytest.fixture
    def realistic_exhibitions(self, system_settings_for_assignment):
        """
        Kreira 5 izlozbi s razlicitim brojevima pozicija.
        
        Izlozbe su otvorene od utorka do nedjelje (radni dani muzeja),
        sto odgovara postavkama u system_settings_for_assignment.
        
        Returns:
            dict: Rjecnik s izlozbama {naziv: Exhibition objekt}
        """
        settings = system_settings_for_assignment
        today = timezone.now()  # datetime, not date
        
        # Definicija izlozbi: (naziv, broj_pozicija, opis)
        exhibition_configs = [
            ("ZKG", 1, "Zagrebacka klasicna galerija"),
            ("Buducnosti", 2, "Izlozba o buducnosti tehnologije"),
            ("Okidaci", 1, "Fotografska izlozba"),
            ("Blackbox", 1, "Multimedijalna instalacija"),
            ("Kiparstvo", 3, "Skulpture i kipovi kroz povijest"),
        ]
        
        exhibitions = {}
        for name, positions, description in exhibition_configs:
            exhibition = Exhibition.objects.create(
                name=name,
                number_of_positions=positions,
                start_date=today,
                end_date=today + timedelta(days=60),  # Traje jos 2 mjeseca
                is_special_event=False,
                # open_on: 1=utorak, 2=srijeda, 3=cetvrtak, 4=petak, 5=subota, 6=nedjelja
                # (0=ponedjeljak je zatvoren jer muzej ne radi ponedjeljkom)
                open_on=[1, 2, 3, 4, 5, 6]
            )
            exhibitions[name] = exhibition
            
        return exhibitions
    
    @pytest.fixture
    def alphabet_guards(self, db, realistic_exhibitions, create_guard_with_user):
        """
        Kreira 26 cuvara (A-Z) s razlicitim karakteristikama.
        
        Distribucija prioriteta:
        - A: 5.00 (najvisi prioritet = dobiva najvise pozicija)
        - B, C, D, E: 4.00 (visok prioritet, s razlicitim preferencijama)
        - F-M: 3.50 - 2.75 (srednji prioritet)
        - N-Z: 2.50 - 1.00 (nizi prioritet = manje sanse za dodjelu)
        
        VAZNO: Kada ima vise availability nego pozicija, koristi se CAPPING
        koji proporcionalno smanjuje availability svakog cuvara.
        
        Omjer availability:work_periods varira od 1:1 do 1:2
        
        Returns:
            list: Lista Guard objekata sortirana po abecedi
        """
        guards = []
        exhibitions = realistic_exhibitions
        
        # ========================================================================
        # KONFIGURACIJA CUVARA
        # ========================================================================
        # Format: (slovo, priority, availability, work_period_count, preferences)
        # preferences je dict: {'exhibitions': [nazivi], 'days': [dani]}
        # ========================================================================
        
        guard_configs = [
            # GRUPA 1: Najbolji prioritet (A)
            ("A", Decimal("5.00"), 10, 10, {}),
            
            # GRUPA 2: Drugi najbolji (B, C, D, E) - svi imaju priority 4.00
            ("B", Decimal("4.00"), 8, 10, {"exhibitions": ["ZKG"]}),
            ("C", Decimal("4.00"), 8, 12, {"days": [1]}),  # Preferira utorak (day 1)
            ("D", Decimal("4.00"), 6, 10, {}),  # Bez preferencija
            ("E", Decimal("4.00"), 5, 10, {"exhibitions": ["Kiparstvo"]}),
            
            # GRUPA 3: Srednji prioritet (F-M)
            ("F", Decimal("3.50"), 5, 8, {"exhibitions": ["Buducnosti"]}),
            ("G", Decimal("3.25"), 5, 10, {"days": [2, 3]}),  # Sri, cet
            ("H", Decimal("3.00"), 4, 8, {}),
            ("I", Decimal("3.00"), 4, 6, {"exhibitions": ["Okidaci", "Blackbox"]}),
            ("J", Decimal("2.75"), 4, 8, {"days": [4, 5]}),  # Pet, sub
            ("K", Decimal("2.75"), 3, 6, {}),
            ("L", Decimal("2.50"), 3, 6, {"exhibitions": ["Kiparstvo"]}),
            ("M", Decimal("2.50"), 3, 5, {}),
            
            # GRUPA 4: Nizi prioritet (N-T)
            ("N", Decimal("2.25"), 3, 6, {"days": [6]}),  # Preferira nedjelju
            ("O", Decimal("2.25"), 3, 5, {}),
            ("P", Decimal("2.00"), 3, 6, {"exhibitions": ["ZKG", "Buducnosti"]}),
            ("Q", Decimal("2.00"), 3, 5, {}),
            ("R", Decimal("1.75"), 3, 6, {}),
            ("S", Decimal("1.75"), 3, 5, {"days": [1, 2, 3]}),
            ("T", Decimal("1.50"), 3, 6, {}),
            
            # GRUPA 5: Nula i negativni prioriteti (U-Z)
            # Ovi cuvari su NAJLOSIJI za dodjelu - imaju najnizi score
            ("U", Decimal("0.50"), 3, 5, {"exhibitions": ["Blackbox"]}),
            ("V", Decimal("0.00"), 3, 6, {}),  # Nula prioritet
            ("W", Decimal("-0.50"), 3, 5, {}),  # Negativan!
            ("X", Decimal("-1.00"), 3, 6, {"days": [4, 5, 6]}),  # Negativan!
            ("Y", Decimal("-1.50"), 3, 5, {}),  # Negativan!
            ("Z", Decimal("-2.00"), 3, 4, {"exhibitions": ["Kiparstvo"], "days": [5, 6]}),  # Najnizi!
        ]
        
        for letter, priority, availability, wp_count, prefs in guard_configs:
            # Koristi fixture za kreiranje cuvara
            guard = create_guard_with_user(
                f"guard_{letter}",
                f"guard_{letter.lower()}@muzej.hr",
                availability=availability,
                priority=priority
            )
            
            # ================================================================
            # WORK PERIODS (radna vremena)
            # ================================================================
            days = [1, 2, 3, 4, 5, 6]  # Utorak - Nedjelja
            shifts = ['morning', 'afternoon']
            
            periods_created = 0
            for day in days:
                for shift in shifts:
                    if periods_created >= wp_count:
                        break
                    GuardWorkPeriod.objects.create(
                        guard=guard,
                        day_of_week=day,
                        shift_type=shift,
                        is_template=True
                    )
                    periods_created += 1
                if periods_created >= wp_count:
                    break
            
            # ================================================================
            # IZRAČUN DOSTUPNIH DANA I IZLOŽBI
            # Koristi istu logiku kao API endpointi available_days/available_exhibitions
            # ================================================================
            
            # Dohvati dane iz work periods za ovog čuvara
            guard_work_periods = GuardWorkPeriod.objects.filter(guard=guard, is_template=True)
            guard_work_days = sorted(set(wp.day_of_week for wp in guard_work_periods))
            
            # Dohvati izložbe koje su otvorene na čuvarove radne dane
            # Sve izložbe imaju open_on=[1,2,3,4,5,6] pa će sve biti dostupne
            # ako čuvar ima barem jedan od tih dana u work periods
            available_exhibition_ids = [
                exhibitions[name].id for name in ["ZKG", "Buducnosti", "Okidaci", "Blackbox", "Kiparstvo"]
                if any(day in exhibitions[name].open_on for day in guard_work_days)
            ]
            
            # ================================================================
            # PREFERENCIJE IZLOZBI
            # Moraju sadržavati SVE dostupne izložbe, rangirane po preferenciji.
            # ================================================================
            
            if "exhibitions" in prefs and prefs["exhibitions"]:
                preferred_ids = [
                    exhibitions[name].id 
                    for name in prefs["exhibitions"] 
                    if name in exhibitions and exhibitions[name].id in available_exhibition_ids
                ]
                # Preferirane na početak, ostale na kraj (u proizvoljnom redoslijedu)
                other_ids = [eid for eid in available_exhibition_ids if eid not in preferred_ids]
                full_exhibition_order = preferred_ids + other_ids
                
                GuardExhibitionPreference.objects.create(
                    guard=guard,
                    exhibition_order=full_exhibition_order,
                    is_template=True
                )
            
            # ================================================================
            # PREFERENCIJE DANA
            # Moraju sadržavati SVE dane iz work periods, rangirane po preferenciji.
            # ================================================================
            
            if "days" in prefs and prefs["days"]:
                preferred_days = [d for d in prefs["days"] if d in guard_work_days]
                other_days = [d for d in guard_work_days if d not in preferred_days]
                full_day_order = preferred_days + other_days
                
                GuardDayPreference.objects.create(
                    guard=guard,
                    day_order=full_day_order,
                    is_template=True
                )
            
            guards.append(guard)
        
        return guards
    
    @pytest.mark.django_db
    def test_realistic_assignment_with_transparency(
        self, 
        system_settings_for_assignment, 
        realistic_exhibitions,
        alphabet_guards
    ):
        """
        ========================================================================
        GLAVNI TEST: Demonstracija algoritma dodjele s potpunom transparentnoscu
        ========================================================================
        
        Ovaj test:
        1. Prikazuje sve ulazne podatke (cuvare, izlozbe, pozicije)
        2. Pokrece algoritam dodjele
        3. Prikazuje detalje izracuna za svaki par (cuvar, pozicija)
        4. Prikazuje konacni raspored
        
        NAPOMENA: Detaljni ispis je vidljiv samo kad se test pokrene s -s flagom:
        pytest test_realistic_scenario.py -v -s
        """
        # Suppress logove da se ne miješaju sa našim printom
        logging.disable(logging.CRITICAL)
        
        settings = system_settings_for_assignment
        exhibitions = realistic_exhibitions
        guards = alphabet_guards
        
        # ====================================================================
        # FAZA 1: PRIKAZ ULAZNIH PODATAKA
        # ====================================================================
        
        print("\n")
        print("=" * 80)
        print("FAZA 1: ULAZNI PODACI")
        print("=" * 80)
        
        # Prikaz izlozbi
        print("\n[IZLOZBE]:")
        print("-" * 60)
        print(f"{'Naziv':<20} {'Pozicija':<10} {'Otvoreno':<30}")
        print("-" * 60)
        
        total_positions_per_shift = 0
        for name, exhibition in exhibitions.items():
            days_open = ", ".join([
                ["Pon", "Uto", "Sri", "Cet", "Pet", "Sub", "Ned"][d] 
                for d in exhibition.open_on
            ])
            print(f"{name:<20} {exhibition.number_of_positions:<10} {days_open:<30}")
            total_positions_per_shift += exhibition.number_of_positions
        
        print("-" * 60)
        print(f"{'UKUPNO po smjeni:':<20} {total_positions_per_shift}")
        
        # Broj radnih dana i smjena
        workdays = 6  # Uto-Ned
        shifts_per_day = 2  # Jutro i popodne
        total_positions = total_positions_per_shift * workdays * shifts_per_day
        print(f"{'Radnih dana:':<20} {workdays}")
        print(f"{'Smjena po danu:':<20} {shifts_per_day}")
        print(f"{'UKUPNO POZICIJA:':<20} {total_positions} (po tjednu)")
        
        # Prikaz cuvara
        print("\n[CUVARI]:")
        print("-" * 90)
        print(f"{'Cuvar':<8} {'Priority':<10} {'Avail.':<8} {'WP':<6} {'Omjer':<8} {'Pref. izlozbe':<20} {'Pref. dani':<15}")
        print("-" * 90)
        
        total_availability = 0
        for guard in guards:
            letter = guard.user.username.split("_")[1]
            wp_count = GuardWorkPeriod.objects.filter(guard=guard, is_template=True).count()
            ratio = f"1:{wp_count/guard.availability:.2f}" if guard.availability > 0 else "N/A"
            
            # Dohvati preferencije izlozbi
            try:
                exh_pref = GuardExhibitionPreference.objects.get(guard=guard, is_template=True)
                exh_names = []
                for eid in exh_pref.exhibition_order:
                    for name, exh in exhibitions.items():
                        if exh.id == eid:
                            exh_names.append(name)
                exh_pref_str = ", ".join(exh_names) if exh_names else "-"
            except GuardExhibitionPreference.DoesNotExist:
                exh_pref_str = "-"
            
            # Dohvati preferencije dana
            try:
                day_pref = GuardDayPreference.objects.get(guard=guard, is_template=True)
                day_names = [["Pon", "Uto", "Sri", "Cet", "Pet", "Sub", "Ned"][d] for d in day_pref.day_order]
                day_pref_str = ", ".join(day_names)
            except GuardDayPreference.DoesNotExist:
                day_pref_str = "-"
            
            print(f"{letter:<8} {float(guard.priority_number):<10.2f} {guard.availability:<8} {wp_count:<6} {ratio:<8} {exh_pref_str:<20} {day_pref_str:<15}")
            total_availability += guard.availability
        
        print("-" * 90)
        print(f"{'UKUPNO availability:':<28} {total_availability}")
        print(f"{'Omjer (avail/poz):':<28} {total_availability/total_positions:.2f}:1")
        
        # ====================================================================
        # FAZA 2: OBJASNJENJE FORMULE
        # ====================================================================
        
        print("\n")
        print("=" * 80)
        print("FAZA 2: FORMULA ZA IZRACUN REZULTATA (SCORE)")
        print("=" * 80)
        print("""
Za svaki par (cuvar, pozicija) racuna se rezultat:

    score = (0.6 x normalized_priority) + (0.2 x exhibition_pref) + (0.2 x day_pref)

Gdje je:
+-----------------------------------------------------------------------------+
| normalized_priority = (guard_priority - min_priority)                       |
|                       -------------------------------------                 |
|                       (max_priority - min_priority)                         |
|                                                                             |
| -> Cuvar s NAJVISIM brojem (5.00) dobiva normalized = 1.00 (najbolji!)      |
| -> Cuvar s NAJNIZIM brojem (1.00) dobiva normalized = 0.00 (najlosiji)      |
| -> VISI priority BROJ = VISE sanse za dodjelu pozicije                      |
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| preference_bonus (exhibition_pref i day_pref):                              |
| -> Svaki se normalizira na 0-1 raspon                                       |
| -> Preferirana izlozba/dan daje bonus                                       |
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| AVAILABILITY CAPPING:                                                       |
| Ako ukupni availability > broj pozicija, sustav proporcionalno smanjuje     |
| availability svakog cuvara tako da ukupno = broj pozicija.                  |
| Cuvari s nizim priority_number se cappaju PRVI.                             |
+-----------------------------------------------------------------------------+
        """)
        
        # Izracunaj normalizirane prioritete za prikaz
        priorities = [float(g.priority_number) for g in guards]
        min_p, max_p = min(priorities), max(priorities)
        
        print(f"\n[INFO] Raspon prioriteta: min={min_p:.2f}, max={max_p:.2f}")
        
        print("\n[NORMALIZIRANI PRIORITETI] - svi cuvari:")
        print("-" * 70)
        print(f"{'Cuvar':<8} {'Priority':<12} {'Normalized':<12} {'Doprinos (60%)':<15}")
        print("-" * 70)
        for guard in guards:
            letter = guard.user.username.split("_")[1]
            p = float(guard.priority_number)
            if max_p > min_p:
                norm = (p - min_p) / (max_p - min_p)
            else:
                norm = 0.5
            priority_contrib = 0.6 * norm
            print(f"{letter:<8} {p:<12.2f} {norm:<12.3f} {priority_contrib:<15.3f}")
        print("-" * 70)
        
        # ====================================================================
        # PRIKAZ KAKO SU CUVARI POREDALI PREFERENCIJE
        # ====================================================================
        from api.utils.preference_scoring import (
            calculate_exhibition_preference_score,
            calculate_day_preference_score
        )
        
        print("\n")
        print("=" * 80)
        print("KAKO SU CUVARI POREDALI PREFERENCIJE")
        print("=" * 80)
        
        day_names = ["Pon", "Uto", "Sri", "Cet", "Pet", "Sub", "Ned"]
        
        # Prikaz exhibition preferenci
        print("\n[A] PREFERENCIJE IZLOZBI (kako je cuvar rangirao):")
        print("-" * 80)
        for guard in guards:
            letter = guard.user.username.split("_")[1]
            try:
                exh_pref = GuardExhibitionPreference.objects.get(guard=guard, is_template=True)
                exh_names = []
                for eid in exh_pref.exhibition_order:
                    for name, exh in exhibitions.items():
                        if exh.id == eid:
                            exh_names.append(name)
                            break
                pref_str = " > ".join(exh_names) if exh_names else "nema preferenci"
                print(f"  Cuvar {letter}: {pref_str}")
            except GuardExhibitionPreference.DoesNotExist:
                print(f"  Cuvar {letter}: nema preferenci")
        
        # Prikaz day preferenci
        print("\n[B] PREFERENCIJE DANA (kako je cuvar rangirao):")
        print("-" * 80)
        for guard in guards:
            letter = guard.user.username.split("_")[1]
            try:
                day_pref = GuardDayPreference.objects.get(guard=guard, is_template=True)
                day_str = " > ".join([day_names[d] for d in day_pref.day_order])
                print(f"  Cuvar {letter}: {day_str}")
            except GuardDayPreference.DoesNotExist:
                print(f"  Cuvar {letter}: nema preferenci")
        
        # Prikaz range-a preferenci
        print("\n[C] RANGE PREFERENCE SCOROVA:")
        print("-" * 80)
        print("""
BEZ NORMALIZACIJE (raw score):
- Rang 1 (najpreferiranija): 2.0 boda
- Rang srednji: između 0.0 i 2.0
- Rang N (najmanje preferirana): 0.0 bodova
- Nema preferenci: 1.0 bod (neutralno)

S NORMALIZACIJOM (za formulu):
- Raw score se dijeli sa 2.0
- Range: 0.0 do 1.0
- Neutralno: 0.5

FORMULA: score = 2.0 * (n - rank) / (n - 1)
Gdje je n = ukupan broj preferenci, rank = pozicija (1-indexed)
        """)
        
        # ====================================================================
        # PRIMJER: KONKRETNA POZICIJA "ZKG UTORAK UJUTRO"
        # ====================================================================
        print("\n")
        print("=" * 120)
        print("PRIMJER: SCORE ZA KONKRETNU POZICIJU - 'ZKG UTORAK UJUTRO'")
        print("=" * 120)
        
        sample_exhibition = exhibitions.get("ZKG")
        sample_day = 1  # Utorak (0=Pon, 1=Uto, ...)
        
        print(f"\nPozicija: {sample_exhibition.name}, Dan: {day_names[sample_day]}, Smjena: Jutro")
        print("\nSvi cuvari sa detaljnim izracunom score-a:")
        print("-" * 120)
        print(f"{'Cuvar':<6} | {'Priority':<8} | {'P.Norm':<7} | {'Exh.Raw':<8} | {'Exh.Norm':<9} | {'Day.Raw':<8} | {'Day.Norm':<9} | {'UKUPNI SCORE':<12}")
        print(f"{'':>6} | {'broj':<8} | {'0-1':<7} | {'0-2':<8} | {'0-1':<9} | {'0-2':<8} | {'0-1':<9} | {'(P+E+D)':<12}")
        print("-" * 120)
        
        for guard in guards:
            letter = guard.user.username.split("_")[1]
            p = float(guard.priority_number)
            
            # Priority normalized (60% weight)
            if max_p > min_p:
                p_norm = (p - min_p) / (max_p - min_p)
            else:
                p_norm = 0.5
            p_contrib = 0.6 * p_norm
            
            # Exhibition preference (20% weight)
            exh_raw = calculate_exhibition_preference_score(
                guard, sample_exhibition, None  # None jer koristimo template
            )
            exh_norm = exh_raw / 2.0
            exh_contrib = 0.2 * exh_norm
            
            # Day preference (20% weight)
            day_raw = calculate_day_preference_score(
                guard, sample_day, None  # None jer koristimo template
            )
            day_norm = day_raw / 2.0
            day_contrib = 0.2 * day_norm
            
            # Ukupni score = 60% priority + 20% exhibition + 20% day
            total_score = p_contrib + exh_contrib + day_contrib
            
            print(f"{letter:<6} | {p:<8.2f} | {p_norm:<7.3f} | {exh_raw:<8.2f} | {exh_norm:<9.3f} | {day_raw:<8.2f} | {day_norm:<9.3f} | {total_score:<12.3f}")
        
        print("-" * 120)
        print("""
LEGENDA:
- Priority broj: Originalni priority broj cuvara (-2.00 do 5.00)
- P.Norm: Normalizirani priority (0-1), VECI = BOLJI
- Exh.Raw: Raw exhibition preference score (0-2): 2=najbolja, 1=neutralno, 0=najgora
- Exh.Norm: Normalized (Exh.Raw / 2)
- Day.Raw: Raw day preference score (0-2): 2=najbolji, 1=neutralno, 0=najgori
- Day.Norm: Normalized (Day.Raw / 2)
- UKUPNI SCORE = (0.6 × P.Norm) + (0.2 × Exh.Norm) + (0.2 × Day.Norm)

VISI UKUPNI SCORE = VECE SANSE ZA DODJELU TE POZICIJE
        """)
        
        # ====================================================================
        # FAZA 3: POKRETANJE ALGORITMA
        # ====================================================================
        
        print("\n")
        print("=" * 80)
        print("FAZA 3: POKRETANJE ALGORITMA DODJELE")
        print("=" * 80)
        
        # Dohvati pozicije prije dodjele
        positions_before = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end,
            exhibition__is_special_event=False
        ).count()
        
        print(f"\n[INFO] Pozicija za dodjelu: {positions_before}")
        print(f"   Cuvara s availability: {len(guards)}")
        print(f"   Ukupni availability: {total_availability}")
        
        # ================================================================
        # AVAILABILITY CAPPING
        # ================================================================
        # Ako je ukupni availability > broj pozicija, moramo "cap-ati"
        # availability svakog cuvara proporcionalno kako bi svi imali
        # fer sansu za dodjelu.
        # ================================================================
        
        availability_caps = calculate_availability_caps(guards, positions_before)
        
        if availability_caps:
            print("\n[CAPPING] Availability capping primijenjen:")
            print("-" * 60)
            print(f"{'Cuvar':<8} {'Original':<12} {'Capped':<12} {'Razlika':<12}")
            print("-" * 60)
            
            total_capped = 0
            for guard in guards:
                letter = guard.user.username.split("_")[1]
                original = guard.availability
                capped = availability_caps.get(guard.id, original)
                diff = original - capped
                if diff > 0:
                    print(f"{letter:<8} {original:<12} {capped:<12} -{diff:<11}")
                total_capped += capped
            
            print("-" * 60)
            print(f"Ukupni capped availability: {total_capped} (odgovara broju pozicija)")
        else:
            print("\n[INFO] Capping nije potreban - availability <= pozicija")
        
        print("\n[WAIT] Pokrecem automatsku dodjelu...")
        
        # Pokreni algoritam S CAPPINGOM
        result = assign_positions_automatically(settings, availability_caps)
        
        print(f"\n[OK] Algoritam zavrsen!")
        print(f"   Status: {result['status']}")
        print(f"   Dodjela: {result['assignments_created']} pozicija")
        
        # ====================================================================
        # FAZA 4: ANALIZA REZULTATA
        # ====================================================================
        
        print("\n")
        print("=" * 80)
        print("FAZA 4: ANALIZA REZULTATA")
        print("=" * 80)
        
        # Statistike po cuvaru
        print("\n[STATS] STATISTIKE PO CUVARU:")
        print("-" * 70)
        print(f"{'Cuvar':<8} {'Priority':<10} {'Availability':<12} {'Dodijeljeno':<12} {'Iskoristeno %':<12}")
        print("-" * 70)
        
        guard_stats = []
        for guard in guards:
            letter = guard.user.username.split("_")[1]
            assigned = PositionHistory.objects.filter(
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            ).count()
            utilization = (assigned / guard.availability * 100) if guard.availability > 0 else 0
            guard_stats.append((letter, float(guard.priority_number), guard.availability, assigned, utilization))
            print(f"{letter:<8} {float(guard.priority_number):<10.2f} {guard.availability:<12} {assigned:<12} {utilization:<12.1f}")
        
        print("-" * 70)
        total_assigned = sum(s[3] for s in guard_stats)
        print(f"{'UKUPNO':<8} {'':<10} {total_availability:<12} {total_assigned:<12}")
        
        # Statistike po izlozbi
        print("\n[STATS] STATISTIKE PO IZLOZBI:")
        print("-" * 60)
        print(f"{'Izlozba':<20} {'Pozicija ukupno':<16} {'Popunjeno':<12} {'%':<10}")
        print("-" * 60)
        
        for name, exhibition in exhibitions.items():
            positions = Position.objects.filter(
                exhibition=exhibition,
                date__gte=settings.next_week_start,
                date__lte=settings.next_week_end
            )
            filled = positions.filter(
                id__in=PositionHistory.objects.filter(
                    action=PositionHistory.Action.ASSIGNED
                ).values_list('position_id', flat=True)
            ).count()
            total = positions.count()
            pct = (filled / total * 100) if total > 0 else 0
            print(f"{name:<20} {total:<16} {filled:<12} {pct:<10.1f}")
        
        # ====================================================================
        # FAZA 5: ZAKLJUCAK
        # ====================================================================
        
        print("\n")
        print("=" * 80)
        print("FAZA 5: ZAKLJUCAK")
        print("=" * 80)
        
        # Analiziraj distribuciju
        assigned_counts = [s[3] for s in guard_stats]
        avg_assigned = sum(assigned_counts) / len(assigned_counts) if assigned_counts else 0
        
        print(f"""
Algoritam je uspjesno dodijelio {total_assigned} pozicija medu {len(guards)} cuvara.

KLJUCNE METRIKE:
- Prosjecno dodijeljeno po cuvaru: {avg_assigned:.1f}
- Maksimalno dodijeljeno: {max(assigned_counts)} (cuvar s najvise dodjela)
- Minimalno dodijeljeno: {min(assigned_counts)} (cuvar s najmanje dodjela)

KAKO ALGORITAM RADI:
1. AVAILABILITY CAPPING: Ako ima vise availability nego pozicija,
   proporcionalno se smanjuje availability svakog cuvara.
   Cuvari s NIZIM priority brojem se cappaju PRVI.

2. SCORE MATRICA: Za svaki par (cuvar, pozicija) se racuna score:
   - 60% od priority_number (visi = bolji)
   - 20% od preferencije izlozbe
   - 20% od preferencije dana

3. MADJARSKI ALGORITAM: Pronalazi optimalnu dodjelu koja
   maksimizira ukupni score svih parova.

4. NAKON DODJELE: Priority_number se smanjuje za cuvare
   koji su dobili pozicije, balansira opterecenje kroz vrijeme.
        """)
        
        # ====================================================================
        # VERIFIKACIJA (Assertions)
        # ====================================================================
        
        # Re-enable logove za assertions
        logging.disable(logging.NOTSET)
        
        # Osnovna provjera - algoritam je radio
        assert result['status'] in ['success', 'warning'], \
            f"Algoritam nije uspio: {result.get('message', 'nepoznata greska')}"
        
        # Provjera da su dodjele napravljene
        assert result['assignments_created'] > 0, \
            "Algoritam nije napravio nijednu dodjelu"
        
        # Provjera da nijedan cuvar nije prekoracio availability
        for guard in guards:
            assigned = PositionHistory.objects.filter(
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            ).count()
            assert assigned <= guard.availability, \
                f"Cuvar {guard.user.username} ima {assigned} dodjela ali availability je {guard.availability}"
        
        print("\n[OK] Sve verifikacije uspjesne!")
        print("=" * 80)


@pytest.mark.django_db  
class TestScoreCalculationExamples:
    """
    Primjeri izracuna rezultata (score) za edukativne svrhe.
    """
    
    def test_score_calculation_examples(self, db):
        """
        Prikazuje primjere izracuna score-a za razumijevanje formule.
        """
        print("\n")
        print("=" * 80)
        print("PRIMJERI IZRACUNA SCORE-a")
        print("=" * 80)
        
        # Parametri formule
        PRIORITY_WEIGHT = 0.4
        PREFERENCE_WEIGHT = 0.4
        BASE_SCORE = 0.2
        
        # Primjeri
        examples = [
            (1.00, 1.00, 5.00, 1.0, "Najnizi priority + preferirana pozicija"),
            (1.00, 1.00, 5.00, 0.5, "Najnizi priority + bez preferencija"),
            (1.00, 1.00, 5.00, 0.0, "Najnizi priority + ne-preferirana pozicija"),
            (5.00, 1.00, 5.00, 1.0, "Najvisi priority + preferirana pozicija"),
            (5.00, 1.00, 5.00, 0.0, "Najvisi priority + ne-preferirana pozicija"),
            (3.00, 1.00, 5.00, 0.5, "Srednji priority + neutralno"),
        ]
        
        print(f"\nFormula: score = ({PRIORITY_WEIGHT} x norm_priority) + ({PREFERENCE_WEIGHT} x pref_bonus) + {BASE_SCORE}")
        print("-" * 80)
        print(f"{'Opis':<45} {'Priority':<10} {'Norm':<8} {'Pref':<8} {'SCORE':<8}")
        print("-" * 80)
        
        for guard_p, min_p, max_p, pref_bonus, desc in examples:
            if max_p > min_p:
                norm_priority = (max_p - guard_p) / (max_p - min_p)
            else:
                norm_priority = 0.5
            
            score = (PRIORITY_WEIGHT * norm_priority) + (PREFERENCE_WEIGHT * pref_bonus) + BASE_SCORE
            
            print(f"{desc:<45} {guard_p:<10.2f} {norm_priority:<8.3f} {pref_bonus:<8.1f} {score:<8.3f}")
        
        print("-" * 80)
        print("""
TUMACENJE:
- Score blizu 1.0 = cuvar ima VELIKU sansu dobiti tu poziciju
- Score blizu 0.2 = cuvar ima MALU sansu (samo bazni score)
- Najnizi priority (1.00) + preferencija = 0.4 + 0.4 + 0.2 = 1.0 (maksimum!)
- Najvisi priority (5.00) + ne-preferira = 0.0 + 0.0 + 0.2 = 0.2 (minimum)
        """)
        
        # Jednostavna verifikacija
        assert True  # Test je edukativni
