# Bad Tools

## Tool 1: get_customer
Description: "Retrieves customer information."

## Tool 2: lookup_order
Description: "Retrieves order details."

# Good Tools

# Tool 1: get_customer
Description: "Looks up a customer account by customer ID or email.
Use FIRST before any order/billing ops to verify the customer.
Input: customer_id (CUST-12345) OR email address.
Trigger: 'help with my account', 'my name is John Smith'.
Do NOT use for order number lookups — use lookup_order."

## Tool 2: lookup_order
Description: "Looks up an order by order number or email. Use after get_customer when the user mentions an order number.
Input: order_number (ORDER-12345).
Trigger: 'I have a question about order 12345', 'my order number'.
Priority: If user gives both customer name AND order number, use lookup_order immediately."
