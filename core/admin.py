from django.contrib import admin

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
    list_display = ("seed_username", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("seed_username",)
    inlines = [
        DiscoveredAccountInline,
        RawScrapeInline,
        QuestionnaireResponseInline,
        ProfileResultInline,
    ]


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
    list_display = ("platform_name", "username", "is_active")
    list_filter = ("platform_name", "is_active")
    search_fields = ("platform_name", "username")
