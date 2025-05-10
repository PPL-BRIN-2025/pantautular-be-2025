from rest_framework import serializers

class CaseLocationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    location__longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    location__latitude = serializers.DecimalField(max_digits=8, decimal_places=6)
    
    city = serializers.CharField(max_length=255)
    location__province = serializers.CharField(max_length=255)

class PrevalenceSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    total_cases = serializers.IntegerField()
    population = serializers.IntegerField()
    prevalence = serializers.FloatField()

class MonthlyCountSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    count = serializers.IntegerField()

class SeverityCountSerializer(serializers.Serializer):
    def to_representation(self, obj):
        result = {}
        for severity_key, month_data in obj.items():
            result[severity_key] = MonthlyCountSerializer(month_data, many=True).data
        return result

class PortalStatisticsSerializer(serializers.Serializer):
    portal = serializers.CharField()
    news_count = serializers.IntegerField()
    disease_count = serializers.IntegerField()

class TopPortalSerializer(serializers.Serializer):
    portal = serializers.CharField()
    count = serializers.IntegerField()
    
class SeverityCountsSerializer(serializers.Serializer):
    hospitalisasi = serializers.IntegerField()
    insiden = serializers.IntegerField()
    mortalitas = serializers.IntegerField()

class DiseaseSeverityStatsSerializer(serializers.Serializer):
    name = serializers.CharField()
    severity_counts = SeverityCountsSerializer()
    total_cases = serializers.IntegerField()

class LocationSeverityStatsSerializer(serializers.Serializer):
    name = serializers.CharField()
    severity_counts = SeverityCountsSerializer()
    total_cases = serializers.IntegerField()

# Map of Indonesian province names to ISO 3166-2 codes
PROVINCE_TO_CODE = {
    'Aceh': 'ID-AC',
    'Bali': 'ID-BA',
    'Bangka Belitung': 'ID-BB',
    'Banten': 'ID-BT',
    'Bengkulu': 'ID-BE',
    'DI Yogyakarta': 'ID-YO',
    'DKI Jakarta': 'ID-JK',
    'Gorontalo': 'ID-GO',
    'Jambi': 'ID-JA',
    'Jawa Barat': 'ID-JB',
    'Jawa Tengah': 'ID-JT',
    'Jawa Timur': 'ID-JI',
    'Kalimantan Barat': 'ID-KB',
    'Kalimantan Selatan': 'ID-KS',
    'Kalimantan Tengah': 'ID-KT',
    'Kalimantan Timur': 'ID-KI',
    'Kalimantan Utara': 'ID-KU',
    'Kepulauan Riau': 'ID-KR',
    'Lampung': 'ID-LA',
    'Maluku': 'ID-MA',
    'Maluku Utara': 'ID-MU',
    'Nusa Tenggara Barat': 'ID-NB',
    'Nusa Tenggara Timur': 'ID-NT',
    'Papua': 'ID-PA',
    'Papua Barat': 'ID-PB',
    'Riau': 'ID-RI',
    'Sulawesi Barat': 'ID-SR',
    'Sulawesi Selatan': 'ID-SN',
    'Sulawesi Tengah': 'ID-ST',
    'Sulawesi Tenggara': 'ID-SG',
    'Sulawesi Utara': 'ID-SA',
    'Sumatera Barat': 'ID-SB',
    'Sumatera Selatan': 'ID-SS',
    'Sumatera Utara': 'ID-SU'
}

class ProvinceClimateSerializer(serializers.Serializer):
    province = serializers.CharField()
    value = serializers.DecimalField(max_digits=8, decimal_places=2)
    
    def to_representation(self, instance):
        return {
            'id': PROVINCE_TO_CODE.get(instance['province'], instance['province']),
            'value': float(instance['value'])
        }


