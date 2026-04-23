# ===== EduVerse Payment Gateway Integration =====
# Support for multiple payment gateways: Stripe, Moyasar (Saudi Arabia)

try:
    import stripe
except ModuleNotFoundError:
    stripe = None
import requests
import json
import hmac
import hashlib
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import Payment, WalletTransaction
import logging

logger = logging.getLogger(__name__)


class PaymentGatewayFactory:
    """
    Factory pattern for creating payment gateway instances
    Supports: Stripe, Moyasar, and can be extended for other gateways
    """
    
    @staticmethod
    def get_gateway(gateway_name):
        """Get payment gateway instance by name"""
        gateways = {
            'stripe': StripeGateway(),
            'moyasar': MoyasarGateway(),
        }
        
        gateway = gateways.get(gateway_name.lower())
        if not gateway:
            raise ValueError(f"Unsupported payment gateway: {gateway_name}")
        
        return gateway


class BasePaymentGateway:
    """Base class for all payment gateways"""
    
    def __init__(self):
        self.name = "Base Gateway"
        self.is_configured = False
    
    def create_payment_intent(self, amount, currency, metadata=None):
        """Create a payment intent/session"""
        raise NotImplementedError
    
    def confirm_payment(self, payment_id, payment_data):
        """Confirm payment after customer completes checkout"""
        raise NotImplementedError
    
    def refund_payment(self, payment_id, amount=None):
        """Refund a payment"""
        raise NotImplementedError
    
    def get_payment_status(self, payment_id):
        """Get current payment status"""
        raise NotImplementedError
    
    def verify_webhook(self, payload, signature):
        """Verify webhook signature"""
        raise NotImplementedError


class StripeGateway(BasePaymentGateway):
    """
    Stripe Payment Gateway Integration
    Documentation: https://stripe.com/docs
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Stripe"
        self.api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        self.publishable_key = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', None)
        self.webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        
        if self.api_key and stripe is not None:
            stripe.api_key = self.api_key
            self.is_configured = True
        else:
            logger.warning("Stripe API key or stripe package not configured")
    
    def create_payment_intent(self, amount, currency='sar', metadata=None):
        """
        Create Stripe Payment Intent
        
        Args:
            amount: Amount in smallest currency unit (e.g., fils for SAR)
            currency: ISO currency code
            metadata: Additional data to attach
        
        Returns:
            dict with payment_intent_id and client_secret
        """
        if not self.is_configured:
            raise Exception("Stripe is not configured")
        
        try:
            # Convert amount to smallest unit (e.g., SAR to Halalas)
            amount_cents = int(Decimal(amount) * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata or {},
                automatic_payment_methods={'enabled': True},
            )
            
            logger.info(f"Stripe Payment Intent created: {intent.id}")
            
            return {
                'success': True,
                'payment_intent_id': intent.id,
                'client_secret': intent.client_secret,
                'status': intent.status,
                'amount': amount,
                'currency': currency,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def confirm_payment(self, payment_intent_id, payment_data=None):
        """Confirm Stripe Payment Intent"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                return {
                    'success': True,
                    'status': 'completed',
                    'transaction_id': intent.id,
                    'amount': intent.amount / 100,  # Convert back to main unit
                    'currency': intent.currency.upper(),
                }
            else:
                return {
                    'success': False,
                    'status': intent.status,
                    'error': f"Payment not completed. Status: {intent.status}",
                }
                
        except stripe.error.StripeError as e:
            logger.error(f"Stripe confirm error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def refund_payment(self, payment_intent_id, amount=None):
        """Refund a Stripe payment"""
        try:
            refund_data = {'payment_intent': payment_intent_id}
            
            if amount:
                refund_data['amount'] = int(Decimal(amount) * 100)
            
            refund = stripe.Refund.create(**refund_data)
            
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': refund.amount / 100 if refund.amount else None,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_payment_status(self, payment_intent_id):
        """Get Stripe payment status"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                'success': True,
                'status': intent.status,
                'amount': intent.amount / 100,
                'currency': intent.currency.upper(),
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def verify_webhook(self, payload, signature):
        """Verify Stripe webhook signature"""
        if not self.webhook_secret:
            logger.warning("Stripe webhook secret not configured")
            return False
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except ValueError:
            logger.error("Invalid webhook payload")
            return None
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid webhook signature")
            return None


class MoyasarGateway(BasePaymentGateway):
    """
    Moyasar Payment Gateway Integration (Saudi Arabia)
    Documentation: https://moyasar.com/docs/api/
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Moyasar"
        self.api_key = getattr(settings, 'MOYASAR_API_KEY', None)
        self.publishable_key = getattr(settings, 'MOYASAR_PUBLISHABLE_KEY', None)
        self.base_url = "https://api.moyasar.com/v1"
        
        self.is_configured = bool(self.api_key and self.publishable_key)
        
        if not self.is_configured:
            logger.warning("Moyasar API keys not configured")
    
    def create_payment_intent(self, amount, currency='SAR', metadata=None):
        """
        Create Moyasar Payment
        
        Args:
            amount: Amount in main currency unit (SAR)
            currency: Currency code (SAR only for Moyasar)
            metadata: Additional data
        
        Returns:
            dict with payment details
        """
        if not self.is_configured:
            raise Exception("Moyasar is not configured")
        
        try:
            # Moyasar uses Halalas (smallest unit of SAR)
            amount_halalas = int(Decimal(amount) * 100)
            
            payment_data = {
                'amount': amount_halalas,
                'currency': currency,
                'description': metadata.get('description', 'EduVerse Payment'),
                'callback_url': metadata.get('callback_url', ''),
                'source': {
                    'type': 'creditcard',
                },
                'metadata': metadata or {},
            }
            
            response = requests.post(
                f"{self.base_url}/payments",
                auth=(self.api_key, ''),
                json=payment_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"Moyasar payment created: {data.get('id')}")
                
                return {
                    'success': True,
                    'payment_id': data.get('id'),
                    'status': data.get('status'),
                    'amount': amount,
                    'currency': currency,
                    'payment_url': data.get('source', {}).get('transaction_url'),
                }
            else:
                error_msg = response.json().get('message', 'Unknown error')
                logger.error(f"Moyasar error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                }
                
        except Exception as e:
            logger.error(f"Moyasar exception: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def confirm_payment(self, payment_id, payment_data=None):
        """Check Moyasar payment status"""
        try:
            response = requests.get(
                f"{self.base_url}/payments/{payment_id}",
                auth=(self.api_key, '')
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                
                if status == 'paid':
                    return {
                        'success': True,
                        'status': 'completed',
                        'transaction_id': payment_id,
                        'amount': data.get('amount') / 100,
                        'currency': data.get('currency'),
                    }
                else:
                    return {
                        'success': False,
                        'status': status,
                        'error': f"Payment not completed. Status: {status}",
                    }
            else:
                return {
                    'success': False,
                    'error': 'Failed to retrieve payment',
                }
                
        except Exception as e:
            logger.error(f"Moyasar confirm error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def refund_payment(self, payment_id, amount=None):
        """Refund Moyasar payment"""
        try:
            refund_data = {}
            if amount:
                refund_data['amount'] = int(Decimal(amount) * 100)
            
            response = requests.post(
                f"{self.base_url}/payments/{payment_id}/refund",
                auth=(self.api_key, ''),
                json=refund_data
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    'success': True,
                    'refund_id': data.get('id'),
                    'status': data.get('status'),
                    'amount': data.get('amount') / 100 if data.get('amount') else None,
                }
            else:
                return {
                    'success': False,
                    'error': response.json().get('message', 'Refund failed'),
                }
                
        except Exception as e:
            logger.error(f"Moyasar refund error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_payment_status(self, payment_id):
        """Get Moyasar payment status"""
        return self.confirm_payment(payment_id)
    
    def verify_webhook(self, payload, signature):
        """Verify Moyasar webhook (if applicable)"""
        # Moyasar webhook verification implementation
        # Check their documentation for specific implementation
        return True


class PaymentProcessor:
    """
    High-level payment processor that handles the complete payment flow
    """
    
    def __init__(self, gateway_name='stripe'):
        self.gateway = PaymentGatewayFactory.get_gateway(gateway_name)
        self.gateway_name = gateway_name
    
    def process_payment(self, user, amount, currency, payment_method, metadata=None):
        """
        Process a complete payment transaction
        
        Args:
            user: User making the payment
            amount: Payment amount
            currency: Currency code
            payment_method: Payment method type
            metadata: Additional information
        
        Returns:
            Payment object and gateway response
        """
        try:
            # Create payment record in database
            payment = Payment.objects.create(
                user=user,
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                payment_gateway=self.gateway_name,
                status='pending',
                booking_id=metadata.get('booking_id') if metadata else None,
                enrollment_id=metadata.get('enrollment_id') if metadata else None,
            )
            
            # Create payment intent with gateway
            result = self.gateway.create_payment_intent(
                amount=amount,
                currency=currency,
                metadata={
                    'payment_id': str(payment.uuid),
                    'user_id': user.id,
                    'user_email': user.email,
                    **(metadata or {})
                }
            )
            
            if result.get('success'):
                # Update payment with transaction details
                payment.transaction_id = result.get('payment_intent_id') or result.get('payment_id')
                payment.status = 'processing'
                payment.save()
                
                logger.info(f"Payment {payment.uuid} created successfully")
                
                return {
                    'success': True,
                    'payment': payment,
                    'gateway_response': result,
                }
            else:
                payment.status = 'failed'
                payment.failure_reason = result.get('error')
                payment.save()
                
                return {
                    'success': False,
                    'payment': payment,
                    'error': result.get('error'),
                }
                
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def confirm_payment_completion(self, payment_uuid, transaction_data=None):
        """Confirm payment after successful checkout"""
        try:
            payment = Payment.objects.get(uuid=payment_uuid)
            
            # Verify with gateway
            result = self.gateway.confirm_payment(
                payment.transaction_id,
                transaction_data
            )
            
            if result.get('success'):
                payment.status = 'completed'
                payment.save()
                
                # Update related objects (enrollment, booking)
                self._update_related_objects(payment)
                
                logger.info(f"Payment {payment.uuid} confirmed successfully")
                
                return {
                    'success': True,
                    'payment': payment,
                }
            else:
                payment.status = 'failed'
                payment.failure_reason = result.get('error')
                payment.save()
                
                return {
                    'success': False,
                    'error': result.get('error'),
                }
                
        except Payment.DoesNotExist:
            return {
                'success': False,
                'error': 'Payment not found',
            }
        except Exception as e:
            logger.error(f"Payment confirmation error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def _update_related_objects(self, payment):
        """Update enrollment or booking status after successful payment"""
        if payment.enrollment:
            payment.enrollment.payment_status = 'paid'
            payment.enrollment.amount_paid = payment.amount
            payment.enrollment.save()
        
        if payment.booking:
            # Update booking payment status if needed
            pass
    
    def process_refund(self, payment_uuid, amount=None, reason=None):
        """Process a refund"""
        try:
            payment = Payment.objects.get(uuid=payment_uuid)
            
            if payment.status != 'completed':
                return {
                    'success': False,
                    'error': 'Only completed payments can be refunded',
                }
            
            # Process refund with gateway
            result = self.gateway.refund_payment(
                payment.transaction_id,
                amount=amount
            )
            
            if result.get('success'):
                refund_amount = amount or payment.amount
                
                payment.status = 'refunded'
                payment.refunded_amount = refund_amount
                payment.refund_date = timezone.now()
                payment.save()
                
                # Update related objects
                if payment.enrollment:
                    payment.enrollment.payment_status = 'refunded'
                    payment.enrollment.status = 'refunded'
                    payment.enrollment.save()
                
                logger.info(f"Payment {payment.uuid} refunded successfully")
                
                return {
                    'success': True,
                    'payment': payment,
                    'refund_amount': refund_amount,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error'),
                }
                
        except Payment.DoesNotExist:
            return {
                'success': False,
                'error': 'Payment not found',
            }
        except Exception as e:
            logger.error(f"Refund error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
