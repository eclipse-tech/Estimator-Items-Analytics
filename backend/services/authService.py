import requests
from utils.constants import get_auth_config, get_bootstrap_headers, get_api_url, get_default_otp, API_REQUEST_TIMEOUT
from utils.utils import _extract_token_from_response


def generate_auth_token(environment_name):
    auth_config = get_auth_config(environment_name)
    payload = {
        "username": str(auth_config["number"])
    }
    try:
        response = requests.post(
            get_api_url(environment_name, "genrate_auth_url"),
            json=payload,
            headers=get_bootstrap_headers(environment_name=environment_name),
            timeout=API_REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise RuntimeError(
                f"Generate auth token failed: {response.status_code} {response.reason}; "
                f"body={response.text[:500]!r}"
            )
        try:
            data = response.json()
        except ValueError as e:
            raise RuntimeError(
                f"Generate auth token response is not valid JSON: {e}; "
                f"status={response.status_code}; body={response.text[:500]!r}"
            )
    except requests.exceptions.RequestException as e:
        print(e)
        raise e
    except Exception as e:
        print(e)
        raise e


def verify_otp(environment_name, otp):
    auth_config = get_auth_config(environment_name)
    payload = {
        "username": str(auth_config["number"]),
        "otp": otp
    }
    try:
        response = requests.post(
            get_api_url(environment_name, "verify_otp"),
            json=payload,
            headers=get_bootstrap_headers(environment_name=environment_name),
            timeout=API_REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise RuntimeError(
                f"Verify OTP failed: {response.status_code} {response.reason}; "
                f"body={response.text[:500]!r}"
            )
        # Extract and return access token
        return _extract_token_from_response(response)
    except requests.exceptions.RequestException as e:
        print(e)
        raise e


def get_auth_token(environment_name):
    auth_config = get_auth_config(environment_name)
    return auth_config["token"]
    # generate_auth_token(environment_name)
    # return verify_otp(environment_name, get_default_otp())
