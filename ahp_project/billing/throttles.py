# billing/throttles.py

from rest_framework.throttling import UserRateThrottle


class PaymentCreateThrottle(UserRateThrottle):
    """10 order-creation attempts per hour per user.

    Scope matches DEFAULT_THROTTLE_RATES['payment_create'] in settings.py.
    """
    scope = 'payment_create'


class PaymentVerifyThrottle(UserRateThrottle):
    """20 payment-verification attempts per hour per user.

    Scope matches DEFAULT_THROTTLE_RATES['payment_verify'] in settings.py.
    """
    scope = 'payment_verify'
