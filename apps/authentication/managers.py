from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin
)
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None,**kwargs):

        if phone is None:
            raise TypeError('Users must have an phone.')

        user = self.model(email=phone,**kwargs)
        user.set_password("123")
        user.save()

        return user

    def create_superuser(self, phone, password):
        """
        Create and return a `User` with superuser (admin) permissions.
        """
        # if password is None:
        #     raise TypeError('Superusers must have a password.')

        # user = self.create_user(phone, password, last_name='User')
        # user.is_superuser = True
        # user.is_staff = True
        # user.is_active = True
        # user.save()

        # return user

        if not phone:
            raise ValueError('Users must have an phone.')

        user = self.model(
            first_name='Super',
            last_name='User',
            phone=phone,
            is_staff=True,
            is_superuser=True,

        )

        user.set_password(password)
        user.is_active = True
        user.save(using=self._db)
        return user


