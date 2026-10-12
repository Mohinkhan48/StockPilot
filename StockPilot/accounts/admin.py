from django.contrib import admin

from accounts.models import Workspace, WorkspaceMembership


class MembershipInline(admin.TabularInline):
    model = WorkspaceMembership
    extra = 0
    fields = ('user', 'role', 'joined_at')
    readonly_fields = ('joined_at',)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display  = ('name', 'owner', 'created_at')
    search_fields = ('name', 'owner__username')
    inlines       = [MembershipInline]


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display  = ('workspace', 'user', 'role', 'joined_at')
    list_filter   = ('role',)
    search_fields = ('workspace__name', 'user__username')
