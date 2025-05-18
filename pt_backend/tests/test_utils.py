import uuid
import random
from pt_backend.models import Disease, Location, Case

# Test data constants
PROVINCE_NAMES = [
    "DKI Jakarta", "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Sumatera Utara",
    "Sumatera Selatan", "Sulawesi Selatan", "Kalimantan Timur", "Bali", "Aceh",
    "Riau", "Lampung", "Banten", "DIY Yogyakarta", "Nusa Tenggara Barat"
]

CITY_PATTERNS = [
    "Kota {}", "Kabupaten {}", "{} Utara", "{} Selatan", "{} Timur", "{} Barat"
]

CITY_NAMES = [
    "Jakarta", "Bandung", "Surabaya", "Medan", "Makassar", "Semarang",
    "Palembang", "Tangerang", "Depok", "Padang", "Bekasi", "Malang",
    "Yogyakarta", "Bogor", "Solo", "Denpasar", "Balikpapan", "Manado",
    "Pontianak", "Banjarmasin", "Cirebon", "Samarinda", "Jambi", "Jayapura"
]

STATUSES = ["minimal", "biasa", "bahaya", "katastropik"]
SEVERITIES = ["hospitalisasi", "insiden", "mortalitas"]
SEVERITY_WEIGHTS = [0.6, 0.3, 0.1]  # hospitalisasi more common, mortalitas less common
GENDERS = ["male", "female"]


def create_test_disease():
    """Create and return a test disease"""
    return Disease.objects.create(
        id=uuid.uuid4(),
        name=f"Test Disease {uuid.uuid4().hex[:8]}",
        level_of_alertness=random.randint(1, 5)
    )


def generate_city_name(index):
    """Generate a city name based on index"""
    if index < len(CITY_NAMES):
        city_pattern = random.choice(CITY_PATTERNS)
        city_base = CITY_NAMES[index]
        return city_pattern.format(city_base)
    return f"City {uuid.uuid4().hex[:6]}" # pragma: no cover


def create_location(city_name, province_name):
    """Create and return a location"""
    # Indonesia roughly spans -11 to 6 latitude, 95 to 141 longitude
    latitude = random.uniform(-10, 6)
    longitude = random.uniform(95, 140)

    return Location.objects.create(
        id=uuid.uuid4(),
        city=city_name,
        province=province_name,
        latitude=latitude,
        longitude=longitude
    )


def create_cases_for_location(location, count, disease):
    """Create cases for a location and return them"""
    cases = []
    for _ in range(count):
        case = Case.objects.create(
            id=uuid.uuid4(),
            gender=random.choice(GENDERS),
            age=random.randint(1, 90),
            city=location.city,
            status=random.choice(STATUSES),
            severity=random.choices(
                SEVERITIES, 
                weights=SEVERITY_WEIGHTS,
                k=1
            )[0],
            disease=disease,
            location=location
        )
        cases.append(case)
    return cases


def generate_test_data(
    num_provinces=5, 
    cities_per_province=3, 
    cases_per_city=10, 
    disease=None
):
    """
    Generate test locations and cases for severity testing
    
    Args:
        num_provinces: Number of provinces to create
        cities_per_province: Number of cities to create per province
        cases_per_city: Number of cases to create per city
        disease: Disease instance to use (will create one if None)
    
    Returns:
        tuple: (test_disease, locations_dict, cases_list)
    """
    # Create a disease if not provided
    if not disease:
        disease = create_test_disease()

    # Select provinces to use
    selected_provinces = random.sample(PROVINCE_NAMES, min(num_provinces, len(PROVINCE_NAMES)))

    locations = {}
    all_cases = []

    # Create locations and cases for each province
    for province in selected_provinces:
        locations[province] = []

        # Generate cities for this province
        for i in range(cities_per_province):
            city_name = generate_city_name(i)
            location = create_location(city_name, province)

            # Store location
            locations[province].append(location)

            # Create and store cases
            cases = create_cases_for_location(location, cases_per_city, disease)
            all_cases.extend(cases)

    return disease, locations, all_cases