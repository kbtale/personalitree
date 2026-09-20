from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from core.exceptions import PersonaliTreeError
from core.scraper.queue import enqueue_scrape

from .models import (
    BurnerAccount,
    DiscoveredAccount,
    ProfileResult,
    QuestionnaireResponse,
    RawScrape,
    Settings,
    Target,
)


class DiscoveredAccountInline(admin.TabularInline):
    model = DiscoveredAccount
    extra = 0


class RawScrapeInline(admin.TabularInline):
    model = RawScrape
    extra = 0


class QuestionnaireResponseInline(admin.TabularInline):
    model = QuestionnaireResponse
    extra = 0


class ProfileResultInline(admin.TabularInline):
    model = ProfileResult
    extra = 0


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ("seed_username", "status", "attempts", "created_at")
    list_filter = ("status",)
    search_fields = ("seed_username",)
    readonly_fields = ("attempts", "last_error")
    actions = ("queue_scraping",)
    inlines = (
        DiscoveredAccountInline,
        RawScrapeInline,
        QuestionnaireResponseInline,
        ProfileResultInline,
    )

    @admin.action(description="Queue scraping")
    def queue_scraping(
        self,
        request: HttpRequest,
        queryset: QuerySet[Target],
    ) -> None:
        """Queue every selected target for scraping."""
        for target in queryset:
            try:
                task_id = enqueue_scrape(target)
            except PersonaliTreeError as exc:
                self.message_user(
                    request,
                    f"Target {target.pk}: {exc}",
                    level=messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"Queued task {task_id} for target {target.pk}.",
                    level=messages.SUCCESS,
                )


@admin.register(DiscoveredAccount)
class DiscoveredAccountAdmin(admin.ModelAdmin):
    list_display = ("target", "platform_name", "username", "verification_confidence")
    list_filter = ("platform_name",)
    search_fields = ("username", "platform_name")


@admin.register(RawScrape)
class RawScrapeAdmin(admin.ModelAdmin):
    list_display = ("target", "platform_name", "scraped_at")
    list_filter = ("platform_name",)
    search_fields = ("platform_name",)


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = ("target", "question_id", "score", "generated_at")
    list_filter = ("question_id",)
    search_fields = ("question_id",)


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
    search_fields = ("key",)


@admin.register(BurnerAccount)
class BurnerAccountAdmin(admin.ModelAdmin):
    list_display = ("platform_name", "username", "is_active", "password_stored")
    list_filter = ("platform_name", "is_active")
    search_fields = ("platform_name", "username")
    exclude = ("password",)
    readonly_fields = ("password_stored",)

    @admin.display(boolean=True, description="Password stored")
    def password_stored(self, obj: BurnerAccount) -> bool:
        return bool(obj.password)
