from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone

from .models import User, SafetyInfo, TrustedContact, Pet, OTPVerification, BlacklistedToken


class SafetyInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyInfo
        exclude = ['id', 'user', 'created_at', 'updated_at']


class TrustedContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrustedContact
        exclude = ['user']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pet
        exclude = ['user']
        read_only_fields = ['id', 'created_at', 'updated_at']


# Read-only; returns the full user profile with nested safety info, contacts, and pets
class UserProfileSerializer(serializers.ModelSerializer):
    safety_info = SafetyInfoSerializer(read_only=True)
    trusted_contacts = TrustedContactSerializer(many=True, read_only=True)
    pets = PetSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'phone_number', 'created_at', 'updated_at',
                  'safety_info', 'trusted_contacts', 'pets']
        read_only_fields = fields


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=4, write_only=True)
    safety_info = SafetyInfoSerializer()
    trusted_contacts = TrustedContactSerializer(many=True)
    pets = PetSerializer(many=True, required=False, default=list)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError('A user with this phone number already exists.')
        return value

    def validate_trusted_contacts(self, value):
        if len(value) < 1:
            raise serializers.ValidationError('At least 1 trusted contact is required.')
        if len(value) > 5:
            raise serializers.ValidationError('Maximum 5 trusted contacts allowed.')
        return value

    def validate_pets(self, value):
        if len(value) > 5:
            raise serializers.ValidationError('Maximum 5 pets allowed.')
        return value


class SigninSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        # Generic error message to avoid revealing whether the email exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password.')

        if not user.check_password(password):
            raise serializers.ValidationError('Invalid email or password.')

        if not user.is_active:
            raise serializers.ValidationError('This account is inactive.')

        data['user'] = user
        return data


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class TokenRefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=4, write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError('New passwords do not match.')
        if data['old_password'] == data['new_password']:
            raise serializers.ValidationError('New password must differ from the old password.')
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=4, min_length=4)


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(min_length=4, write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError('Passwords do not match.')
        return data


class ProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    phone_number = serializers.CharField(max_length=20, required=False)
    safety_info = SafetyInfoSerializer(required=False)

    def validate_phone_number(self, value):
        user = self.context['request'].user
        if User.objects.filter(phone_number=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError('This phone number is already in use.')
        return value
