from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Department(models.Model):
    name = models.CharField(max_length=100) # e.g., Cardiology, Orthopedics
    
    def __str__(self):
        return self.name

class Doctor(models.Model):
    # Link to Django User for specific doctor login
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    room_number = models.CharField(max_length=10)

    def __str__(self):
        return f"Dr. {self.name} ({self.department.name})"

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Consulted', 'Consulted'),
        ('Cancelled', 'Cancelled'),
    ]
    
    patient_name = models.CharField(max_length=200)
    age = models.IntegerField()
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    token_number = models.PositiveIntegerField(editable=False, null=True, blank=True)
    is_emergency = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    registration_time = models.DateTimeField(auto_now_add=True)
    estimated_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Emergency patients appear at the top of the queue, then by time
        ordering = ['-is_emergency', 'registration_time']

    def save(self, *args, **kwargs):
        if not self.token_number:
            # Logic: Generate token based on current doctor's patient count for the day
            today = timezone.now().date()
            daily_count = Appointment.objects.filter(
                doctor=self.doctor, 
                registration_time__date=today
            ).count()
            self.token_number = daily_count + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Token {self.token_number} - {self.patient_name} (Dr. {self.doctor.name})"