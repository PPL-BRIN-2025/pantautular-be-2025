from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

class SignupSerializer(serializers.Serializer):
    name     = serializers.CharField(max_length=255)
    email    = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Password confirmation does not match."})
        
        # Validasi kekuatan password menggunakan validator Django
        validate_password(data['new_password'], self.context['user'])
        return data
