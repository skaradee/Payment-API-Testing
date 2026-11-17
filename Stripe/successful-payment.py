"""Send one USD 15.00 payment to Stripe's sandbox using a successful test card."""
import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    key = os.environ.get('STRIPE_SECRET_KEY', '')
    if not key.startswith('sk_test_') or key == 'sk_test_dummy':
        print('Set STRIPE_SECRET_KEY to your Stripe sandbox secret key (sk_test_...).')
        return 1

    # Stripe amounts are in cents. pm_card_visa simulates a successful card;
    # there is no actual test-card balance to fund or check.
    request = Request(
        'https://api.stripe.com/v1/payment_intents',
        method='POST',
        data=urlencode({
            'amount': 1500,
            'currency': 'usd',
            'payment_method': 'pm_card_visa',
            # Eligible payment methods are configured in the Stripe Dashboard.
            'confirm': 'true',
            'return_url': 'https://example.com/return',
        }).encode(),
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Idempotency-Key': str(uuid.uuid4()),
        },
    )

    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            payment = json.load(response)
    except HTTPError as exc:
        print(f'FAIL: Stripe returned HTTP {exc.code}.')
        try:
            error = json.load(exc).get('error', {})
            for field in ('message', 'type', 'code', 'param', 'decline_code'):
                if error.get(field):
                    # Only show diagnostic fields, never the full payment or request.
                    value = str(error[field]).replace(key, '[REDACTED]')
                    print(f'{field}: {value}')
        except (ValueError, AttributeError, OSError):
            print('Stripe did not provide a readable JSON error.')
        request_id = exc.headers.get('Request-Id') if exc.headers else None
        if request_id:
            print(f'Request ID: {request_id}')
        return 1
    except (URLError, OSError, ValueError):
        print('FAIL: Could not obtain a valid Stripe response. Check the Dashboard before retrying.')
        return 1

    if (payment.get('status') == 'succeeded'
            and payment.get('amount') == 1500
            and payment.get('currency') == 'usd'
            and payment.get('livemode') is False):
        print(f"PASS: USD 15.00 test payment succeeded. PaymentIntent: {payment['id']}")
        return 0
    print(f"FAIL: Unexpected payment status: {payment.get('status', 'unknown')}")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
