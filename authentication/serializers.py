from rest_framework import serializers

class SignupSerializer(serializers.Serializer):
    name     = serializers.CharField(max_length=255)
    email    = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)

class LoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)