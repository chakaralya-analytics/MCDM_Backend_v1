# users/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('phone_number',)

class LoginSerializer(serializers.Serializer):
    """Serializer for login requests (username/email + password only)"""
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=128, write_only=True)

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    # ✅ Make phone_number required
    phone_number = serializers.CharField(max_length=15, required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'phone_number')
        
    def validate_email(self, value):
        """
        Ensure email is unique
        """
        user_id = self.instance.id if self.instance else None
        if User.objects.exclude(id=user_id).filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
        
    def validate_username(self, value):
        """
        Ensure username is unique
        """
        user_id = self.instance.id if self.instance else None
        if User.objects.exclude(id=user_id).filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value
    
    def validate_phone_number(self, value):
        """
        Basic phone number validation
        """
        if not value:
            raise serializers.ValidationError("Phone number is required.")
        
        if not all(c.isdigit() or c in '+-() ' for c in value):
            raise serializers.ValidationError("Phone number can only contain digits, +, -, (, ), and spaces.")
        return value

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        
        # Refresh to ensure profile was created by signal
        user.refresh_from_db()
        
        # Update phone number on the profile
        if hasattr(user, 'profile'):
            user.profile.phone_number = phone_number
            user.profile.save()
        else:
            # Fallback: create profile if it doesn't exist
            from .models import UserProfile
            UserProfile.objects.create(user=user, phone_number=phone_number)
            
        return user
        
    def update(self, instance, validated_data):
        phone_number = validated_data.pop('phone_number', None)
        
        # Update user fields
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])
        instance.save()
        
        # Update phone number
        if phone_number is not None:
            instance.profile.phone_number = phone_number
            instance.profile.save()
            
        return instance