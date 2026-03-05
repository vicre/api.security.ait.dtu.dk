# forms.py
from django import forms
from django.core.validators import EmailValidator


class MfaResetLookupForm(forms.Form):
    """Form used for looking up user authentication methods."""

    user_principal_name = forms.EmailField(
        label="userPrincipalName",
        max_length=255,
        validators=[EmailValidator()],
        widget=forms.TextInput(
            attrs={"autocomplete": "email", "class": "form-control"}
        ),
        help_text="Enter the Azure AD userPrincipalName (typically the user's email).",
    )


class DeleteAuthenticationMethodForm(forms.Form):
    """Form used for deleting an individual authentication method."""

    METHOD_TYPE_CHOICES = (
        ("#microsoft.graph.microsoftAuthenticatorAuthenticationMethod", "Microsoft Authenticator"),
        ("#microsoft.graph.phoneAuthenticationMethod", "Phone"),
        ("#microsoft.graph.softwareOathAuthenticationMethod", "Software OATH"),
    )

    user_principal_name = forms.EmailField(
        max_length=255,
        validators=[EmailValidator()],
        widget=forms.HiddenInput(),
    )
    method_id = forms.CharField(max_length=255, widget=forms.HiddenInput())
    method_type = forms.ChoiceField(choices=METHOD_TYPE_CHOICES, widget=forms.HiddenInput())


class DeleteAllAuthenticationMethodsForm(forms.Form):
    """Form used for deleting all authentication methods for a user."""

    user_principal_name = forms.EmailField(
        max_length=255,
        validators=[EmailValidator()],
        widget=forms.HiddenInput(),
    )
