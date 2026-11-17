"""Three Stripe sandbox integration exercises. All amounts are USD cents."""
import argparse
import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from success_payment import NoRedirect


def api(key, path, fields=None, idempotency_key=None):
    headers = {'Authorization': f'Bearer {key}'}
    if fields is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Idempotency-Key'] = idempotency_key or str(uuid.uuid4())
    request = Request('https://api.stripe.com/v1/' + path,
                      data=urlencode(fields).encode() if fields is not None else None,
                      headers=headers)
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        body = json.load(exc)
        error = body.get('error', {})
        for field in ('message', 'type', 'code', 'param', 'decline_code'):
            if error.get(field):
                print(f'{field}: {str(error[field]).replace(key, "[REDACTED]")}')
        if exc.headers and exc.headers.get('Request-Id'):
            print('Request ID:', exc.headers['Request-Id'])
        return exc.code, body


def payment_fields(method='pm_card_visa'):
    return {'amount': 1500, 'currency': 'usd', 'payment_method': method,
            'confirm': 'true', 'return_url': 'https://example.com/return'}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def check_payment(status, payment):
    check(status == 200 and payment.get('status') == 'succeeded'
          and payment.get('amount') == 1500 and payment.get('currency') == 'usd'
          and payment.get('livemode') is False and payment.get('id'),
          'Expected a successful USD 15.00 sandbox payment.')


def insufficient_funds(key):
    status, body = api(key, 'payment_intents',
                       payment_fields('pm_card_visa_chargeDeclinedInsufficientFunds'))
    error = body.get('error', {})
    check(status == 402 and error.get('code') == 'card_declined'
          and error.get('decline_code') == 'insufficient_funds',
          'Expected HTTP 402 with insufficient_funds.')
    print('PASS insufficient-funds: expected decline received; no successful payment.')


def duplicate_payment(key):
    # One key and identical fields for both submissions of the same purchase.
    retry_key = str(uuid.uuid4())
    print('Payment retry key:', retry_key)
    fields = payment_fields()
    status, first = api(key, 'payment_intents', fields, retry_key)
    check_payment(status, first)
    status, second = api(key, 'payment_intents', fields, retry_key)
    check_payment(status, second)
    check(first['id'] == second['id'], 'Duplicate submission created a different PaymentIntent!')
    check(first.get('latest_charge') and first['latest_charge'] == second.get('latest_charge'),
          'Expected the same successful charge for both submissions.')
    print(f"PASS duplicate-payment: both requests returned {first['id']}; one USD 15.00 payment.")


def partial_refund(key):
    # Create a fresh payment so this exercise cannot refund an unrelated purchase.
    status, payment = api(key, 'payment_intents', payment_fields())
    check_payment(status, payment)
    print('PaymentIntent:', payment['id'])
    status, refund = api(key, 'refunds', {'payment_intent': payment['id'], 'amount': 500})
    check(status == 200 and refund.get('status') == 'succeeded'
          and refund.get('amount') == 500 and refund.get('currency') == 'usd'
          and refund.get('payment_intent') == payment['id'],
          f"Expected a successful USD 5.00 refund; status={refund.get('status', 'unknown')}.")
    charge_id = refund.get('charge')
    check(isinstance(charge_id, str) and charge_id.startswith('ch_'), 'Missing refund charge ID.')
    status, charge = api(key, 'charges/' + charge_id)
    check(status == 200 and charge.get('livemode') is False
          and charge.get('payment_intent') == payment['id']
          and charge.get('currency') == 'usd' and charge.get('amount') == 1500
          and charge.get('amount_refunded') == 500 and charge.get('refunded') is False,
          'Expected a partially refunded charge: USD 15.00 paid, USD 5.00 refunded.')
    print(f"PASS partial-refund: {refund['id']}; USD 5.00 refunded, USD 10.00 remains unrefunded.")


EXERCISES = {'insufficient-funds': insufficient_funds,
             'duplicate-payment': duplicate_payment, 'partial-refund': partial_refund}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exercise', choices=['all', *EXERCISES])
    args = parser.parse_args()
    key = os.environ.get('STRIPE_SECRET_KEY', '')
    if not key.startswith('sk_test_') or key == 'sk_test_dummy':
        print('Set STRIPE_SECRET_KEY to your Stripe sandbox sk_test_ key.')
        return 1
    failed = False
    names = EXERCISES if args.exercise == 'all' else [args.exercise]
    for name in names:
        print('\nRunning:', name)
        try:
            EXERCISES[name](key)
        except (ValueError, URLError, OSError, KeyError, TypeError) as exc:
            message = str(exc).replace(key, '[REDACTED]') if isinstance(exc, ValueError) else type(exc).__name__
            print('FAIL:', message)
            print('Check the Stripe Dashboard before rerunning; a payment or refund may already exist.')
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
