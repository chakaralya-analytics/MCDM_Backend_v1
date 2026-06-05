# billing/urls.py
# Relative paths only — the api/v1/billing/ prefix is owned by ahp_project/urls.py.

from django.urls import path
from . import views
from .webhooks import razorpay_webhook

urlpatterns = [
    path('create-order/', views.CreateOrderView.as_view(), name='billing_create_order'),   # POST /api/v1/billing/create-order/
    path('verify-payment/', views.VerifyPaymentView.as_view(), name='billing_verify_payment'), # POST /api/v1/billing/verify-payment/
    path('payments/', views.PaymentHistoryView.as_view(), name='billing_payments'),        # GET  /api/v1/billing/payments/

    # Webhook — CSRF-exempt, HMAC-SHA256 verified.
    # Register this URL in Razorpay Dashboard → Settings → Webhooks.
    path('webhook/razorpay/', razorpay_webhook, name='razorpay_webhook'),                  # POST /api/v1/billing/webhook/razorpay/
]
