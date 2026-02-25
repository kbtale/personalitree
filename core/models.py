from django.db import models


class Target(models.Model):
    """Central entity representing a username under investigation."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SCRAPING = "scraping", "Scraping"
        EVALUATING = "evaluating", "Evaluating"
        COMPLETED = "completed", "Completed"

    seed_username = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seed_username} ({self.status})"


class DiscoveredAccount(models.Model):
    """A social media profile discovered for a target."""

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="discovered_accounts",
    )
    platform_name = models.CharField(max_length=100)
    url = models.URLField(max_length=500)
    username = models.CharField(max_length=255)
    verification_confidence = models.FloatField(default=0.0)

    class Meta:
        unique_together = ("target", "platform_name", "username")
        ordering = ["platform_name"]

    def __str__(self):
        return f"{self.platform_name}: {self.username}"


class RawScrape(models.Model):
    """Unstructured text and metadata scraped from a platform."""

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="raw_scrapes",
    )
    platform_name = models.CharField(max_length=100)
    raw_text_dump = models.TextField(blank=True, default="")
    metadata_json = models.JSONField(default=dict, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scraped_at"]

    def __str__(self):
        return f"{self.platform_name} scrape for {self.target.seed_username}"


class QuestionnaireResponse(models.Model):
    """Individual LLM answer for a single questionnaire question."""

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="questionnaire_responses",
    )
    question_id = models.CharField(max_length=50)
    score = models.IntegerField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("target", "question_id")
        ordering = ["question_id"]

    def __str__(self):
        return f"Q{self.question_id}: {self.score}"


class Settings(models.Model):
    """Key-value runtime configuration store."""

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, default="")

    class Meta:
        verbose_name_plural = "Settings"

    def __str__(self):
        return self.key


class BurnerAccount(models.Model):
    """Credentials for bypassing platform login walls."""

    platform_name = models.CharField(max_length=100)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.platform_name}: {self.username}"
