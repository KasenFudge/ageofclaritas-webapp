from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    birthday = models.DateField(null=True, blank=True)
    is_new_player = models.BooleanField(default=True)
    parent_account = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='child_accounts')
    is_minor = models.BooleanField(default=False)

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