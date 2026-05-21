from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('signin/', views.SigninView.as_view(), name='signin'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token-refresh'),

    # Password management
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('forgot-password/verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),
    path('forgot-password/resend-otp/', views.ResendOTPView.as_view(), name='resend-otp'),
    path('forgot-password/reset/', views.ResetPasswordView.as_view(), name='reset-password'),

    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),

    # Trusted contacts
    path('contacts/', views.TrustedContactListCreateView.as_view(), name='contacts'),
    path('contacts/<uuid:pk>/', views.TrustedContactDetailView.as_view(), name='contact-detail'),

    # Pets
    path('pets/', views.PetListCreateView.as_view(), name='pets'),
    path('pets/<uuid:pk>/', views.PetDetailView.as_view(), name='pet-detail'),
]
