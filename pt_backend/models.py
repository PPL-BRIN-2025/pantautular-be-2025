from django.db import models
import uuid
from django.contrib.auth.hashers import make_password

class User(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    last_login = models.DateTimeField(null=True, blank=True)

    def has_role(self, role_name):
        return self.role == role_name

    def update_password(self, new_password):
        self.password = make_password(new_password)
        self.save()

    def get_email_field_name(self):
        return "email"

    def get_username(self):
        return self.email    

    def __str__(self):
        return self.name

class Role(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class Permission(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.name

class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="users")

    class Meta:
        unique_together = ("user", "role")
    
class UserRoleRegistered(models.Model):

    role = models.OneToOneField(          
        Role,
        on_delete=models.CASCADE,
        related_name="registration_meta",
    )

    label = models.CharField(
        max_length=100,
        blank=True,
        help_text="Friendly name shown in the UI (defaults to role.name)",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Lower values appear earlier in dropdowns.",
    )

    class Meta:
        ordering = ("sort_order", "role__name")
        verbose_name = "registered role option"
        verbose_name_plural = "registered role options"

    def save(self, *args, **kwargs):
        if not self.label:
            self.label = self.role.name
        super().save(*args, **kwargs)

    def __str__(self) -> str:           
        return self.label

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="roles")

    class Meta:
        unique_together = ("role", "permission")

class HealthProtocol(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    url = models.URLField()

    def __str__(self):
        return self.title

class Disease(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    level_of_alertness = models.IntegerField()

    @staticmethod
    def get_disease_by_id(disease_id):
        return Disease.objects.filter(id=disease_id).first()
    
    @staticmethod
    def get_disease_cases(self):
        return self.cases.all()
    
    def __str__(self):
        return self.name

class Climate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    province = models.CharField(max_length=255)
    temperature = models.DecimalField(max_digits=8, decimal_places=2)
    precipitation = models.DecimalField(max_digits=8, decimal_places=2)
    humidity = models.DecimalField(max_digits=8, decimal_places=2)
    year = models.IntegerField()
    month = models.IntegerField()

    def __str__(self):
        return self.province
    
    @staticmethod
    def get_climate_for_location(location, year, month=None):
        query = Climate.objects.filter(province=location.province, year=year)
        if month:
            query = query.filter(month=month)
        return query

class HealthProtocolDisease(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    health_protocol = models.ForeignKey(HealthProtocol, on_delete=models.CASCADE, related_name="diseases")
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name="protocols")

    class Meta:
        unique_together = ("health_protocol", "disease")

class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    latitude = models.DecimalField(max_digits=8, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    city = models.CharField(max_length=255, unique=False)
    province = models.CharField(max_length=255, unique=False)

    @staticmethod
    def get_location_by_city(city):
        return Location.objects.filter(city=city).first()

    @staticmethod
    def get_all_locations():
        return Location.objects.all()

    def __str__(self):
        return self.city


class Case(models.Model):
    STATUS_CHOICES = [
        ("minimal", "Minimal"),
        ("biasa", "Biasa"),
        ("bahaya", "Bahaya"),
        ("katastropik", "Katastropik"),
    ]

    SEVERITY_CHOICES = [
        ("hospitalisasi", "Hospitalisasi"),
        ("insiden", "Insiden"),
        ("mortalitas", "Mortalitas"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gender = models.CharField(max_length=10)
    age = models.IntegerField()
    city = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    severity = models.CharField(max_length=255, choices=SEVERITY_CHOICES)
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name="cases")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="cases")

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="expert_uploaded_cases"
    )

    # Keep batch optional for now to avoid destructive cascades in production.
    # When ready, switch to CASCADE and make non-null via a migration.
    batch = models.ForeignKey(
        "CaseUploadBatch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    @staticmethod
    def get_all_locations():
        return Case.objects.values("id", "location__longitude", "location__latitude", "city", "location__province")
    
    def __str__(self):
        return f"Case {self.id} - {self.city}"

    class Meta:
        ordering = ("-created_at", "id")

class CaseUploadBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="case_batches"
    )
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self):
        return f"{self.filename} ({self.uploaded_by.email})"

class News(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portal = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    content = models.TextField()
    url = models.URLField()
    author = models.CharField(max_length=255)
    date_published = models.DateTimeField()
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="news")
    img_url = models.URLField(blank=True)

    def __str__(self):
        return self.title
