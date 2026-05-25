from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import admin
from django.utils import timezone
from datetime import date

# Create your models here.
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    date_of_birth = models.DateField()

    is_student = models.BooleanField(default=False)
    student_status_expires = models.DateField(null=True, blank=True)

    @property
    def has_valid_student_discount(self):
        """
        Dynamically checks if the user is a student. If their expiration
        date has passed, it automatically updates the database to reset their status.
        """
        if not self.is_student:
            return False
        
        if self.student_status_expires:
            # Check if today's date has passed the expiration date
            if timezone.now().date() > self.student_status_expires:
                # The status has expired! Turn off the flags and save to the database
                self.is_student = False
                self.student_status_expires = None
                self.save(update_fields=['is_student', 'student_status_expires'])
                return False
                
        # If they are a student and either have no expiration date or haven't reached it yet
        return True

    # A registered parent account that can manage, register, and purchase event tickets for child accounts.
    parent_account = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_accounts',
        help_text=(
            "Links this profile to a primary adult guardian account. "
            "Enables unified family checkouts and minor event registration management."
        )
    )

    REQUIRED_FIELDS = ['email', 'date_of_birth']
    
    # Users age as of a given date, calculated when called.
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

    def has_signed_active_waiver(self):
        waiver = Waiver.objects.filter(is_active=True).first()
        if not waiver: # No Active Waiver Found
            return False
        return WaiverSignature.objects.filter(user=self, waiver=waiver).exists()
    
    def __str__(self):
        return f"{self.get_full_name() or self.username}"
    
    def clean(self):
        """
        Validates model integrity constraints before database serialization.
        """
        super().clean()
        
        if self.parent_account:
            # 1. Prevent a user from assigning themselves as their own parent
            if self.parent_account_id == self.id:
                raise ValidationError({
                    "parent_account": "An account cannot be assigned as its own parent profile."
                })
                
            # 2. Enforce that the target parent account must be an adult (18+) as of today
            today = timezone.localdate()
            parent_age = self.parent_account.age_on(today)
            
            if parent_age < 18:
                raise ValidationError({
                    "parent_account": f"The selected parent account belongs to a minor ({parent_age} years old). Parent accounts must be an adult (18+)."
                })

    def save(self, *args, **kwargs):
        """
        Overrides the save method to force clean validation check before writing to the DB.
        """
        self.full_clean()  # Forces the clean() rules above to execute on .save() calls
        super().save(*args, **kwargs)

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

