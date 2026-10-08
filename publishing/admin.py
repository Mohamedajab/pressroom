from django.contrib import admin

from .models import Workspace

# Editorial models intentionally stay outside admin: all changes go through services.
# Use the bootstrap command to create a workspace and owner.
admin.site.register(Workspace)
admin.site.site_header = "Pressroom administration"
