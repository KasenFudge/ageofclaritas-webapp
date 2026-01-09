from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

# Create your models here.
class Profile(models.Model):
    # Relation to the Django User class to use Django built in User functionality
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Information on the users birthday for calculating age.
    date_of_birth = models.DateField()
    
    # Users age as of a given date, calculated when called.
    @property
    def age_on(self, on_date: date) -> int | None:
        if not self.date_of_birth:
            return None
        
        dob = self.date_of_birth
        years = on_date.year - dob.year
        if (on_date.month, on_date.day) < (dob.month, dob.day): # Subtract 1 if birthday hasn't happened yet this year
            years -= 1
        return years
    
    @property
    def age(self) -> int | None:
        return self.age_on(timezone.localdate())
    
    # Minor status, calculated when called based off of the users age.
    @property
    def is_minor(self) -> bool | None:
        if not self.age:
            return None
        age = self.age
        if age >= 18:
            return False
        else:
            return True
    
    # A registered parent account that can sign up younger players for events. Parent account must be an adult.
    parent_account = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='child_accounts')

    def has_signed_active_waiver(self):
        waiver = Waiver.objects.filter(is_active=True).first()
        if not waiver: # No Active Waiver Found
            return False
        return WaiverSignature.objects.filter(user=self, waiver=waiver).exists()
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    # Later on will have stuff for characters here, will probably create a whole seperate app for them down the
    # line because it will get complicated. A foreign key relation.
    # Other than that, this is really all Profile needs, Django User takes care of everything else.

class Waiver(models.Model):
    title = models.CharField(max_length=50)
    effective_date = models.DateField(auto_now_add=True, help_text="Will update automatically when the waiver is created or updated.")
    content = models.TextField()
    is_active = models.BooleanField(default=True, help_text="Only one waiver should be active at a time.")

    class Meta:
        ordering = ['-effective_date']

    def save(self, *args, **kwargs):
        if self.is_active:
            Waiver.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} {self.effective_date.year}"

class WaiverSignature(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    waiver = models.ForeignKey(Waiver, on_delete=models.CASCADE)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'waiver')

