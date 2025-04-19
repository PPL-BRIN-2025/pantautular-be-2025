from django.core.management.base import BaseCommand
from django.db import transaction
import uuid
import random
from datetime import datetime
from pt_backend.models import Climate  # Replace 'your_app' with your actual app name

class Command(BaseCommand):
    help = 'Generates dummy climate data for Indonesian provinces from 2015-2024'

    def handle(self, *args, **kwargs):
        self.stdout.write('Generating climate data...')
        
        # List of Indonesian provinces (pre-Papua split)
        provinces = [
            "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Kepulauan Riau", 
            "Jambi", "Sumatera Selatan", "Bangka Belitung", "Bengkulu", "Lampung",
            "Banten", "DKI Jakarta", "Jawa Barat", "Jawa Tengah", "DI Yogyakarta",
            "Jawa Timur", "Bali", "Nusa Tenggara Barat", "Nusa Tenggara Timur",
            "Kalimantan Barat", "Kalimantan Tengah", "Kalimantan Selatan", 
            "Kalimantan Timur", "Kalimantan Utara", "Sulawesi Utara", 
            "Gorontalo", "Sulawesi Tengah", "Sulawesi Barat", "Sulawesi Selatan",
            "Sulawesi Tenggara", "Maluku", "Maluku Utara", "Papua", "Papua Barat"
        ]
        
        # Climate characteristics by region (generalized)
        climate_regions = {
            "Western": {  # Sumatra, Java, Bali
                "temp_base": 27.5, "temp_var": 1.5,
                "humidity_base": 78, "humidity_var": 5,
                "precipitation_base": 250, "precipitation_var": 100
            },
            "Northern": {  # North Kalimantan, North Sulawesi
                "temp_base": 27.0, "temp_var": 1.0,
                "humidity_base": 80, "humidity_var": 5,
                "precipitation_base": 230, "precipitation_var": 90
            },
            "Central": {  # Central Kalimantan, Central Sulawesi
                "temp_base": 27.2, "temp_var": 1.2,
                "humidity_base": 82, "humidity_var": 4,
                "precipitation_base": 260, "precipitation_var": 100
            },
            "Eastern": {  # Maluku, Papua
                "temp_base": 26.5, "temp_var": 1.0,
                "humidity_base": 83, "humidity_var": 4,
                "precipitation_base": 280, "precipitation_var": 110
            },
            "Southern": {  # NTT, NTB, Southern regions
                "temp_base": 28.0, "temp_var": 1.5,
                "humidity_base": 75, "humidity_var": 6,
                "precipitation_base": 200, "precipitation_var": 80
            }
        }
        
        # Map provinces to climate regions
        province_to_region = {
            "Aceh": "Western", "Sumatera Utara": "Western", "Sumatera Barat": "Western",
            "Riau": "Western", "Kepulauan Riau": "Western", "Jambi": "Western",
            "Sumatera Selatan": "Western", "Bangka Belitung": "Western", "Bengkulu": "Western",
            "Lampung": "Western", "Banten": "Western", "DKI Jakarta": "Western",
            "Jawa Barat": "Western", "Jawa Tengah": "Western", "DI Yogyakarta": "Western",
            "Jawa Timur": "Western", "Bali": "Western",
            "Nusa Tenggara Barat": "Southern", "Nusa Tenggara Timur": "Southern",
            "Kalimantan Barat": "Western", "Kalimantan Tengah": "Central",
            "Kalimantan Selatan": "Southern", "Kalimantan Timur": "Central",
            "Kalimantan Utara": "Northern", "Sulawesi Utara": "Northern",
            "Gorontalo": "Northern", "Sulawesi Tengah": "Central",
            "Sulawesi Barat": "Central", "Sulawesi Selatan": "Southern",
            "Sulawesi Tenggara": "Southern", "Maluku": "Eastern",
            "Maluku Utara": "Eastern", "Papua": "Eastern", "Papua Barat": "Eastern"
        }
        
        # Seasonal variations - Indonesia generally has wet (Oct-Mar) and dry (Apr-Sep) seasons
        seasonal_factors = {
            1: {"temp": -0.5, "humidity": 10, "precip": 1.7},  # January - peak wet season
            2: {"temp": -0.3, "humidity": 8, "precip": 1.5},
            3: {"temp": 0.0, "humidity": 5, "precip": 1.3},
            4: {"temp": 0.3, "humidity": 0, "precip": 1.0},
            5: {"temp": 0.5, "humidity": -3, "precip": 0.7},
            6: {"temp": 0.8, "humidity": -5, "precip": 0.5},  # June - peak dry season
            7: {"temp": 0.5, "humidity": -5, "precip": 0.4},
            8: {"temp": 0.3, "humidity": -3, "precip": 0.5},
            9: {"temp": 0.0, "humidity": 0, "precip": 0.7},
            10: {"temp": -0.2, "humidity": 3, "precip": 1.0},
            11: {"temp": -0.3, "humidity": 6, "precip": 1.3},
            12: {"temp": -0.5, "humidity": 9, "precip": 1.5}  # December - wet season again
        }
        
        # Climate change factor - slight warming trend over years
        climate_change_factor = lambda year: (year - 2015) * 0.03  # ~ 0.03°C increase per year
        
        # El Niño and La Niña years (simplified)
        el_nino_years = [2015, 2016, 2019, 2023]  # Hotter, drier
        la_nina_years = [2017, 2020, 2021, 2022]  # Cooler, wetter
        
        # Batch create records for better performance
        climate_data_records = []

        # Generate data for all provinces, all months, all years
        for province in provinces:
            region = province_to_region[province]
            region_data = climate_regions[region]
            
            for year in range(2015, 2025):
                for month in range(1, 13):
                    # Base climate values for this region
                    temp_base = region_data["temp_base"]
                    humidity_base = region_data["humidity_base"]
                    precip_base = region_data["precipitation_base"]
                    
                    # Apply seasonal variations
                    season = seasonal_factors[month]
                    temp = temp_base + season["temp"]
                    humidity = humidity_base + season["humidity"]
                    precipitation = precip_base * season["precip"]
                    
                    # Apply climate change trend
                    temp += climate_change_factor(year)
                    
                    # Apply El Niño/La Niña effects
                    if year in el_nino_years:
                        temp += 0.5
                        humidity -= 5
                        precipitation *= 0.8
                    elif year in la_nina_years:
                        temp -= 0.3
                        humidity += 3
                        precipitation *= 1.2
                    
                    # Add small random variations
                    temp += random.uniform(-region_data["temp_var"], region_data["temp_var"])
                    humidity += random.uniform(-region_data["humidity_var"], region_data["humidity_var"])
                    precipitation += random.uniform(-region_data["precipitation_var"], region_data["precipitation_var"])
                    
                    # Ensure values are within reasonable ranges
                    temp = round(max(20, min(35, temp)), 1)
                    humidity = round(max(60, min(95, humidity)), 1)
                    precipitation = round(max(10, precipitation), 1)
                    
                    # Create climate data record
                    climate_data_records.append(
                        Climate(
                            id=uuid.uuid4(),
                            province=province,
                            year=year,
                            month=month,
                            temperature=temp,
                            humidity=humidity,
                            precipitation=precipitation
                        )
                    )
                    
                    # Create in batches of 100 to avoid memory issues
                    if len(climate_data_records) >= 100:
                        with transaction.atomic():
                            Climate.objects.bulk_create(climate_data_records)
                        climate_data_records = []
                        
        # Create any remaining records
        if climate_data_records:
            with transaction.atomic():
                Climate.objects.bulk_create(climate_data_records)
                
        self.stdout.write(self.style.SUCCESS(f'Successfully generated climate data for {len(provinces)} provinces over 10 years'))


# Sample usage to inspect generated data:
def sample_data():
    """View sample of generated data"""
    # Get sample data for Jakarta in 2020
    jakarta_2020 = Climate.objects.filter(province="DKI Jakarta", year=2020).order_by('month')
    
    print("Sample climate data for Jakarta in 2020:")
    for record in jakarta_2020:
        print(f"Month: {record.month}, Temp: {record.temperature}°C, " 
              f"Humidity: {record.humidity}%, Precipitation: {record.precipitation}mm")
              
    # Compare wet vs dry season across provinces in 2023
    print("\nComparing January (wet) vs July (dry) 2023 across provinces:")
    wet_season = Climate.objects.filter(year=2023, month=1)
    dry_season = Climate.objects.filter(year=2023, month=7)
    
    wet_avg_precip = sum(w.precipitation for w in wet_season) / wet_season.count()
    dry_avg_precip = sum(d.precipitation for d in dry_season) / dry_season.count()
    
    print(f"Average precipitation in January 2023: {wet_avg_precip:.1f}mm")
    print(f"Average precipitation in July 2023: {dry_avg_precip:.1f}mm")