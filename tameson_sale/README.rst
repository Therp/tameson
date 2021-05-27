============
Tameson_sale
============


Sale related customizations for Tameson

    * Includes fields to enable invoice control policy (ordered/delivered)
      on sale order/sale order lines/payment terms (over-riding the product).
    * Adds a field to mark the order as paid.
    * Runs periodic checks to make sure the business logic is correct and
      a cron job to send notifications when it finds non-validated invoices
      for done pickings.
    * Set 'online payment' (default) or 'signature' (delivered qty) automatically depending on the invoice policy
