# Payment-API-Testing

 This repository is a work in progress to learn about API testing for various payment platforms. Most modern digital payment solutions use Stripe, Paypal, or Square for processing payments either in stores or online. To test the integration with each vendor, it is important to test if the various functionalities are working properly. The goal of API integration test is to first test the usual transaction of payment successfully going through. Next, we check for some of the regular corner cases such as insufficient balance, duplicate transaction, or reutrn money to the customer.

Currently, there is Stripe payment platform API testing done using the Stripe Sandbox. This requires privatekey that starts with sk_test. The APIs for Paypal and Square payments will also be added very soon.
