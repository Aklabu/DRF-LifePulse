import random
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from utils.response import CustomResponse
from .models import User, SafetyInfo, TrustedContact, Pet, OTPVerification, BlacklistedToken
from .services import send_otp_email
from .serializers import (
    SignupSerializer, SigninSerializer, LogoutSerializer, TokenRefreshSerializer,
    ChangePasswordSerializer, ForgotPasswordSerializer, VerifyOTPSerializer,
    ResendOTPSerializer, ResetPasswordSerializer, ProfileUpdateSerializer,
    UserProfileSerializer, TrustedContactSerializer, PetSerializer,
)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# Registers a new user with safety info, trusted contacts, and optional pets
class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        data = serializer.validated_data

        # Atomic transaction ensures partial failures don't leave orphaned records
        with transaction.atomic():
            user = User.objects.create_user(
                email=data['email'],
                password=data['password'],
                name=data['name'],
                phone_number=data['phone_number'],
            )
            user.is_logged_in = True
            user.save(update_fields=['is_logged_in'])
            SafetyInfo.objects.create(user=user, **data['safety_info'])
            for contact_data in data['trusted_contacts']:
                TrustedContact.objects.create(user=user, **contact_data)
            for pet_data in data.get('pets', []):
                Pet.objects.create(user=user, **pet_data)

        tokens = get_tokens_for_user(user)
        profile = UserProfileSerializer(user, context={'request': request}).data

        return CustomResponse.success(
            message='Account created successfully.',
            data={**tokens, 'user': profile},
            status_code=201,
        )


# Authenticates a user and returns JWT tokens
class SigninView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SigninSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Invalid credentials.',
                status_code=400,
                errors=serializer.errors,
            )

        user = serializer.validated_data['user']
        user.is_logged_in = True
        user.save(update_fields=['is_logged_in'])
        tokens = get_tokens_for_user(user)
        profile = UserProfileSerializer(user, context={'request': request}).data

        return CustomResponse.success(
            message='Signed in successfully.',
            data={**tokens, 'user': profile},
        )


# Blacklists the refresh token to invalidate the session
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Refresh token is required.',
                status_code=400,
                errors=serializer.errors,
            )

        BlacklistedToken.objects.create(token=serializer.validated_data['refresh_token'])
        request.user.is_logged_in = False
        request.user.save(update_fields=['is_logged_in'])
        return CustomResponse.success(message='Logged out successfully.')


# Issues a new access token from a valid, non-blacklisted refresh token
class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Refresh token is required.',
                status_code=400,
                errors=serializer.errors,
            )

        token_str = serializer.validated_data['refresh_token']

        if BlacklistedToken.objects.filter(token=token_str).exists():
            return CustomResponse.error(message='Token has been invalidated.', status_code=401)

        try:
            refresh = RefreshToken(token_str)
            access_token = str(refresh.access_token)
        except TokenError:
            return CustomResponse.error(
                message='Invalid or expired refresh token.',
                status_code=401,
            )

        return CustomResponse.success(
            message='Token refreshed successfully.',
            data={'access': access_token},
        )


# Allows an authenticated user to change their password
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        user = request.user
        data = serializer.validated_data

        if not user.check_password(data['old_password']):
            return CustomResponse.error(message='Old password is incorrect.', status_code=400)

        user.set_password(data['new_password'])
        user.save()

        return CustomResponse.success(message='Password changed successfully.')


# Sends an OTP to the email if the account exists (response is always the same to prevent enumeration)
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        email = serializer.validated_data['email']

        if User.objects.filter(email=email).exists():
            OTPVerification.objects.filter(email=email).delete()
            otp = str(random.randint(1000, 9999))
            OTPVerification.objects.create(
                email=email,
                otp=otp,
                expires_at=timezone.now() + timezone.timedelta(minutes=5),
            )
            send_otp_email(email, otp)

        # Always return success to avoid revealing whether the email is registered
        return CustomResponse.success(
            message='If an account with that email exists, an OTP has been sent.'
        )


# Verifies the submitted OTP and marks it as verified for the reset step
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        record = OTPVerification.objects.filter(email=email).order_by('-created_at').first()

        if not record:
            return CustomResponse.error(message='No OTP found for this email.', status_code=400)
        if record.is_expired():
            return CustomResponse.error(message='OTP has expired.', status_code=400)
        if record.otp != otp:
            return CustomResponse.error(message='Invalid OTP.', status_code=400)

        record.is_verified = True
        record.save()

        return CustomResponse.success(message='OTP verified successfully.')


# Replaces the existing OTP with a fresh one and resends it
class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        email = serializer.validated_data['email']

        if User.objects.filter(email=email).exists():
            OTPVerification.objects.filter(email=email).delete()
            otp = str(random.randint(1000, 9999))
            OTPVerification.objects.create(
                email=email,
                otp=otp,
                expires_at=timezone.now() + timezone.timedelta(minutes=5),
            )
            send_otp_email(email, otp)

        return CustomResponse.success(message='If an account exists, a new OTP has been sent.')


# Resets the password after confirming a verified OTP exists
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        data = serializer.validated_data
        email = data['email']

        # Require a verified OTP before allowing the password change
        record = OTPVerification.objects.filter(email=email, is_verified=True).order_by('-created_at').first()

        if not record:
            return CustomResponse.error(
                message='OTP verification required before resetting password.',
                status_code=400,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return CustomResponse.error(message='User not found.', status_code=404)

        user.set_password(data['new_password'])
        user.save()
        record.delete()  # Prevent OTP reuse

        return CustomResponse.success(message='Password reset successfully.')


# Retrieves or partially updates the authenticated user's profile
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return CustomResponse.success(
            message='Profile retrieved successfully.',
            data=serializer.data,
        )

    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        data = serializer.validated_data
        user = request.user

        if 'name' in data:
            user.name = data['name']
        if 'phone_number' in data:
            user.phone_number = data['phone_number']
        user.save()

        if 'safety_info' in data:
            SafetyInfo.objects.filter(user=user).update(**data['safety_info'])

        profile = UserProfileSerializer(user, context={'request': request}).data
        return CustomResponse.success(
            message='Profile updated successfully.',
            data=profile,
        )


# Lists trusted contacts or adds a new one (max 5)
class TrustedContactListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contacts = TrustedContact.objects.filter(user=request.user)
        serializer = TrustedContactSerializer(contacts, many=True)
        return CustomResponse.success(
            message='Contacts retrieved successfully.',
            data=serializer.data,
        )

    def post(self, request):
        if request.user.trusted_contacts.count() >= 5:
            return CustomResponse.error(
                message='Maximum 5 trusted contacts allowed.',
                status_code=400,
            )

        serializer = TrustedContactSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        serializer.save(user=request.user)
        return CustomResponse.success(
            message='Contact added successfully.',
            data=serializer.data,
            status_code=201,
        )


# Updates or deletes a single trusted contact (cannot delete the last one)
class TrustedContactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return TrustedContact.objects.get(pk=pk, user=user)
        except TrustedContact.DoesNotExist:
            return None

    def patch(self, request, pk):
        contact = self.get_object(pk, request.user)
        if not contact:
            return CustomResponse.error(message='Contact not found.', status_code=404)

        serializer = TrustedContactSerializer(contact, data=request.data, partial=True)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        serializer.save()
        return CustomResponse.success(
            message='Contact updated successfully.',
            data=serializer.data,
        )

    def delete(self, request, pk):
        contact = self.get_object(pk, request.user)
        if not contact:
            return CustomResponse.error(message='Contact not found.', status_code=404)

        if request.user.trusted_contacts.count() <= 1:
            return CustomResponse.error(
                message='Cannot delete the last trusted contact. Minimum 1 required.',
                status_code=400,
            )

        contact.delete()
        return CustomResponse.success(message='Contact deleted successfully.')


# Lists pets or registers a new one (max 5)
class PetListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pets = Pet.objects.filter(user=request.user)
        serializer = PetSerializer(pets, many=True, context={'request': request})
        return CustomResponse.success(
            message='Pets retrieved successfully.',
            data=serializer.data,
        )

    def post(self, request):
        if request.user.pets.count() >= 5:
            return CustomResponse.error(
                message='Maximum 5 pets allowed.',
                status_code=400,
            )

        serializer = PetSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        serializer.save(user=request.user)
        return CustomResponse.success(
            message='Pet added successfully.',
            data=serializer.data,
            status_code=201,
        )


# Updates or deletes a single pet record
class PetDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Pet.objects.get(pk=pk, user=user)
        except Pet.DoesNotExist:
            return None

    def patch(self, request, pk):
        pet = self.get_object(pk, request.user)
        if not pet:
            return CustomResponse.error(message='Pet not found.', status_code=404)

        serializer = PetSerializer(
            pet,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        serializer.save()
        return CustomResponse.success(
            message='Pet updated successfully.',
            data=serializer.data,
        )

    def delete(self, request, pk):
        pet = self.get_object(pk, request.user)
        if not pet:
            return CustomResponse.error(message='Pet not found.', status_code=404)

        pet.delete()
        return CustomResponse.success(message='Pet deleted successfully.')
