"""What every ODAS client shares: where it lives, and how it is authenticated.

ODAS serves both the device-class taxonomy and the requirement tree behind one
base URL and one credential. That credential is never held here — it arrives
per request from the caller, which is what makes tenancy the caller's to prove
rather than this server's to assume.
"""

BASE_URL_ENV_VAR = "ODAS_BASE_URL"

# The caller supplies its own ODAS credential on this header; the server holds none.
ODAS_TOKEN_HEADER = "X-ODAS-Token"

CREDENTIAL_HINT = f"Supply a valid ODAS token on the {ODAS_TOKEN_HEADER} request header."

ODAS_TOKEN_HINT = (
    "The caller must supply its ODAS token on that header; this server holds no "
    "credentials of its own."
)
