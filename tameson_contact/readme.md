# Tameson Contact Customizations for Odoo 16

This Odoo module provides additional features and constraints for contact management in Odoo 16. It ensures unique email addresses for non-parent/child contacts, provides additional permissions for sales_team administrators to merge contacts, and adds a server action for admin/settings users to find and merge all contacts having duplicate emails.

## Features

-   Contact creation with unique email constraint
-   Enhanced contact merging capabilities for sales_team administrators
-   Server action to find and merge contacts with duplicate emails

## Installation

To install this module, simply place it in your `addons` folder and update the app list in your Odoo instance. Then, search for `Tameson Contact Customizations` in the list of available apps and click the `Install` button.

## Dependencies

-   `base_address_extended`
-   `sales_team`

## Impact on Odoo Default Functionality, take into account on upgrade

This module extends the default Odoo contact management functionalities as follows:

1. **Unique email constraint**: In the default Odoo functionality, duplicate email addresses are allowed for contacts. This module enforces a unique email constraint for non-parent/child contacts, ensuring that each contact has a unique email address.

2. **Enhanced contact merging**: By default, Odoo provides contact merging capabilities but with limited permissions. This module expands the permissions, allowing sales_team administrators to merge contacts.

3. **Server action for merging contacts**: The default Odoo functionality does not include a server action to find and merge all contacts with duplicate emails. This module adds a server action for admin/settings users to find and merge duplicate contacts. Child contacts will be archived if they have the same zip code; otherwise, they will be set as other addresses. The newest delivery and invoice
   contacts will remain unchanged.

## Data

-   `views/contact.xml`: Contains the view definition for the contact form.
-   `wizard/tameson_merge.xml`: Contains the view definition for the contact merge wizard.
