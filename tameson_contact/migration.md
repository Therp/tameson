**src/tameson/tameson_contact/models/partner_type.py**

-   Model for partner type

**src/tameson/tameson_contact/models/res_partner.py**

-   partner type
-   Contact type partner address field include street
-   Email constraint
-   Child constraint
-   Reset portal user password from contact
-   Extract house address from street
-   Partner with VAT set as company
-   company_name string field value create as separate contact, make parent company

**src/tameson/tameson_contact/views/contact.xml**

-   Partner type
-   Help tab
-   email, country required
-   If portal account, button to reset password
-   Reset password link

**src/tameson/tameson_contact/views/partner_type.xml**

-   Model views

**src/tameson/tameson_contact/wizard/contact_creation.py** **src/tameson/tameson_contact/wizard/contact_creation.xml**

-   Contact creation wizard for tameson

**src/tameson/tameson_contact/wizard/tameson_merge.py** **src/tameson/tameson_contact/wizard/tameson_merge.xml**

-   Tameson wizard for contact merge

**src/tameson/tameson_contact/wizard/base_partner_merge.py**

-   Skip extra check for Sales manager for default contact merge operation
