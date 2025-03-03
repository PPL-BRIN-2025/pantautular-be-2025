from django.db import models
import uuid

# Create your models here.
class User(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=255)  # Sesuai dengan ERD
    email = models.EmailField(unique=True)

    def has_role(self, role_name):
        return self.role == role_name

    def account_exist(self, email):
        return User.objects.filter(email=email).exists()

    def update_password(self, email, new_password):
        user = User.objects.get(email=email)
        user.password = new_password
        user.save()

    def __str__(self):
        return self.name


class Role(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)

    def has_permission(self, perm_name):
        return self.permissions.filter(name=perm_name).exists()

    def __str__(self):
        return self.name


class Permission(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "role")


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

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

    def get_all_diseases():
        return Disease.objects.all()

    def get_disease_by_id(disease_id):
        return Disease.objects.filter(disease_id=disease_id).first()

    def get_disease_cases(self):
        return self.case_set.all()  # Mengambil semua kasus terkait penyakit ini

    def __str__(self):
        return self.name


class HealthProtocolDisease(models.Model):
    health_protocol = models.ForeignKey(HealthProtocol, on_delete=models.CASCADE)
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("health_protocol", "disease")


class Case(models.Model):
    STATUS_CHOICES = [
        ("confirmed", "Confirmed"),
        ("recovered", "Recovered"),
        ("deceased", "Deceased"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gender = models.CharField(max_length=10)
    age = models.IntegerField()
    city = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE)

    def get_all_cases_locations():
        return Location.objects.filter(case__isnull=False)

    def __str__(self):
        return f"Case {self.id} - {self.city}"


class Location(models.Model):
    latitude = models.DecimalField(max_digits=8, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    name = models.CharField(max_length=255, unique=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="locations")

    def get_location_by_name(name):
        return Location.objects.filter(name=name).first()

    def get_all_locations():
        return Location.objects.all()

    def __str__(self):
        return self.name


class News(models.Model):
    portal = models.CharField(max_length=255)
    news_type = models.CharField(max_length=100)
    content = models.TextField()
    url = models.URLField()
    author = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    release_date = models.DateTimeField()

    def get_all_sumber_berita_nasional_detail():
        return News.objects.filter(news_type="Nasional")

    def get_all_sumber_berita_lokal_detail():
        return News.objects.filter(news_type="Lokal")

    def get_all_sumber_berita_kesehatan_detail():
        return News.objects.filter(news_type="Kesehatan")
    
    def get_all_news():
        return News.objects.all()

    def __str__(self):
        return self.title