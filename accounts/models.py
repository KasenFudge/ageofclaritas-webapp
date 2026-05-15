from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.contrib import admin
from django.utils import timezone
from datetime import date

# Create your models here.
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    date_of_birth = models.DateField()

    # A registered parent account that can sign up younger players for events. Parent account must be an adult.
    parent_account = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_accounts'
    )
    
    # Users age as of a given date, calculated when called.
    @property
    def age_on(self, on_date: date) -> int | None:
        if not self.date_of_birth:
            return None
        
        dob = self.date_of_birth
        years = on_date.year - dob.year

        # Subtract 1 if birthday hasn't happened yet this year
        if (on_date.month, on_date.day) < (dob.month, dob.day):
            years -= 1
        
        return years
    
    @property
    @admin.display(description='Age', ordering='date_of_birth')
    def age(self):
        return self.age_on(timezone.localdate())
    
    # Minor status, calculated when called based off of the users age.
    @property
    @admin.display(description='Minor Status', boolean=True)
    def is_minor(self) -> bool | None:
        age = self.age

        if age is None:
            return None
        
        return age < 18

    def has_signed_active_waiver(self):
        waiver = Waiver.objects.filter(is_active=True).first()
        if not waiver: # No Active Waiver Found
            return False
        return WaiverSignature.objects.filter(user=self, waiver=waiver).exists()
    
    def __str__(self):
        return f"{self.get_full_name() or self.username}"

    # Later on will have stuff for characters here, will probably create a whole seperate app for them down the
    # line because it will get complicated. A foreign key relation.

class Waiver(models.Model):
    title = models.CharField(max_length=50)
    effective_date = models.DateField(auto_now_add=True)
    content = models.TextField()
    is_active = models.BooleanField(
        default=True,
        help_text="Only one waiver should be active at a time."
    )

    class Meta:
        ordering = ['-effective_date']

    def save(self, *args, **kwargs):
        # If this waiver is being set to active, deactivate all other waivers.
        if self.is_active:
            Waiver.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} {self.effective_date.year}"

class WaiverSignature(models.Model):
    # This now points directly to your CustomUser
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='waiver_signatures'
    )
    waiver = models.ForeignKey(
        Waiver, 
        on_delete=models.CASCADE, 
        related_name='signatures'
    )
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents a user from signing the same version of a waiver twice
        unique_together = ('user', 'waiver')

    def __str__(self):
        return f"{self.user.username} signed {self.waiver.title}"

