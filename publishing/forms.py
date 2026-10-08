from django import forms
from django.contrib.auth import get_user_model

from .models import Membership


class PageForm(forms.Form):
    title = forms.CharField(max_length=160)
    slug = forms.SlugField(
        max_length=100, help_text="The permanent URL. Set once when creating a page."
    )
    excerpt = forms.CharField(
        max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    body = forms.CharField(
        max_length=100000,
        widget=forms.Textarea(attrs={"rows": 17}),
        help_text="Markdown supported: headings, links, lists and code blocks.",
    )
    expected_version = forms.IntegerField(widget=forms.HiddenInput(), required=False, min_value=1)


class WorkflowForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(
        choices=[
            (action, action)
            for action in ["submit", "publish", "schedule", "reject", "archive", "restore"]
        ]
    )
    scheduled_for = forms.DateTimeField(required=False)
    number = forms.IntegerField(required=False, min_value=1)


class MemberForm(forms.Form):
    username = forms.CharField(max_length=150, help_text="Add an existing account by username.")
    role = forms.ChoiceField(choices=Membership.Role.choices)

    def clean_username(self):
        username = self.cleaned_data["username"]
        try:
            self.member = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as error:
            raise forms.ValidationError("This account does not exist yet.") from error
        return username
