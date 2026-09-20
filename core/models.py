from django.core.exceptions import ValidationError
from django.db import models

from core.constants import FRAMEWORK_TRAITS, SCORE_MAX, SCORE_MIN, Framework
from core.exceptions import TargetNotFoundError
from core.fields import EncryptedTextField


class TargetQuerySet(models.QuerySet):
    """Query helpers for Target."""

    def fetch(self, target_id: int) -> "Target":
        """Return the Target with the given id or raise TargetNotFoundError."""
        target = self.filter(id=target_id).first()
        if target is None:
            raise TargetNotFoundError(f"Target {target_id} does not exist")
        return target


class Target(models.Model):
    """Central entity representing a username under investigation."""

    objects = TargetQuerySet.as_manager()

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        SCRAPING = "scraping", "Scraping"
        EVALUATING = "evaluating", "Evaluating"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    seed_username = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
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
        ordering = ("platform_name",)

    def __str__(self) -> str:
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
        unique_together = ("target", "platform_name")
        ordering = ("-scraped_at",)

    def __str__(self) -> str:
        return f"{self.platform_name} scrape for {self.target.seed_username}"


class Question(models.Model):
    """A single questionnaire item evaluated by the LLM."""

    question_id = models.CharField(max_length=50)
    framework_name = models.CharField(max_length=100, choices=Framework.choices)
    trait = models.CharField(max_length=50)
    text = models.TextField()
    reverse_scored = models.BooleanField(default=False)
    min_score = models.PositiveSmallIntegerField(default=SCORE_MIN)
    max_score = models.PositiveSmallIntegerField(default=SCORE_MAX)

    class Meta:
        unique_together = ("framework_name", "question_id")
        ordering = ("question_id",)

    def clean(self) -> None:
        """Reject a trait outside the framework or an inverted score scale."""
        super().clean()
        traits = FRAMEWORK_TRAITS.get(self.framework_name, ())
        if self.trait not in traits:
            raise ValidationError(
                {"trait": f"'{self.trait}' is not part of {self.framework_name}"}
            )
        if self.min_score >= self.max_score:
            raise ValidationError({"min_score": "must be lower than max_score"})

    def __str__(self) -> str:
        return f"{self.question_id}: {self.text[:60]}"


class QuestionnaireResponse(models.Model):
    """Individual LLM answer for a single questionnaire question."""

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="questionnaire_responses",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="responses",
    )
    score = models.IntegerField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("target", "question")
        ordering = ("question__question_id",)

    def __str__(self) -> str:
        return f"Q{self.question.question_id}: {self.score}"


class Settings(models.Model):
    """Key-value runtime configuration store."""

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, default="")

    class Meta:
        verbose_name_plural = "Settings"

    def __str__(self) -> str:
        return self.key


class BurnerAccount(models.Model):
    """Credentials for bypassing platform login walls."""

    platform_name = models.CharField(max_length=100)
    username = models.CharField(max_length=255)
    password = EncryptedTextField()
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.platform_name}: {self.username}"


class ProfileResult(models.Model):
    """Aggregated personality framework scores."""

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="profile_results",
    )
    framework_name = models.CharField(max_length=100, choices=Framework.choices)
    score_data = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("target", "framework_name")
        ordering = ("-generated_at",)

    def __str__(self) -> str:
        return f"{self.framework_name} for {self.target.seed_username}"
