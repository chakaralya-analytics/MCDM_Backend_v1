# billing/views.py

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from plans.services.subscription_service import get_subscription_info
from .serializers import (
    CreateOrderSerializer,
    PaymentRecordSerializer,
    VerifyPaymentSerializer,
)
from .services import billing_service
from .tasks import send_payment_success_email, send_payment_failure_notification
from .throttles import PaymentCreateThrottle, PaymentVerifyThrottle

logger = logging.getLogger(__name__)


class CreateOrderView(APIView):
    """POST /api/v1/billing/create-order/

    Creates a Razorpay order and a pending PaymentRecord.
    Returns the payload the frontend passes to the Razorpay checkout widget.
    Amount is calculated server-side — never from the request body.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentCreateThrottle]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan_name = serializer.validated_data.get('plan')
        billing_cycle = serializer.validated_data['billing_cycle']
        credit_pack = serializer.validated_data.get('credit_pack')

        try:
            if credit_pack:
                order_data = billing_service.create_credit_pack_order(
                    user=request.user,
                    pack_id=credit_pack,
                )
            else:
                order_data = billing_service.create_order(
                    user=request.user,
                    plan_name=plan_name,
                    billing_cycle=billing_cycle,
                )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            logger.warning(
                "create_order auth/config failure: user=%s plan=%s credit_pack=%s",
                request.user.id, plan_name, credit_pack,
            )
            return Response({'error': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as exc:
            error_text = str(exc).lower()
            if 'authentication' in error_text or 'unauthorized' in error_text:
                logger.warning(
                    "create_order provider auth failure: user=%s plan=%s credit_pack=%s",
                    request.user.id, plan_name, credit_pack,
                )
                return Response(
                    {'error': 'Razorpay authentication failed.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            logger.exception(
                "create_order failed: user=%s plan=%s credit_pack=%s",
                request.user.id, plan_name, credit_pack,
            )
            return Response(
                {'error': 'Failed to create payment order. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(order_data, status=status.HTTP_201_CREATED)


class VerifyPaymentView(APIView):
    """POST /api/v1/billing/verify-payment/

    Verifies the Razorpay payment signature server-side, activates the
    subscription, and returns the updated subscription state.

    Security: NEVER trust the frontend's payment success alone.
    The signature check here is the authoritative gate.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentVerifyThrottle]

    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data

        try:
            record = billing_service.verify_payment(
                user=request.user,
                order_id=d['razorpay_order_id'],
                payment_id=d['razorpay_payment_id'],
                signature=d['razorpay_signature'],
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception(
                "verify_payment failed: user=%s order=%s",
                request.user.id, d.get('razorpay_order_id'),
            )
            return Response(
                {'error': 'Payment verification failed. Please contact support.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Enqueue confirmation email asynchronously — non-blocking.
        send_payment_success_email.delay(request.user.id, record.id)

        return Response({
            'status': 'success',
            'payment': PaymentRecordSerializer(record).data,
            'subscription': get_subscription_info(request.user),
        }, status=status.HTTP_200_OK)


class PaymentHistoryView(APIView):
    """GET /api/v1/billing/payments/ — recent payment records for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        records = billing_service.get_payment_history(request.user)
        return Response(PaymentRecordSerializer(records, many=True).data)
