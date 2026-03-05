"""Service wrappers around Graph API helper scripts."""

from .scripts.graph_apicall_deletemfa import microsoft_authentication_method
from .scripts.graph_apicall_deletephone import phone_authentication_method
from .scripts.graph_apicall_deletesoftwaremfa import delete_software_mfa_method
from .scripts.graph_apicall_getuser import get_user
from .scripts.graph_apicall_getuserphoto import get_user_photo
from .scripts.graph_apicall_listuserauthenticationmethods import (
    list_user_authentication_methods,
)


def execute_get_user(user_principal_name, select_parameters):
    return get_user(
        user_principal_name=user_principal_name,
        select_parameters=select_parameters,
    )


def execute_get_user_photo(user_principal_name):
    return get_user_photo(user_principal_name)


def execute_list_user_authentication_methods(user_id):
    response, status_code = list_user_authentication_methods(user_id)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_response": response.text}
    return payload, status_code


def execute_phone_authentication_method(azure_user_principal_id, authentication_method_id):
    return phone_authentication_method(azure_user_principal_id, authentication_method_id)


def execute_microsoft_authentication_method(azure_user_principal_id, authentication_method_id):
    return microsoft_authentication_method(azure_user_principal_id, authentication_method_id)


def execute_delete_software_mfa_method(azure_user_principal_id, authentication_method_id):
    return delete_software_mfa_method(azure_user_principal_id, authentication_method_id)
