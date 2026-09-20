from django.core.exceptions import ValidationError
from django.db import models

from core.constants import SCORE_MAX, SCORE_MIN
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
    display_name = models.CharField(max_length=255, blank=True, default="")
    confidence = models.FloatField(default=0.0)
    signals = models.JSONField(default=list, blank=True)

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


class Framework(models.Model):
    """A loaded instrument: what it is, where it came from, and whether it runs."""

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    citation = models.TextField(blank=True, default="")
    source_url = models.URLField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("slug",)

    def __str__(self) -> str:
        return self.name


class Trait(models.Model):
    """A trait an instrument measures; its items roll up into it."""

    framework = models.ForeignKey(
        Framework,
        on_delete=models.CASCADE,
        related_name="traits",
    )
    slug = models.SlugField(max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("framework", "slug")
        ordering = ("slug",)

    def __str__(self) -> str:
        return f"{self.framework.slug}:{self.slug}"


class Question(models.Model):
    """A single instrument item evaluated by the LLM."""

    framework = models.ForeignKey(
        Framework,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    trait = models.ForeignKey(
        Trait,
        on_delete=models.PROTECT,
        related_name="questions",
    )
    question_id = models.CharField(max_length=50)
    text = models.TextField()
    reverse_scored = models.BooleanField(default=False)
    min_score = models.PositiveSmallIntegerField(default=SCORE_MIN)
    max_score = models.PositiveSmallIntegerField(default=SCORE_MAX)

    class Meta:
        unique_together = ("framework", "question_id")
        ordering = ("question_id",)

    def clean(self) -> None:
        """Reject an item whose trait is foreign or whose scale cannot be scored."""
        super().clean()
        if self.trait_id and self.framework_id:
            if self.trait.framework_id != self.framework_id:
                raise ValidationError(
                    {"trait": "must belong to the same framework as the item"}
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
    """Aggregated scores for one target on one instrument."""

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name="profile_results",
    )
    framework = models.ForeignKey(
        Framework,
        on_delete=models.PROTECT,
        related_name="profile_results",
    )
    score_data = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("target", "framework")
        ordering = ("-generated_at",)

    def __str__(self) -> str:
        return f"{self.framework.slug} for {self.target.seed_username}"
