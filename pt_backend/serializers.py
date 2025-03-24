from rest_framework import serializers

class CaseLocationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    location__longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    location__latitude = serializers.DecimalField(max_digits=8, decimal_places=6)
    city = serializers.CharField(max_length=255)

class GenderDistributionSerializer(serializers.Serializer):
    male = serializers.IntegerField()
    female = serializers.IntegerField()

class PortalStatisticsSerializer(serializers.Serializer):
    portal = serializers.CharField()
    news_count = serializers.IntegerField()
    disease_count = serializers.IntegerField()